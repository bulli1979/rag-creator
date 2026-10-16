from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .models import (
    ApiKeyRecord,
    AdminWebClient,
    AdminWebConnection,
    AdminWebEvent,
    AdminWebPreference,
    ChatFeedbackRecord,
    ChatRequestRecord,
    DocumentRecord,
    DocumentStatus,
    JobRecord,
    JobStatus,
    JobType,
)


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


def _row_to_api_key(row: sqlite3.Row) -> ApiKeyRecord:
    return ApiKeyRecord(
        keyId=row["keyId"],
        label=row["label"] or "",
        isAdmin=bool(int(row["isAdmin"] or 0)),
        createdAt=row["createdAt"],
        lastUsedAt=row["lastUsedAt"],
        revokedAt=row["revokedAt"],
    )


def _row_to_chat_feedback(row: sqlite3.Row) -> ChatFeedbackRecord:
    helpful_raw = row["helpful"]
    helpful = None if helpful_raw is None else bool(int(helpful_raw))
    return ChatFeedbackRecord(
        feedbackId=row["feedbackId"],
        requestId=row["requestId"],
        helpful=helpful,
        rating=row["rating"],
        comment=row["comment"],
        createdAt=row["createdAt"],
    )


def _row_to_chat_request(row: sqlite3.Row, feedback: ChatFeedbackRecord | None = None) -> ChatRequestRecord:
    metrics_raw = row["metricsJson"] or "{}"
    try:
        metrics = json.loads(metrics_raw)
        if not isinstance(metrics, dict):
            metrics = {}
    except Exception:
        metrics = {}
    try:
        context_chunk_count = len(json.loads(row["contextSummaryJson"] or "[]"))
    except Exception:
        context_chunk_count = 0
    return ChatRequestRecord(
        requestId=row["requestId"],
        environmentId=row["environmentId"],
        message=row["message"],
        language=row["language"],
        answer=row["answer"],
        clientSource=row["clientSource"],
        status=row["status"],
        errorMessage=row["errorMessage"],
        llmModel=row["llmModel"],
        topK=row["topK"],
        contextChunkCount=context_chunk_count,
        metrics=metrics,
        createdAt=row["createdAt"],
        feedback=feedback,
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
                docId TEXT NOT NULL,
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
                sizeBytes INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (docId, environmentId)
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
                message TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS chat_requests (
                requestId TEXT PRIMARY KEY,
                environmentId TEXT NOT NULL DEFAULT 'default',
                message TEXT NOT NULL,
                historyJson TEXT NOT NULL DEFAULT '[]',
                language TEXT,
                answer TEXT,
                contextSummaryJson TEXT NOT NULL DEFAULT '[]',
                metricsJson TEXT NOT NULL DEFAULT '{}',
                llmModel TEXT,
                topK INTEGER,
                clientSource TEXT,
                status TEXT NOT NULL,
                errorMessage TEXT,
                elapsedMs INTEGER,
                createdAt INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_feedback (
                feedbackId TEXT PRIMARY KEY,
                requestId TEXT NOT NULL UNIQUE,
                helpful INTEGER,
                rating INTEGER,
                comment TEXT,
                createdAt INTEGER NOT NULL,
                FOREIGN KEY(requestId) REFERENCES chat_requests(requestId) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                keyId TEXT PRIMARY KEY,
                keyHash TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL DEFAULT '',
                isAdmin INTEGER NOT NULL DEFAULT 0,
                createdAt INTEGER NOT NULL,
                lastUsedAt INTEGER,
                revokedAt INTEGER
            );

            CREATE TABLE IF NOT EXISTS admin_web_clients (
                clientId TEXT PRIMARY KEY,
                label TEXT NOT NULL DEFAULT '',
                userAgent TEXT,
                createdAt INTEGER NOT NULL,
                lastSeenAt INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_web_connections (
                connectionId TEXT PRIMARY KEY,
                clientId TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT 'default',
                apiBaseUrl TEXT NOT NULL,
                apiKey TEXT NOT NULL,
                isDefault INTEGER NOT NULL DEFAULT 0,
                createdAt INTEGER NOT NULL,
                updatedAt INTEGER NOT NULL,
                FOREIGN KEY(clientId) REFERENCES admin_web_clients(clientId) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS admin_web_preferences (
                clientId TEXT NOT NULL,
                prefKey TEXT NOT NULL,
                prefValueJson TEXT NOT NULL DEFAULT 'null',
                updatedAt INTEGER NOT NULL,
                PRIMARY KEY (clientId, prefKey),
                FOREIGN KEY(clientId) REFERENCES admin_web_clients(clientId) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS admin_web_events (
                eventId TEXT PRIMARY KEY,
                clientId TEXT,
                eventType TEXT NOT NULL,
                payloadJson TEXT,
                createdAt INTEGER NOT NULL,
                FOREIGN KEY(clientId) REFERENCES admin_web_clients(clientId) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS batch_test_settings (
                settingsId TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                chatSettingsJson TEXT NOT NULL DEFAULT '{}',
                evalJudgeJson TEXT NOT NULL DEFAULT '{}',
                createdAt INTEGER NOT NULL,
                updatedAt INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS batch_test_runs (
                runId TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                fileName TEXT NOT NULL DEFAULT '',
                evaluateAnswers INTEGER NOT NULL DEFAULT 0,
                language TEXT,
                total INTEGER NOT NULL DEFAULT 0,
                current INTEGER NOT NULL DEFAULT 0,
                progress INTEGER NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                llmModel TEXT NOT NULL DEFAULT '',
                environmentId TEXT NOT NULL DEFAULT '',
                environmentName TEXT NOT NULL DEFAULT '',
                settingsId TEXT,
                settingsName TEXT NOT NULL DEFAULT '',
                settingsSnapshotJson TEXT NOT NULL DEFAULT '{}',
                summaryJson TEXT NOT NULL DEFAULT '{}',
                resultsJson TEXT NOT NULL DEFAULT '[]',
                createdAt TEXT NOT NULL,
                finishedAt TEXT,
                updatedAt INTEGER NOT NULL
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
        self._migrate_documents_composite_pk()
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_documents_env_updated ON documents(environmentId, updatedAt DESC)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_env_updated ON jobs(environmentId, updatedAt DESC)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_requests_env_created ON chat_requests(environmentId, createdAt DESC)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_admin_web_connections_client ON admin_web_connections(clientId, updatedAt DESC)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_admin_web_events_created ON admin_web_events(createdAt DESC)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_batch_test_runs_created ON batch_test_runs(createdAt DESC)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_batch_test_settings_updated ON batch_test_settings(updatedAt DESC)"
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

    def _migrate_documents_composite_pk(self) -> None:
        """docId allein als PK → (docId, environmentId), damit dieselbe Datei in mehreren Envs existieren kann."""
        pk_cols = [
            str(r["name"])
            for r in self._conn.execute("PRAGMA table_info(documents)").fetchall()
            if int(r["pk"] or 0) > 0
        ]
        pk_cols_sorted = sorted(pk_cols, key=lambda n: next(
            int(r["pk"]) for r in self._conn.execute("PRAGMA table_info(documents)").fetchall() if str(r["name"]) == n
        ))
        if pk_cols_sorted == ["docId", "environmentId"]:
            return
        if set(pk_cols) == {"docId", "environmentId"}:
            return

        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents_v2 (
                docId TEXT NOT NULL,
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
                sizeBytes INTEGER NOT NULL DEFAULT 0,
                sourceId TEXT NOT NULL DEFAULT '',
                contentHash TEXT NOT NULL DEFAULT '',
                version INTEGER NOT NULL DEFAULT 1,
                isActive INTEGER NOT NULL DEFAULT 1,
                canonicalLocation TEXT NOT NULL DEFAULT '',
                corpusVersion TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (docId, environmentId)
            );
            INSERT OR IGNORE INTO documents_v2 (
                docId, environmentId, fileName, filePath, fileHash, fileType,
                createdAt, updatedAt, status, errorMessage, chunkCount, tags, source,
                corpusPath, lastIndexedAt, sizeBytes,
                sourceId, contentHash, version, isActive, canonicalLocation, corpusVersion
            )
            SELECT
                docId, COALESCE(NULLIF(environmentId, ''), 'default'), fileName, filePath, fileHash, fileType,
                createdAt, updatedAt, status, errorMessage, chunkCount, tags, source,
                corpusPath, lastIndexedAt, sizeBytes,
                sourceId, contentHash, version, isActive, canonicalLocation, corpusVersion
            FROM documents;
            DROP TABLE documents;
            ALTER TABLE documents_v2 RENAME TO documents;
            """
        )
        self._conn.commit()

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
            ON CONFLICT(docId, environmentId) DO UPDATE SET
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
        self,
        doc_id: str,
        status: DocumentStatus,
        error_message: str | None = None,
        *,
        environment_id: str | None = None,
    ) -> None:
        now = int(time.time() * 1000)
        if environment_id:
            self._conn.execute(
                "UPDATE documents SET status = ?, errorMessage = ?, updatedAt = ? WHERE docId = ? AND environmentId = ?",
                (status.value, error_message, now, doc_id, environment_id),
            )
        else:
            self._conn.execute(
                "UPDATE documents SET status = ?, errorMessage = ?, updatedAt = ? WHERE docId = ?",
                (status.value, error_message, now, doc_id),
            )
        self._conn.commit()

    def set_document_index_result(
        self, doc_id: str, chunk_count: int, *, environment_id: str | None = None
    ) -> None:
        now = int(time.time() * 1000)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            if environment_id:
                row = self._conn.execute(
                    "SELECT environmentId, sourceId FROM documents WHERE docId = ? AND environmentId = ?",
                    (doc_id, environment_id),
                ).fetchone()
            else:
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
                   isActive = 1, lastIndexedAt = ?, updatedAt = ? WHERE docId = ? AND environmentId = ?""",
                (chunk_count, now, now, doc_id, row["environmentId"]),
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

    def count_document_envs(self, doc_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM documents WHERE docId = ?", (doc_id,)
        ).fetchone()
        return int(row["c"] if row else 0)

    def delete_document(self, doc_id: str, environment_id: str | None = None) -> None:
        if environment_id:
            self._conn.execute(
                "DELETE FROM documents WHERE docId = ? AND environmentId = ?",
                (doc_id, environment_id),
            )
        else:
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

    def insert_chat_request(
        self,
        *,
        request_id: str,
        environment_id: str,
        message: str,
        history_json: str,
        language: str | None,
        answer: str | None,
        context_summary_json: str,
        metrics_json: str,
        llm_model: str | None,
        top_k: int | None,
        client_source: str | None,
        status: str,
        error_message: str | None,
        elapsed_ms: int | None,
    ) -> None:
        now = int(time.time() * 1000)
        self._conn.execute(
            """
            INSERT INTO chat_requests (
                requestId, environmentId, message, historyJson, language, answer,
                contextSummaryJson, metricsJson, llmModel, topK, clientSource,
                status, errorMessage, elapsedMs, createdAt
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                environment_id,
                message,
                history_json,
                language,
                answer,
                context_summary_json,
                metrics_json,
                llm_model,
                top_k,
                client_source,
                status,
                error_message,
                elapsed_ms,
                now,
            ),
        )
        self._conn.commit()

    def get_chat_request(self, request_id: str) -> ChatRequestRecord | None:
        row = self._conn.execute(
            "SELECT * FROM chat_requests WHERE requestId = ?",
            (request_id,),
        ).fetchone()
        if not row:
            return None
        fb_row = self._conn.execute(
            "SELECT * FROM chat_feedback WHERE requestId = ?",
            (request_id,),
        ).fetchone()
        feedback = _row_to_chat_feedback(fb_row) if fb_row else None
        return _row_to_chat_request(row, feedback)

    def list_chat_requests(
        self,
        *,
        environment_id: str | None = None,
        limit: int = 100,
    ) -> list[ChatRequestRecord]:
        limit = max(1, min(limit, 500))
        if environment_id:
            rows = self._conn.execute(
                """
                SELECT * FROM chat_requests
                WHERE environmentId = ?
                ORDER BY createdAt DESC
                LIMIT ?
                """,
                (environment_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM chat_requests
                ORDER BY createdAt DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        results: list[ChatRequestRecord] = []
        for row in rows:
            fb_row = self._conn.execute(
                "SELECT * FROM chat_feedback WHERE requestId = ?",
                (row["requestId"],),
            ).fetchone()
            feedback = _row_to_chat_feedback(fb_row) if fb_row else None
            results.append(_row_to_chat_request(row, feedback))
        return results

    def upsert_chat_feedback(
        self,
        *,
        feedback_id: str,
        request_id: str,
        helpful: bool | None,
        rating: int | None,
        comment: str | None,
    ) -> ChatFeedbackRecord:
        now = int(time.time() * 1000)
        helpful_val = None if helpful is None else int(helpful)
        self._conn.execute(
            """
            INSERT INTO chat_feedback (feedbackId, requestId, helpful, rating, comment, createdAt)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(requestId) DO UPDATE SET
                helpful=excluded.helpful,
                rating=excluded.rating,
                comment=excluded.comment,
                createdAt=excluded.createdAt
            """,
            (feedback_id, request_id, helpful_val, rating, comment, now),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM chat_feedback WHERE requestId = ?",
            (request_id,),
        ).fetchone()
        if not row:
            raise RuntimeError("Feedback konnte nicht gespeichert werden.")
        return _row_to_chat_feedback(row)

    def count_active_api_keys(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM api_keys WHERE revokedAt IS NULL"
        ).fetchone()
        return int(row["c"] if row else 0)

    def insert_api_key(
        self,
        *,
        key_id: str,
        key_hash: str,
        label: str,
        is_admin: bool,
    ) -> None:
        now = int(time.time() * 1000)
        self._conn.execute(
            """
            INSERT INTO api_keys (keyId, keyHash, label, isAdmin, createdAt)
            VALUES (?, ?, ?, ?, ?)
            """,
            (key_id, key_hash, label, int(is_admin), now),
        )
        self._conn.commit()

    def get_api_key_by_hash(self, key_hash: str) -> ApiKeyRecord | None:
        row = self._conn.execute(
            "SELECT * FROM api_keys WHERE keyHash = ?",
            (key_hash,),
        ).fetchone()
        return _row_to_api_key(row) if row else None

    def touch_api_key_last_used(self, key_id: str) -> None:
        now = int(time.time() * 1000)
        self._conn.execute(
            "UPDATE api_keys SET lastUsedAt = ? WHERE keyId = ?",
            (now, key_id),
        )
        self._conn.commit()

    def list_api_keys(self) -> list[ApiKeyRecord]:
        rows = self._conn.execute(
            "SELECT * FROM api_keys ORDER BY createdAt DESC"
        ).fetchall()
        return [_row_to_api_key(row) for row in rows]

    def revoke_api_key(self, key_id: str) -> bool:
        now = int(time.time() * 1000)
        cur = self._conn.execute(
            """
            UPDATE api_keys SET revokedAt = ?
            WHERE keyId = ? AND revokedAt IS NULL
            """,
            (now, key_id),
        )
        self._conn.commit()
        return int(cur.rowcount or 0) > 0

    # --- Admin-Web Persistenz ---

    def upsert_admin_web_client(
        self,
        *,
        client_id: str,
        label: str = "",
        user_agent: str | None = None,
    ) -> AdminWebClient:
        now = int(time.time() * 1000)
        existing = self._conn.execute(
            "SELECT * FROM admin_web_clients WHERE clientId = ?",
            (client_id,),
        ).fetchone()
        if existing:
            self._conn.execute(
                """
                UPDATE admin_web_clients
                SET label = ?, userAgent = COALESCE(?, userAgent), lastSeenAt = ?
                WHERE clientId = ?
                """,
                (label or existing["label"] or "", user_agent, now, client_id),
            )
        else:
            self._conn.execute(
                """
                INSERT INTO admin_web_clients (clientId, label, userAgent, createdAt, lastSeenAt)
                VALUES (?, ?, ?, ?, ?)
                """,
                (client_id, label or "", user_agent, now, now),
            )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM admin_web_clients WHERE clientId = ?",
            (client_id,),
        ).fetchone()
        assert row is not None
        return AdminWebClient(
            clientId=row["clientId"],
            label=row["label"] or "",
            userAgent=row["userAgent"],
            createdAt=row["createdAt"],
            lastSeenAt=row["lastSeenAt"],
        )

    def get_admin_web_client(self, client_id: str) -> AdminWebClient | None:
        row = self._conn.execute(
            "SELECT * FROM admin_web_clients WHERE clientId = ?",
            (client_id,),
        ).fetchone()
        if not row:
            return None
        return AdminWebClient(
            clientId=row["clientId"],
            label=row["label"] or "",
            userAgent=row["userAgent"],
            createdAt=row["createdAt"],
            lastSeenAt=row["lastSeenAt"],
        )

    def list_admin_web_connections(self, client_id: str) -> list[AdminWebConnection]:
        rows = self._conn.execute(
            """
            SELECT * FROM admin_web_connections
            WHERE clientId = ?
            ORDER BY isDefault DESC, updatedAt DESC
            """,
            (client_id,),
        ).fetchall()
        return [
            AdminWebConnection(
                connectionId=row["connectionId"],
                clientId=row["clientId"],
                name=row["name"] or "default",
                apiBaseUrl=row["apiBaseUrl"],
                apiKey=row["apiKey"],
                isDefault=bool(int(row["isDefault"] or 0)),
                createdAt=row["createdAt"],
                updatedAt=row["updatedAt"],
            )
            for row in rows
        ]

    def upsert_admin_web_connection(
        self,
        *,
        connection_id: str,
        client_id: str,
        name: str,
        api_base_url: str,
        api_key: str,
        is_default: bool,
    ) -> AdminWebConnection:
        now = int(time.time() * 1000)
        if is_default:
            self._conn.execute(
                "UPDATE admin_web_connections SET isDefault = 0 WHERE clientId = ?",
                (client_id,),
            )
        existing = self._conn.execute(
            "SELECT createdAt FROM admin_web_connections WHERE connectionId = ?",
            (connection_id,),
        ).fetchone()
        created_at = int(existing["createdAt"]) if existing else now
        self._conn.execute(
            """
            INSERT INTO admin_web_connections (
                connectionId, clientId, name, apiBaseUrl, apiKey, isDefault, createdAt, updatedAt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(connectionId) DO UPDATE SET
                name=excluded.name,
                apiBaseUrl=excluded.apiBaseUrl,
                apiKey=excluded.apiKey,
                isDefault=excluded.isDefault,
                updatedAt=excluded.updatedAt
            """,
            (
                connection_id,
                client_id,
                name.strip() or "default",
                api_base_url.rstrip("/"),
                api_key,
                int(is_default),
                created_at,
                now,
            ),
        )
        self._conn.commit()
        rows = self.list_admin_web_connections(client_id)
        for row in rows:
            if row.connection_id == connection_id:
                return row
        raise RuntimeError("Admin-Web-Verbindung konnte nicht gespeichert werden.")

    def delete_admin_web_connection(self, connection_id: str, client_id: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM admin_web_connections WHERE connectionId = ? AND clientId = ?",
            (connection_id, client_id),
        )
        self._conn.commit()
        return int(cur.rowcount or 0) > 0

    def list_admin_web_preferences(self, client_id: str) -> list[AdminWebPreference]:
        rows = self._conn.execute(
            "SELECT * FROM admin_web_preferences WHERE clientId = ? ORDER BY prefKey",
            (client_id,),
        ).fetchall()
        result: list[AdminWebPreference] = []
        for row in rows:
            try:
                value = json.loads(row["prefValueJson"])
            except Exception:
                value = None
            result.append(
                AdminWebPreference(
                    clientId=row["clientId"],
                    prefKey=row["prefKey"],
                    prefValue=value,
                    updatedAt=row["updatedAt"],
                )
            )
        return result

    def upsert_admin_web_preference(
        self,
        *,
        client_id: str,
        pref_key: str,
        pref_value: object,
    ) -> AdminWebPreference:
        now = int(time.time() * 1000)
        key = pref_key.strip()
        if not key:
            raise ValueError("prefKey darf nicht leer sein.")
        self._conn.execute(
            """
            INSERT INTO admin_web_preferences (clientId, prefKey, prefValueJson, updatedAt)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(clientId, prefKey) DO UPDATE SET
                prefValueJson=excluded.prefValueJson,
                updatedAt=excluded.updatedAt
            """,
            (client_id, key, json.dumps(pref_value, ensure_ascii=False), now),
        )
        self._conn.commit()
        return AdminWebPreference(
            clientId=client_id,
            prefKey=key,
            prefValue=pref_value,  # type: ignore[arg-type]
            updatedAt=now,
        )

    def insert_admin_web_event(
        self,
        *,
        event_id: str,
        client_id: str | None,
        event_type: str,
        payload: dict | None,
    ) -> AdminWebEvent:
        now = int(time.time() * 1000)
        self._conn.execute(
            """
            INSERT INTO admin_web_events (eventId, clientId, eventType, payloadJson, createdAt)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event_id,
                client_id,
                event_type.strip() or "unknown",
                json.dumps(payload, ensure_ascii=False) if payload is not None else None,
                now,
            ),
        )
        self._conn.commit()
        return AdminWebEvent(
            eventId=event_id,
            clientId=client_id,
            eventType=event_type.strip() or "unknown",
            payload=payload,
            createdAt=now,
        )

    def list_admin_web_events(
        self,
        *,
        client_id: str | None = None,
        limit: int = 100,
    ) -> list[AdminWebEvent]:
        limit = max(1, min(int(limit), 500))
        if client_id:
            rows = self._conn.execute(
                """
                SELECT * FROM admin_web_events
                WHERE clientId = ?
                ORDER BY createdAt DESC
                LIMIT ?
                """,
                (client_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM admin_web_events
                ORDER BY createdAt DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result: list[AdminWebEvent] = []
        for row in rows:
            payload = None
            if row["payloadJson"]:
                try:
                    parsed = json.loads(row["payloadJson"])
                    payload = parsed if isinstance(parsed, dict) else {"value": parsed}
                except Exception:
                    payload = None
            result.append(
                AdminWebEvent(
                    eventId=row["eventId"],
                    clientId=row["clientId"],
                    eventType=row["eventType"],
                    payload=payload,
                    createdAt=row["createdAt"],
                )
            )
        return result

    # —— Bulk / Batch-Test Persistenz ——

    def upsert_batch_test_settings(
        self,
        *,
        settings_id: str,
        name: str,
        chat_settings: dict[str, Any],
        eval_judge: dict[str, Any],
    ) -> dict[str, Any]:
        now = int(time.time() * 1000)
        existing = self._conn.execute(
            "SELECT createdAt FROM batch_test_settings WHERE settingsId = ?",
            (settings_id,),
        ).fetchone()
        created = int(existing["createdAt"]) if existing else now
        self._conn.execute(
            """
            INSERT INTO batch_test_settings (
                settingsId, name, chatSettingsJson, evalJudgeJson, createdAt, updatedAt
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(settingsId) DO UPDATE SET
                name = excluded.name,
                chatSettingsJson = excluded.chatSettingsJson,
                evalJudgeJson = excluded.evalJudgeJson,
                updatedAt = excluded.updatedAt
            """,
            (
                settings_id,
                name.strip() or "Unbenannt",
                json.dumps(chat_settings, ensure_ascii=False),
                json.dumps(eval_judge, ensure_ascii=False),
                created,
                now,
            ),
        )
        self._conn.commit()
        row = self.get_batch_test_settings(settings_id)
        assert row is not None
        return row

    def get_batch_test_settings(self, settings_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM batch_test_settings WHERE settingsId = ?",
            (settings_id,),
        ).fetchone()
        return None if row is None else self._batch_settings_row(row)

    def list_batch_test_settings(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM batch_test_settings ORDER BY updatedAt DESC"
        ).fetchall()
        return [self._batch_settings_row(r) for r in rows]

    def delete_batch_test_settings(self, settings_id: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM batch_test_settings WHERE settingsId = ?",
            (settings_id,),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def _batch_settings_row(self, row: sqlite3.Row) -> dict[str, Any]:
        try:
            chat = json.loads(row["chatSettingsJson"] or "{}")
        except Exception:
            chat = {}
        try:
            judge = json.loads(row["evalJudgeJson"] or "{}")
        except Exception:
            judge = {}
        return {
            "settingsId": row["settingsId"],
            "name": row["name"],
            "chatSettings": chat if isinstance(chat, dict) else {},
            "evalJudge": judge if isinstance(judge, dict) else {},
            "createdAt": row["createdAt"],
            "updatedAt": row["updatedAt"],
        }

    def upsert_batch_test_run(self, payload: dict[str, Any]) -> None:
        now = int(time.time() * 1000)
        self._conn.execute(
            """
            INSERT INTO batch_test_runs (
                runId, status, fileName, evaluateAnswers, language,
                total, current, progress, message, error,
                llmModel, environmentId, environmentName,
                settingsId, settingsName, settingsSnapshotJson,
                summaryJson, resultsJson, createdAt, finishedAt, updatedAt
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            ON CONFLICT(runId) DO UPDATE SET
                status = excluded.status,
                fileName = excluded.fileName,
                evaluateAnswers = excluded.evaluateAnswers,
                language = excluded.language,
                total = excluded.total,
                current = excluded.current,
                progress = excluded.progress,
                message = excluded.message,
                error = excluded.error,
                llmModel = excluded.llmModel,
                environmentId = excluded.environmentId,
                environmentName = excluded.environmentName,
                settingsId = excluded.settingsId,
                settingsName = excluded.settingsName,
                settingsSnapshotJson = excluded.settingsSnapshotJson,
                summaryJson = excluded.summaryJson,
                resultsJson = excluded.resultsJson,
                finishedAt = excluded.finishedAt,
                updatedAt = excluded.updatedAt
            """,
            (
                payload["runId"],
                payload.get("status", "queued"),
                payload.get("fileName", ""),
                1 if payload.get("evaluateAnswers") else 0,
                payload.get("language"),
                int(payload.get("total") or 0),
                int(payload.get("current") or 0),
                int(payload.get("progress") or 0),
                payload.get("message") or "",
                payload.get("error") or "",
                payload.get("llmModel") or "",
                payload.get("environmentId") or "",
                payload.get("environmentName") or "",
                payload.get("settingsId"),
                payload.get("settingsName") or "",
                json.dumps(payload.get("settingsSnapshot") or {}, ensure_ascii=False),
                json.dumps(payload.get("summary") or {}, ensure_ascii=False),
                json.dumps(payload.get("results") or [], ensure_ascii=False),
                payload.get("createdAt") or "",
                payload.get("finishedAt"),
                now,
            ),
        )
        self._conn.commit()

    def get_batch_test_run(self, run_id: str, *, include_results: bool = True) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM batch_test_runs WHERE runId = ?",
            (run_id,),
        ).fetchone()
        return None if row is None else self._batch_run_row(row, include_results=include_results)

    def list_batch_test_runs(
        self,
        *,
        limit: int = 50,
        sort_by: str = "createdAt",
        sort_dir: str = "desc",
    ) -> list[dict[str, Any]]:
        allowed = {
            "createdAt": "createdAt",
            "finishedAt": "finishedAt",
            "status": "status",
            "fileName": "fileName",
            "progress": "progress",
            "total": "total",
            "llmModel": "llmModel",
            "environmentName": "environmentName",
        }
        col = allowed.get(sort_by, "createdAt")
        direction = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
        rows = self._conn.execute(
            f"SELECT * FROM batch_test_runs ORDER BY {col} {direction} LIMIT ?",
            (max(1, min(limit, 200)),),
        ).fetchall()
        return [self._batch_run_row(r, include_results=False) for r in rows]

    def delete_batch_test_run(self, run_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM batch_test_runs WHERE runId = ?", (run_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def _batch_run_row(self, row: sqlite3.Row, *, include_results: bool) -> dict[str, Any]:
        try:
            summary = json.loads(row["summaryJson"] or "{}")
        except Exception:
            summary = {}
        try:
            snapshot = json.loads(row["settingsSnapshotJson"] or "{}")
        except Exception:
            snapshot = {}
        payload: dict[str, Any] = {
            "runId": row["runId"],
            "status": row["status"],
            "createdAt": row["createdAt"],
            "finishedAt": row["finishedAt"],
            "fileName": row["fileName"],
            "evaluateAnswers": bool(row["evaluateAnswers"]),
            "language": row["language"],
            "total": row["total"],
            "current": row["current"],
            "progress": row["progress"],
            "message": row["message"],
            "error": row["error"],
            "llmModel": row["llmModel"],
            "environmentId": row["environmentId"],
            "environmentName": row["environmentName"],
            "settingsId": row["settingsId"],
            "settingsName": row["settingsName"],
            "settingsSnapshot": snapshot if isinstance(snapshot, dict) else {},
            "summary": summary if isinstance(summary, dict) else {},
        }
        if include_results:
            try:
                results = json.loads(row["resultsJson"] or "[]")
            except Exception:
                results = []
            payload["results"] = results if isinstance(results, list) else []
        return payload
