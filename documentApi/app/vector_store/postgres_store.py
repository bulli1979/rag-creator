from __future__ import annotations

import json
import logging
import re

import psycopg2
import psycopg2.pool
from psycopg2.extras import execute_batch

from ..file_store import create_sha256

_logger = logging.getLogger(__name__)

_PG_UPSERT_PAGE_SIZE = 64


class PostgresVectorStore:
    """pgvector in Postgres (wie bisher)."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "rag",
        user: str = "postgres",
        password: str = "",
        schema: str = "public",
    ) -> None:
        self._schema = schema
        self._config = {
            "host": host,
            "port": port,
            "dbname": database,
            "user": user,
            "password": password,
        }
        self._pool: psycopg2.pool.SimpleConnectionPool | None = None
        self._try_create_pool()

    def _try_create_pool(self) -> None:
        try:
            self._pool = psycopg2.pool.SimpleConnectionPool(
                1,
                10,
                connect_timeout=30,
                **self._config,
            )
        except Exception:
            self._pool = None

    def update_connection_config(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        schema: str = "public",
    ) -> None:
        if self._pool:
            try:
                self._pool.closeall()
            except Exception:
                pass
        self._schema = schema
        self._config = {
            "host": host,
            "port": port,
            "dbname": database,
            "user": user,
            "password": password,
        }
        self._try_create_pool()

    @staticmethod
    def _safe_ident(name: str) -> str:
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
            raise ValueError(f"Ungueltiger Postgres-Bezeichner: {name}")
        return f'"{name}"'

    def _qualified_table(self, table_name: str) -> str:
        return f"{self._safe_ident(self._schema)}.{self._safe_ident(table_name)}"

    def health_check(self) -> dict:
        try:
            conn = self._get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return {"status": "ok", "message": "Postgres erreichbar."}
            finally:
                self._put_conn(conn)
        except Exception as exc:
            return {"status": "error", "message": f"Postgres Fehler: {exc}"}

    def ensure_schema(self, table_name: str) -> None:
        qualified = self._qualified_table(table_name)
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self._safe_ident(self._schema)}")
                cur.execute(
                    f"""CREATE TABLE IF NOT EXISTS {qualified} (
                        point_id text PRIMARY KEY,
                        document_id text NOT NULL,
                        chunk_index integer NOT NULL,
                        embedding vector NOT NULL,
                        source_path text NOT NULL,
                        source_modified_unix_seconds bigint NOT NULL,
                        text_content text NOT NULL,
                        tags jsonb NOT NULL,
                        source text NOT NULL,
                        file_name text NOT NULL,
                        source_id text NOT NULL DEFAULT '',
                        content_hash text NOT NULL DEFAULT '',
                        version integer NOT NULL DEFAULT 1,
                        is_active boolean NOT NULL DEFAULT true,
                        canonical_location text NOT NULL DEFAULT '',
                        corpus_version text NOT NULL DEFAULT '',
                        category text NOT NULL DEFAULT '',
                        instrument text NOT NULL DEFAULT '',
                        authority text NOT NULL DEFAULT 'unclassified',
                        document_status text NOT NULL DEFAULT 'active',
                        section text NOT NULL DEFAULT '',
                        heading_path jsonb NOT NULL DEFAULT '[]'::jsonb,
                        parent_section text NOT NULL DEFAULT '',
                        previous_section text NOT NULL DEFAULT '',
                        next_section text NOT NULL DEFAULT '',
                        content_types jsonb NOT NULL DEFAULT '[]'::jsonb
                    )"""
                )
                for column, ddl in (
                    ("source_id", "text NOT NULL DEFAULT ''"),
                    ("content_hash", "text NOT NULL DEFAULT ''"),
                    ("version", "integer NOT NULL DEFAULT 1"),
                    ("is_active", "boolean NOT NULL DEFAULT true"),
                    ("canonical_location", "text NOT NULL DEFAULT ''"),
                    ("corpus_version", "text NOT NULL DEFAULT ''"),
                    ("category", "text NOT NULL DEFAULT ''"),
                    ("instrument", "text NOT NULL DEFAULT ''"),
                    ("authority", "text NOT NULL DEFAULT 'unclassified'"),
                    ("document_status", "text NOT NULL DEFAULT 'active'"),
                    ("section", "text NOT NULL DEFAULT ''"),
                    ("heading_path", "jsonb NOT NULL DEFAULT '[]'::jsonb"),
                    ("parent_section", "text NOT NULL DEFAULT ''"),
                    ("previous_section", "text NOT NULL DEFAULT ''"),
                    ("next_section", "text NOT NULL DEFAULT ''"),
                    ("content_types", "jsonb NOT NULL DEFAULT '[]'::jsonb"),
                ):
                    cur.execute(f"ALTER TABLE {qualified} ADD COLUMN IF NOT EXISTS {column} {ddl}")
                cur.execute(f"UPDATE {qualified} SET source_id = document_id WHERE source_id = ''")
                cur.execute(f"UPDATE {qualified} SET content_hash = document_id WHERE content_hash = ''")
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS {self._safe_ident(table_name + '_document_id_idx')} "
                    f"ON {qualified} (document_id)"
                )
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS {self._safe_ident(table_name + '_source_active_idx')} "
                    f"ON {qualified} (source_id, is_active)"
                )
            conn.commit()
        finally:
            self._put_conn(conn)

    def remove_document(self, table_name: str, doc_id: str) -> None:
        qualified = self._qualified_table(table_name)
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {qualified} WHERE document_id = %s", (doc_id,))
            conn.commit()
        finally:
            self._put_conn(conn)

    def remove_source(self, table_name: str, source_id: str) -> None:
        qualified = self._qualified_table(table_name)
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {qualified} WHERE source_id = %s", (source_id,))
            conn.commit()
        finally:
            self._put_conn(conn)

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

        n = len(vectors)
        qualified = self._qualified_table(table_name)
        sql = f"""INSERT INTO {qualified} (
            point_id, document_id, chunk_index, embedding,
            source_path, source_modified_unix_seconds,
            text_content, tags, source, file_name, source_id, content_hash,
            version, is_active, canonical_location, corpus_version,
            category, instrument, authority, document_status, section, heading_path,
            parent_section, previous_section, next_section, content_types
        ) VALUES (
            %s, %s, %s, %s::vector, %s, %s, %s, %s::jsonb, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
            %s, %s, %s, %s::jsonb
        )
        ON CONFLICT (point_id) DO UPDATE SET
            document_id = EXCLUDED.document_id,
            chunk_index = EXCLUDED.chunk_index,
            embedding = EXCLUDED.embedding,
            source_path = EXCLUDED.source_path,
            source_modified_unix_seconds = EXCLUDED.source_modified_unix_seconds,
            text_content = EXCLUDED.text_content,
            tags = EXCLUDED.tags,
            source = EXCLUDED.source,
            file_name = EXCLUDED.file_name,
            source_id = EXCLUDED.source_id,
            content_hash = EXCLUDED.content_hash,
            version = EXCLUDED.version,
            is_active = EXCLUDED.is_active,
            canonical_location = EXCLUDED.canonical_location,
            corpus_version = EXCLUDED.corpus_version,
            category = EXCLUDED.category,
            instrument = EXCLUDED.instrument,
            authority = EXCLUDED.authority,
            document_status = EXCLUDED.document_status,
            section = EXCLUDED.section,
            heading_path = EXCLUDED.heading_path,
            parent_section = EXCLUDED.parent_section,
            previous_section = EXCLUDED.previous_section,
            next_section = EXCLUDED.next_section,
            content_types = EXCLUDED.content_types"""

        rows: list[tuple] = []
        for vector, payload in zip(vectors, payloads):
            chunk_ix = int(payload["chunkIndex"])
            point_id = create_sha256(f"{doc_id}:{chunk_ix}")
            vector_literal = f"[{','.join(str(v) for v in vector)}]"
            rows.append(
                (
                    point_id,
                    payload["documentId"],
                    chunk_ix,
                    vector_literal,
                    payload["sourcePath"],
                    payload["sourceModifiedUnixSeconds"],
                    payload["text"],
                    json.dumps(payload["tags"]),
                    payload["source"],
                    payload["fileName"],
                    source_id,
                    payload.get("contentHash", doc_id),
                    int(payload.get("version", 1)),
                    False,
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

        conn = self._get_conn()
        try:
            _logger.info(
                "pg upsert start: doc_id=%s… chunks=%s (batch page_size=%s)",
                doc_id[:16],
                n,
                _PG_UPSERT_PAGE_SIZE,
            )
            with conn.cursor() as cur:
                try:
                    cur.execute("SET LOCAL statement_timeout = '600s'")
                except Exception:
                    _logger.debug("SET LOCAL statement_timeout nicht gesetzt", exc_info=True)
                cur.execute(f"DELETE FROM {qualified} WHERE document_id = %s", (doc_id,))
                execute_batch(
                    cur,
                    sql,
                    rows,
                    page_size=_PG_UPSERT_PAGE_SIZE,
                )
                cur.execute(f"UPDATE {qualified} SET is_active = false WHERE source_id = %s", (source_id,))
                cur.execute(
                    f"UPDATE {qualified} SET is_active = true WHERE source_id = %s AND document_id = %s",
                    (source_id, doc_id),
                )
            conn.commit()
            _logger.info("pg upsert fertig: doc_id=%s… rows=%s", doc_id[:16], n)
        except Exception:
            conn.rollback()
            _logger.exception("pg upsert fehlgeschlagen doc_id=%s", doc_id[:16])
            raise
        finally:
            self._put_conn(conn)

    def activate_source_version(self, table_name: str, source_id: str, doc_id: str) -> None:
        qualified = self._qualified_table(table_name)
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT count(*) FROM {qualified} WHERE source_id = %s AND document_id = %s",
                    (source_id, doc_id),
                )
                if int(cur.fetchone()[0]) == 0:
                    raise ValueError(f"Keine Vektoren fuer Source-Version {source_id}/{doc_id}")
                cur.execute(f"UPDATE {qualified} SET is_active = false WHERE source_id = %s", (source_id,))
                cur.execute(
                    f"UPDATE {qualified} SET is_active = true WHERE source_id = %s AND document_id = %s",
                    (source_id, doc_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def cleanup_inactive_versions(self, table_name: str, source_id: str | None = None) -> int:
        qualified = self._qualified_table(table_name)
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                if source_id is None:
                    cur.execute(f"DELETE FROM {qualified} WHERE is_active = false")
                else:
                    cur.execute(
                        f"DELETE FROM {qualified} WHERE is_active = false AND source_id = %s",
                        (source_id,),
                    )
                count = int(cur.rowcount or 0)
            conn.commit()
            return count
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def similarity_search(
        self,
        table_name: str,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        qualified = self._qualified_table(table_name)
        vector_literal = f"[{','.join(str(v) for v in query_vector)}]"
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""SELECT text_content, document_id, file_name, chunk_index, source_path, source,
                               1 - (embedding <=> %s::vector) AS similarity,
                               category, instrument, authority, document_status, section, heading_path,
                               parent_section, previous_section, next_section, content_types, source_id, canonical_location, corpus_version
                        FROM {qualified}
                        WHERE is_active = true
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s""",
                    (vector_literal, vector_literal, top_k),
                )
                rows = cur.fetchall()
            return [
                {
                    "text": row[0],
                    "documentId": row[1],
                    "fileName": row[2],
                    "chunkIndex": row[3],
                    "sourcePath": row[4],
                    "source": row[5],
                    "similarity": float(row[6]),
                    "category": row[7],
                    "instrument": row[8],
                    "authority": row[9],
                    "status": row[10],
                    "section": row[11],
                    "headingPath": row[12],
                    "parentSection": row[13],
                    "previousSection": row[14],
                    "nextSection": row[15],
                    "contentTypes": row[16],
                    "sourceId": row[17],
                    "canonicalLocation": row[18],
                    "corpusVersion": row[19],
                }
                for row in rows
            ]
        finally:
            self._put_conn(conn)

    def search_by_filename(
        self,
        table_name: str,
        pattern: str,
        query_vector: list[float],
        top_k: int = 2,
    ) -> list[dict]:
        """Return top_k chunks whose file_name contains pattern (case-insensitive), ordered by similarity."""
        qualified = self._qualified_table(table_name)
        vector_literal = f"[{','.join(str(v) for v in query_vector)}]"
        like_pattern = f"%{pattern.lower()}%"
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""SELECT text_content, document_id, file_name, chunk_index, source_path, source,
                               1 - (embedding <=> %s::vector) AS similarity,
                               category, instrument, authority, document_status, section, heading_path,
                               parent_section, previous_section, next_section, content_types, source_id, canonical_location, corpus_version
                        FROM {qualified}
                        WHERE is_active = true AND lower(file_name) LIKE %s
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s""",
                    (vector_literal, like_pattern, vector_literal, max(1, top_k)),
                )
                rows = cur.fetchall()
            return [
                {
                    "text": row[0],
                    "documentId": row[1],
                    "fileName": row[2],
                    "chunkIndex": row[3],
                    "sourcePath": row[4],
                    "source": row[5],
                    "similarity": float(row[6]),
                    "category": row[7],
                    "instrument": row[8],
                    "authority": row[9],
                    "status": row[10],
                    "section": row[11],
                    "headingPath": row[12],
                    "parentSection": row[13],
                    "previousSection": row[14],
                    "nextSection": row[15],
                    "contentTypes": row[16],
                    "sourceId": row[17],
                    "canonicalLocation": row[18],
                    "corpusVersion": row[19],
                }
                for row in rows
            ]
        finally:
            self._put_conn(conn)

    def _get_conn(self):
        if not self._pool:
            self._try_create_pool()
        if not self._pool:
            raise ConnectionError("Keine Postgres-Verbindung verfuegbar.")
        return self._pool.getconn()

    def _put_conn(self, conn) -> None:
        if self._pool:
            self._pool.putconn(conn)
