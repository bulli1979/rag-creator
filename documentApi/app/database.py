from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from .models import DocumentRecord, DocumentStatus, JobRecord, JobStatus, JobType


def _parse_tags(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return [str(entry) for entry in parsed] if isinstance(parsed, list) else []
    except Exception:
        return []


def _row_to_document(row: sqlite3.Row) -> DocumentRecord:
    return DocumentRecord(
        docId=row["docId"],
        fileName=row["fileName"],
        filePath=row["filePath"],
        fileHash=row["fileHash"],
        fileType=row["fileType"],
        createdAt=row["createdAt"],
        updatedAt=row["updatedAt"],
        status=row["status"],
        errorMessage=row["errorMessage"],
        chunkCount=row["chunkCount"],
        tags=_parse_tags(row["tags"]),
        source=row["source"] or "",
        corpusPath=row["corpusPath"],
        lastIndexedAt=row["lastIndexedAt"],
        sizeBytes=row["sizeBytes"] or 0,
        sourceId=row["sourceId"] or "",
        contentHash=row["contentHash"] or row["fileHash"],
        version=row["version"] or 1,
        isActive=bool(row["isActive"]),
        canonicalLocation=row["canonicalLocation"] or "",
        corpusVersion=row["corpusVersion"] or "",
    )


def _row_to_job(row: sqlite3.Row) -> JobRecord:
    return JobRecord(
        jobId=row["jobId"],
        docId=row["docId"],
        type=row["type"],
        status=row["status"],
        progress=row["progress"],
        createdAt=row["createdAt"],
        updatedAt=row["updatedAt"],
        message=row["message"] or "",
    )


class IndexDatabase:
    def __init__(self, database_path: Path) -> None:
        self._conn = sqlite3.connect(str(database_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                docId TEXT PRIMARY KEY,
                environmentId TEXT NOT NULL DEFAULT 'default',
                fileName TEXT NOT NULL,
                filePath TEXT NOT NULL,
                fileHash TEXT NOT NULL,
                fileType TEXT NOT NULL,
                createdAt INTEGER NOT NULL,
                updatedAt INTEGER NOT NULL,
                status TEXT NOT NULL,
                errorMessage TEXT,
                chunkCount INTEGER NOT NULL DEFAULT 0,
                tags TEXT NOT NULL DEFAULT '[]',
                source TEXT NOT NULL DEFAULT '',
                corpusPath TEXT NOT NULL,
                lastIndexedAt INTEGER,
                sizeBytes INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS jobs (
                jobId TEXT PRIMARY KEY,
                docId TEXT NOT NULL,
                environmentId TEXT NOT NULL DEFAULT 'default',
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                progress REAL NOT NULL,
                createdAt INTEGER NOT NULL,
                updatedAt INTEGER NOT NULL,
                message TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(docId) REFERENCES documents(docId) ON DELETE CASCADE
            );
            """
        )
        self._ensure_column("documents", "environmentId", "TEXT NOT NULL DEFAULT 'default'")
        self._ensure_column("documents", "sourceId", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("documents", "contentHash", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("documents", "version", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column("documents", "isActive", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column("documents", "canonicalLocation", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("documents", "corpusVersion", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("jobs", "environmentId", "TEXT NOT NULL DEFAULT 'default'")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_documents_env_updated ON documents(environmentId, updatedAt DESC)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_env_updated ON jobs(environmentId, updatedAt DESC)"
        )
        self._conn.execute("UPDATE documents SET sourceId = 'legacy:' || docId WHERE sourceId = ''")
        self._conn.execute("UPDATE documents SET contentHash = fileHash WHERE contentHash = ''")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_documents_env_source ON documents(environmentId, sourceId, version DESC)"
        )
        self._conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_one_active_source "
            "ON documents(environmentId, sourceId) WHERE isActive = 1"
        )
        self._conn.commit()

    def _ensure_column(self, table: str, column: str, ddl: str) -> None:
        cols = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        if any(str(c["name"]) == column for c in cols):
            return
        self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def upsert_document(
        self,
        *,
        environment_id: str,
        doc_id: str,
        file_name: str,
        file_path: str,
        file_hash: str,
        file_type: str,
        status: DocumentStatus,
        tags: list[str],
        source: str,
        corpus_path: str,
        size_bytes: int,
        source_id: str,
        content_hash: str,
        version: int,
        is_active: bool,
        canonical_location: str,
        corpus_version: str,
    ) -> None:
        now = int(time.time() * 1000)
        self._conn.execute(
            """
            INSERT INTO documents (
                docId, environmentId, fileName, filePath, fileHash, fileType, createdAt, updatedAt,
                status, tags, source, corpusPath, sizeBytes, sourceId, contentHash,
                version, isActive, canonicalLocation, corpusVersion
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(docId) DO UPDATE SET
                environmentId=excluded.environmentId,
                fileName=excluded.fileName,
                filePath=excluded.filePath,
                fileHash=excluded.fileHash,
                fileType=excluded.fileType,
                updatedAt=excluded.updatedAt,
                status=excluded.status,
                tags=excluded.tags,
                source=excluded.source,
                corpusPath=excluded.corpusPath,
                sizeBytes=excluded.sizeBytes,
                sourceId=excluded.sourceId,
                contentHash=excluded.contentHash,
                version=excluded.version,
                isActive=excluded.isActive,
                canonicalLocation=excluded.canonicalLocation,
                corpusVersion=excluded.corpusVersion
            """,
            (
                doc_id, environment_id, file_name, file_path, file_hash, file_type,
                now, now, status.value, json.dumps(tags), source,
                corpus_path, size_bytes, source_id, content_hash, version,
                int(is_active), canonical_location, corpus_version,
            ),
        )
        self._conn.commit()

    def set_document_status(
        self, doc_id: str, status: DocumentStatus, error_message: str | None = None
    ) -> None:
        now = int(time.time() * 1000)
        self._conn.execute(
            "UPDATE documents SET status = ?, errorMessage = ?, updatedAt = ? WHERE docId = ?",
            (status.value, error_message, now, doc_id),
        )
        self._conn.commit()

    def set_document_index_result(self, doc_id: str, chunk_count: int) -> None:
        now = int(time.time() * 1000)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._conn.execute(
                "SELECT environmentId, sourceId FROM documents WHERE docId = ?", (doc_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Dokument nicht gefunden: {doc_id}")
            self._conn.execute(
                "UPDATE documents SET isActive = 0 WHERE environmentId = ? AND sourceId = ? AND docId <> ?",
                (row["environmentId"], row["sourceId"], doc_id),
            )
            self._conn.execute(
                """UPDATE documents SET chunkCount = ?, status = 'done', errorMessage = NULL,
                   isActive = 1, lastIndexedAt = ?, updatedAt = ? WHERE docId = ?""",
                (chunk_count, now, now, doc_id),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def get_active_document_by_source(self, source_id: str, environment_id: str) -> DocumentRecord | None:
        row = self._conn.execute(
            "SELECT * FROM documents WHERE environmentId = ? AND sourceId = ? AND isActive = 1",
            (environment_id, source_id),
        ).fetchone()
        return _row_to_document(row) if row else None

    def next_source_version(self, source_id: str, environment_id: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS nextVersion FROM documents WHERE environmentId = ? AND sourceId = ?",
            (environment_id, source_id),
        ).fetchone()
        return int(row["nextVersion"])

    def list_documents(self, environment_id: str) -> list[DocumentRecord]:
        rows = self._conn.execute(
            "SELECT * FROM documents WHERE environmentId = ? ORDER BY updatedAt DESC",
            (environment_id,),
        ).fetchall()
        return [_row_to_document(row) for row in rows]

    def get_document(self, doc_id: str, environment_id: str | None = None) -> DocumentRecord | None:
        if environment_id is None:
            row = self._conn.execute(
                "SELECT * FROM documents WHERE docId = ?", (doc_id,)
            ).fetchone()
            return _row_to_document(row) if row else None
        row = self._conn.execute(
            "SELECT * FROM documents WHERE docId = ? AND environmentId = ?",
            (doc_id, environment_id),
        ).fetchone()
        return _row_to_document(row) if row else None

    def delete_document(self, doc_id: str) -> None:
        self._conn.execute("DELETE FROM documents WHERE docId = ?", (doc_id,))
        self._conn.commit()

    def upsert_job(
        self,
        *,
        environment_id: str,
        job_id: str,
        doc_id: str,
        job_type: JobType,
        status: JobStatus,
        progress: float,
        message: str,
    ) -> None:
        now = int(time.time() * 1000)
        self._conn.execute(
            """
            INSERT INTO jobs (jobId, docId, environmentId, type, status, progress, createdAt, updatedAt, message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(jobId) DO UPDATE SET
                environmentId=excluded.environmentId,
                status=excluded.status,
                progress=excluded.progress,
                updatedAt=excluded.updatedAt,
                message=excluded.message
            """,
            (job_id, doc_id, environment_id, job_type.value, status.value, progress, now, now, message),
        )
        self._conn.commit()

    def list_jobs(self, environment_id: str) -> list[JobRecord]:
        rows = self._conn.execute(
            "SELECT * FROM jobs WHERE environmentId = ? ORDER BY updatedAt DESC LIMIT 200",
            (environment_id,),
        ).fetchall()
        return [_row_to_job(row) for row in rows]

    def list_doc_ids_by_status(self, status: str, environment_id: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT docId FROM documents WHERE status = ? AND environmentId = ? ORDER BY updatedAt ASC",
            (status, environment_id),
        ).fetchall()
        return [str(r["docId"]) for r in rows]

    def recover_after_api_restart(self, environment_id: str) -> tuple[int, int]:
        """
        Nach Prozess-Neustart: es laeuft kein Worker mehr.
        - processing -> queued (wird wieder eingeplant)
        - alte Jobs queued/running -> error (werden durch neue Jobs ersetzt)
        """
        now = int(time.time() * 1000)
        cur_docs = self._conn.execute(
            """
            UPDATE documents
            SET status = 'queued', errorMessage = NULL, updatedAt = ?
            WHERE status = 'processing' AND environmentId = ?
            """,
            (now, environment_id),
        )
        cur_jobs = self._conn.execute(
            """
            UPDATE jobs
            SET status = 'error',
                message = ?,
                progress = 1.0,
                updatedAt = ?
            WHERE status IN ('queued', 'running') AND environmentId = ?
            """,
            ("Unterbrochen (API-Neustart — wird neu eingeplant).", now, environment_id),
        )
        self._conn.commit()
        return (int(cur_docs.rowcount or 0), int(cur_jobs.rowcount or 0))
