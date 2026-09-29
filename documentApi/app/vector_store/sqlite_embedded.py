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
            file_name TEXT NOT NULL,
            source_id TEXT NOT NULL DEFAULT '',
            content_hash TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL DEFAULT 1,
            is_active INTEGER NOT NULL DEFAULT 1,
            canonical_location TEXT NOT NULL DEFAULT '',
            corpus_version TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            instrument TEXT NOT NULL DEFAULT '',
            authority TEXT NOT NULL DEFAULT 'unclassified',
            document_status TEXT NOT NULL DEFAULT 'active',
            section TEXT NOT NULL DEFAULT '',
            heading_path TEXT NOT NULL DEFAULT '[]',
            parent_section TEXT NOT NULL DEFAULT '',
            previous_section TEXT NOT NULL DEFAULT '',
            next_section TEXT NOT NULL DEFAULT '',
            content_types TEXT NOT NULL DEFAULT '[]'
        )"""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(ddl)
                existing = {row[1] for row in conn.execute(f'PRAGMA table_info("{t}")')}
                additions = {
                    "source_id": "TEXT NOT NULL DEFAULT ''",
                    "content_hash": "TEXT NOT NULL DEFAULT ''",
                    "version": "INTEGER NOT NULL DEFAULT 1",
                    "is_active": "INTEGER NOT NULL DEFAULT 1",
                    "canonical_location": "TEXT NOT NULL DEFAULT ''",
                    "corpus_version": "TEXT NOT NULL DEFAULT ''",
                    "category": "TEXT NOT NULL DEFAULT ''",
                    "instrument": "TEXT NOT NULL DEFAULT ''",
                    "authority": "TEXT NOT NULL DEFAULT 'unclassified'",
                    "document_status": "TEXT NOT NULL DEFAULT 'active'",
                    "section": "TEXT NOT NULL DEFAULT ''",
                    "heading_path": "TEXT NOT NULL DEFAULT '[]'",
                    "parent_section": "TEXT NOT NULL DEFAULT ''",
                    "previous_section": "TEXT NOT NULL DEFAULT ''",
                    "next_section": "TEXT NOT NULL DEFAULT ''",
                    "content_types": "TEXT NOT NULL DEFAULT '[]'",
                }
                for column, column_ddl in additions.items():
                    if column not in existing:
                        conn.execute(f'ALTER TABLE "{t}" ADD COLUMN {column} {column_ddl}')
                conn.execute(f"UPDATE \"{t}\" SET source_id = document_id WHERE source_id = ''")
                conn.execute(f"UPDATE \"{t}\" SET content_hash = document_id WHERE content_hash = ''")
                conn.execute(
                    f'CREATE INDEX IF NOT EXISTS "{t}_document_id_idx" ON "{t}" (document_id)'
                )
                conn.execute(
                    f'CREATE INDEX IF NOT EXISTS "{t}_source_active_idx" ON "{t}" (source_id, is_active)'
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

    def remove_source(self, table_name: str, source_id: str) -> None:
        t = _sanitize_table_name(table_name)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(f'DELETE FROM "{t}" WHERE source_id = ?', (source_id,))
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
        source_id = str(payloads[0].get("sourceId", doc_id)) if payloads else doc_id
        self.replace_source_chunks(table_name, source_id, doc_id, vectors, payloads)

    def replace_source_chunks(
        self,
        table_name: str,
        source_id: str,
        doc_id: str,
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None:
        if len(vectors) != len(payloads):
            raise ValueError("Anzahl von Vektoren und Payloads muss identisch sein.")
        if not vectors:
            raise ValueError("Mindestens ein Vektor ist fuer den Source-Austausch erforderlich.")
        t = _sanitize_table_name(table_name)
        sql = f"""INSERT INTO "{t}" (
            point_id, document_id, chunk_index, embedding,
            source_path, source_modified_unix_seconds,
            text_content, tags, source, file_name, source_id, content_hash,
            version, is_active, canonical_location, corpus_version,
            category, instrument, authority, document_status, section, heading_path,
            parent_section, previous_section, next_section, content_types
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(point_id) DO UPDATE SET
            document_id = excluded.document_id,
            chunk_index = excluded.chunk_index,
            embedding = excluded.embedding,
            source_path = excluded.source_path,
            source_modified_unix_seconds = excluded.source_modified_unix_seconds,
            text_content = excluded.text_content,
            tags = excluded.tags,
            source = excluded.source,
            file_name = excluded.file_name,
            source_id = excluded.source_id,
            content_hash = excluded.content_hash,
            version = excluded.version,
            is_active = excluded.is_active,
            canonical_location = excluded.canonical_location,
            corpus_version = excluded.corpus_version,
            category = excluded.category,
            instrument = excluded.instrument,
            authority = excluded.authority,
            document_status = excluded.document_status,
            section = excluded.section,
            heading_path = excluded.heading_path,
            parent_section = excluded.parent_section,
            previous_section = excluded.previous_section,
            next_section = excluded.next_section,
            content_types = excluded.content_types"""
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
                    source_id,
                    payload.get("contentHash", doc_id),
                    int(payload.get("version", 1)),
                    0,
                    payload.get("canonicalLocation", ""),
                    payload.get("corpusVersion", ""),
                    payload.get("category", ""),
                    payload.get("instrument", ""),
                    payload.get("authority", "unclassified"),
                    payload.get("documentStatus", "active"),
                    payload.get("section", ""),
                    json.dumps(payload.get("headingPath", [])),
                    payload.get("parentSection", ""),
                    payload.get("previousSection", ""),
                    payload.get("nextSection", ""),
                    json.dumps(payload.get("contentTypes", [])),
                )
            )
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(f'DELETE FROM "{t}" WHERE document_id = ?', (doc_id,))
                conn.executemany(sql, rows)
                conn.execute(f'UPDATE "{t}" SET is_active = 0 WHERE source_id = ?', (source_id,))
                conn.execute(
                    f'UPDATE "{t}" SET is_active = 1 WHERE source_id = ? AND document_id = ?',
                    (source_id, doc_id),
                )
                conn.commit()
                _logger.info("sqlite source replacement fertig: source=%s… doc=%s… rows=%s", source_id[:12], doc_id[:12], len(rows))
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def activate_source_version(self, table_name: str, source_id: str, doc_id: str) -> None:
        t = _sanitize_table_name(table_name)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                count = conn.execute(
                    f'SELECT COUNT(*) FROM "{t}" WHERE source_id = ? AND document_id = ?',
                    (source_id, doc_id),
                ).fetchone()[0]
                if not count:
                    raise ValueError(f"Keine Vektoren fuer Source-Version {source_id}/{doc_id}")
                conn.execute(f'UPDATE "{t}" SET is_active = 0 WHERE source_id = ?', (source_id,))
                conn.execute(
                    f'UPDATE "{t}" SET is_active = 1 WHERE source_id = ? AND document_id = ?',
                    (source_id, doc_id),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def cleanup_inactive_versions(self, table_name: str, source_id: str | None = None) -> int:
        t = _sanitize_table_name(table_name)
        with self._lock:
            conn = self._connect()
            try:
                if source_id is None:
                    cur = conn.execute(f'DELETE FROM "{t}" WHERE is_active = 0')
                else:
                    cur = conn.execute(
                        f'DELETE FROM "{t}" WHERE is_active = 0 AND source_id = ?', (source_id,)
                    )
                conn.commit()
                return int(cur.rowcount or 0)
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
                    f'SELECT text_content, document_id, file_name, chunk_index, source_path, source, embedding, category, instrument, authority, document_status, section, heading_path, parent_section, previous_section, next_section, content_types, source_id, canonical_location, corpus_version FROM "{t}" WHERE is_active = 1'
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
            scored.append((sim, row[:6] + row[7:]))

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
                    "category": row[6],
                    "instrument": row[7],
                    "authority": row[8],
                    "status": row[9],
                    "section": row[10],
                    "headingPath": json.loads(row[11]),
                    "parentSection": row[12],
                    "previousSection": row[13],
                    "nextSection": row[14],
                    "contentTypes": json.loads(row[15]),
                    "sourceId": row[16],
                    "canonicalLocation": row[17],
                    "corpusVersion": row[18],
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
                    f'SELECT text_content, document_id, file_name, chunk_index, source_path, source, embedding, category, instrument, authority, document_status, section, heading_path, parent_section, previous_section, next_section, content_types, source_id, canonical_location, corpus_version FROM "{t}"'
                    f' WHERE is_active = 1 AND lower(file_name) LIKE ?',
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
            scored.append((sim, row[:6] + row[7:]))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "text": row[0],
                "documentId": row[1],
                "fileName": row[2],
                "chunkIndex": row[3],
                "sourcePath": row[4],
                "source": row[5],
                "category": row[6],
                "instrument": row[7],
                "authority": row[8],
                "status": row[9],
                "section": row[10],
                "headingPath": json.loads(row[11]),
                "parentSection": row[12],
                "previousSection": row[13],
                "nextSection": row[14],
                "contentTypes": json.loads(row[15]),
                "sourceId": row[16],
                "canonicalLocation": row[17],
                "corpusVersion": row[18],
                "similarity": sim,
            }
            for sim, row in scored[: max(1, top_k)]
        ]
