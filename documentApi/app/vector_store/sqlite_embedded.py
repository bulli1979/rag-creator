from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from pathlib import Path

import numpy as np

from ..file_store import create_sha256

_logger = logging.getLogger(__name__)


def _sanitize_table_name(name: str) -> str:
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        raise ValueError(f"Ungueltiger Tabellenname: {name}")
    return name


class SqliteEmbeddedVectorStore:
    """Eingebettete Vektorsuche ohne Server: SQLite + Cosinus-Ähnlichkeit (Embeddings normalisiert)."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path), timeout=120)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def health_check(self) -> dict:
        try:
            with self._lock:
                conn = self._connect()
                try:
                    conn.execute("SELECT 1")
                finally:
                    conn.close()
            return {"status": "ok", "message": f"SQLite embedded OK ({self._db_path})."}
        except Exception as exc:
            return {"status": "error", "message": f"SQLite Fehler: {exc}"}

    def ensure_schema(self, table_name: str) -> None:
        t = _sanitize_table_name(table_name)
        ddl = f"""CREATE TABLE IF NOT EXISTS "{t}" (
            point_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            embedding TEXT NOT NULL,
            source_path TEXT NOT NULL,
            source_modified_unix_seconds INTEGER NOT NULL,
            text_content TEXT NOT NULL,
            tags TEXT NOT NULL,
            source TEXT NOT NULL,
            file_name TEXT NOT NULL
        )"""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(ddl)
                conn.execute(
                    f'CREATE INDEX IF NOT EXISTS "{t}_document_id_idx" ON "{t}" (document_id)'
                )
                conn.commit()
            finally:
                conn.close()

    def remove_document(self, table_name: str, doc_id: str) -> None:
        t = _sanitize_table_name(table_name)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(f'DELETE FROM "{t}" WHERE document_id = ?', (doc_id,))
                conn.commit()
            finally:
                conn.close()

    def upsert_document_chunks(
        self,
        table_name: str,
        doc_id: str,
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None:
        if len(vectors) != len(payloads):
            raise ValueError("Anzahl von Vektoren und Payloads muss identisch sein.")
        t = _sanitize_table_name(table_name)
        sql = f"""INSERT INTO "{t}" (
            point_id, document_id, chunk_index, embedding,
            source_path, source_modified_unix_seconds,
            text_content, tags, source, file_name
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(point_id) DO UPDATE SET
            document_id = excluded.document_id,
            chunk_index = excluded.chunk_index,
            embedding = excluded.embedding,
            source_path = excluded.source_path,
            source_modified_unix_seconds = excluded.source_modified_unix_seconds,
            text_content = excluded.text_content,
            tags = excluded.tags,
            source = excluded.source,
            file_name = excluded.file_name"""
        rows: list[tuple] = []
        for vector, payload in zip(vectors, payloads):
            chunk_ix = int(payload["chunkIndex"])
            point_id = create_sha256(f"{doc_id}:{chunk_ix}")
            rows.append(
                (
                    point_id,
                    payload["documentId"],
                    chunk_ix,
                    json.dumps(vector),
                    payload["sourcePath"],
                    int(payload["sourceModifiedUnixSeconds"]),
                    payload["text"],
                    json.dumps(payload["tags"]),
                    payload["source"],
                    payload["fileName"],
                )
            )
        with self._lock:
            conn = self._connect()
            try:
                conn.executemany(sql, rows)
                conn.commit()
                _logger.info("sqlite upsert fertig: doc_id=%s… rows=%s", doc_id[:16], len(rows))
            finally:
                conn.close()

    def similarity_search(
        self,
        table_name: str,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        t = _sanitize_table_name(table_name)
        q = np.asarray(query_vector, dtype=np.float64)
        qn = np.linalg.norm(q)
        if qn > 0:
            q = q / qn
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    f'SELECT text_content, document_id, file_name, chunk_index, source_path, source, embedding FROM "{t}"'
                )
                all_rows = cur.fetchall()
            finally:
                conn.close()

        scored: list[tuple[float, tuple]] = []
        for row in all_rows:
            emb = np.asarray(json.loads(row[6]), dtype=np.float64)
            en = np.linalg.norm(emb)
            if en > 0:
                emb = emb / en
            sim = float(np.dot(q, emb))
            scored.append((sim, row[:6]))

        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[dict] = []
        for sim, row in scored[: max(1, top_k)]:
            out.append(
                {
                    "text": row[0],
                    "documentId": row[1],
                    "fileName": row[2],
                    "chunkIndex": row[3],
                    "sourcePath": row[4],
                    "source": row[5],
                    "similarity": sim,
                }
            )
        return out

    def search_by_filename(
        self,
        table_name: str,
        pattern: str,
        query_vector: list[float],
        top_k: int = 2,
    ) -> list[dict]:
        """Return top_k chunks whose file_name contains pattern (case-insensitive), ordered by similarity."""
        t = _sanitize_table_name(table_name)
        q = np.asarray(query_vector, dtype=np.float64)
        qn = np.linalg.norm(q)
        if qn > 0:
            q = q / qn
        pat = pattern.lower()
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    f'SELECT text_content, document_id, file_name, chunk_index, source_path, source, embedding FROM "{t}"'
                    f' WHERE lower(file_name) LIKE ?',
                    (f"%{pat}%",),
                )
                all_rows = cur.fetchall()
            finally:
                conn.close()
        scored: list[tuple[float, tuple]] = []
        for row in all_rows:
            emb = np.asarray(json.loads(row[6]), dtype=np.float64)
            en = np.linalg.norm(emb)
            if en > 0:
                emb = emb / en
            sim = float(np.dot(q, emb))
            scored.append((sim, row[:6]))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "text": row[0],
                "documentId": row[1],
                "fileName": row[2],
                "chunkIndex": row[3],
                "sourcePath": row[4],
                "source": row[5],
                "similarity": sim,
            }
            for sim, row in scored[: max(1, top_k)]
        ]
