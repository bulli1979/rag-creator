from __future__ import annotations

import asyncio
import csv
import logging
import io
import json
import re
import sys
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import _DEFAULT_SETTINGS, get_app_paths, load_settings, save_settings as persist_settings
from .database import IndexDatabase
from .file_store import FileStore, create_sha256
from .models import (
    AddDocumentsResult,
    AppSettings,
    DocumentRecord,
    DocumentStatus,
    JobRecord,
    JobStatus,
    JobType,
    PostgresEnvironment,
    ProgressEventPayload,
    UploadOptions,
)
from .services.thread_pool import run_in_worker_pool
from .services.folder_scan import iter_files_recursive
from .vector_store.factory import create_vector_store, resolve_qdrant_path, resolve_sqlite_path
from .vector_store.postgres_store import PostgresVectorStore
from .vector_store.protocol import VectorStore
from .worker import embed_texts, parse_document

_logger = logging.getLogger(__name__)

_SOURCE_LABEL_URL_RE = re.compile(
    r"(?:quelle|source|url)\s*:\s*(https?://[^\s<>'\"`]+|www\.[^\s<>'\"`]+)",
    re.IGNORECASE,
)


def _normalize_source_url(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().strip('"').strip("'")
    if not s:
        return None
    # Falls alte Werte wie .../index.md gespeichert wurden, fürs Öffnen strippen.
    s = re.sub(r"/index\.(?:md|html?|htm)$", "/", s, flags=re.IGNORECASE)
    return s


def _extract_source_url_from_chunk_text(text: str) -> str | None:
    t = text or ""
    m = _SOURCE_LABEL_URL_RE.search(t)
    if not m:
        return None
    return _normalize_source_url(m.group(1))


class IngestService:
    def __init__(
        self,
        database: IndexDatabase,
        file_store: FileStore,
        vector_service: VectorStore,
    ) -> None:
        self._db = database
        self._fs = file_store
        self._vs = vector_service
        self._queue: list[dict] = []
        self._is_processing = False
        self._is_db_validated = False
        # Bis initialize(): dieselben Defaults wie load_settings (leeres AppSettings() waere ungueltig).
        self._settings: AppSettings = _DEFAULT_SETTINGS.model_copy(deep=True)
        self._progress_subscribers: list[Callable[[ProgressEventPayload], None]] = []

    def _active_pg(self) -> PostgresEnvironment:
        return self._settings.get_active_postgres()

    def _active_environment_id(self) -> str:
        return self._settings.active_postgres_environment_id

    def _rebuild_vector_store(self) -> None:
        self._vs = create_vector_store(self._active_pg(), get_app_paths()["base"])

    def _sync_chat_vector_store(self) -> None:
        from .dependencies import get_chat_service

        try:
            get_chat_service().set_vector_store(self._vs)
        except RuntimeError:
            pass

    async def initialize(self) -> None:
        self._settings = load_settings()
        self._rebuild_vector_store()
        # In-Memory-Queue ist nach Neustart leer; SQLite kennt noch queued/processing.
        env_id = self._active_environment_id()
        n_reset, n_jobs = self._db.recover_after_api_restart(env_id)
        if n_reset or n_jobs:
            _logger.info(
                "startup recovery: %s Docs (processing->queued), %s alte Jobs abgebrochen",
                n_reset,
                n_jobs,
            )
        pending = self._db.list_doc_ids_by_status(DocumentStatus.queued.value, env_id)
        if pending:
            _logger.info(
                "startup: %s wartende Dokumente wieder in die Verarbeitungsqueue",
                len(pending),
            )
        for doc_id in pending:
            self._enqueue_job(doc_id, JobType.reindex)
        asyncio.get_event_loop().call_soon(
            lambda: asyncio.ensure_future(self._process_queue())
        )

    def subscribe_progress(
        self, handler: Callable[[ProgressEventPayload], None]
    ) -> Callable[[], None]:
        self._progress_subscribers.append(handler)

        def unsubscribe() -> None:
            self._progress_subscribers.remove(handler)

        return unsubscribe

    def list_documents(self) -> list[DocumentRecord]:
        return self._db.list_documents(self._active_environment_id())

    def list_jobs(self) -> list[JobRecord]:
        return self._db.list_jobs(self._active_environment_id())

    async def add_documents(
        self,
        files: list[tuple[str, bytes]],
        options: UploadOptions,
    ) -> AddDocumentsResult:
        self._ensure_db_validated()
        queued_ids: list[str] = []
        skipped_ids: list[str] = []
        messages: list[str] = []
        seen_hashes: set[str] = set()

        for file_name, content in files:
            try:
                doc_id = create_sha256(content)
                if doc_id in seen_hashes:
                    messages.append(
                        f"Duplikat im selben Upload uebersprungen: {file_name}"
                    )
                    skipped_ids.append(doc_id)
                    continue
                seen_hashes.add(doc_id)

                existing = self._db.get_document(doc_id, self._active_environment_id())
                if existing is not None:
                    if (
                        existing.status == DocumentStatus.done
                        and existing.chunk_count > 0
                    ):
                        messages.append(
                            f"Bereits indexiert, uebersprungen: {file_name}"
                        )
                        skipped_ids.append(doc_id)
                        continue
                    if existing.status in (
                        DocumentStatus.queued,
                        DocumentStatus.processing,
                    ):
                        # Kein erneutes Kopieren: Job erneut anstossen (Queue war evtl. nach Neustart leer).
                        if self._enqueue_job(doc_id, JobType.reindex):
                            messages.append(
                                f"Verarbeitung erneut angestossen: {file_name}"
                            )
                            queued_ids.append(doc_id)
                        else:
                            messages.append(
                                f"Bereits in der aktuellen Verarbeitungsqueue: {file_name}"
                            )
                            skipped_ids.append(doc_id)
                        continue

                stored = self._fs.copy_to_managed_storage(
                    file_name, file_bytes=content
                )
                doc_id = stored["docId"]
                self._db.upsert_document(
                    environment_id=self._active_environment_id(),
                    doc_id=doc_id,
                    file_name=stored["fileName"],
                    file_path=stored["destinationPath"],
                    file_hash=stored["fileHash"],
                    file_type=stored["extension"] or "unknown",
                    status=DocumentStatus.queued,
                    tags=options.tags,
                    source=options.source,
                    corpus_path=self._fs.get_corpus_path(doc_id),
                    size_bytes=stored["sizeBytes"],
                )
                self._enqueue_job(doc_id, JobType.reindex)
                queued_ids.append(doc_id)
            except Exception as exc:
                _logger.exception("add_documents file=%s", file_name)
                messages.append(f"Fehler bei {file_name}: {exc}")

        if not queued_ids and files:
            messages.append(
                "Hinweis: Kein neuer Job angelegt (alles uebersprungen oder nur Duplikate). "
                "Wartende Dokumente werden beim API-Start automatisch fortgesetzt; "
                "Ordner erneut hochladen stoesst wartende Eintraege ohne erneuten Speicher an."
            )
        asyncio.get_event_loop().call_soon(
            lambda: asyncio.ensure_future(self._process_queue())
        )
        return AddDocumentsResult(
            queued_doc_ids=queued_ids,
            skipped_doc_ids=skipped_ids,
            messages=messages,
        )

    async def add_documents_from_folder_path(
        self,
        folder_path: str,
        options: UploadOptions,
        *,
        offset: int = 0,
        batch_size: int = 400,
    ) -> tuple[AddDocumentsResult, int, int, bool]:
        self._ensure_db_validated()
        files = iter_files_recursive(folder_path)
        file_count = len(files)
        if not files:
            return (
                AddDocumentsResult(
                    queued_doc_ids=[],
                    skipped_doc_ids=[],
                    messages=[f"Ordner ist leer: {folder_path}"],
                ),
                0,
                0,
                True,
            )
        safe_offset = max(0, offset)
        safe_batch_size = min(2000, max(1, batch_size))
        subset = files[safe_offset : safe_offset + safe_batch_size]
        next_offset = safe_offset + len(subset)
        done = next_offset >= file_count

        queued_ids: list[str] = []
        skipped_ids: list[str] = []
        messages: list[str] = []
        seen_hashes: set[str] = set()

        for absolute_path, relative_name in subset:
            try:
                content = Path(absolute_path).read_bytes()
                doc_id = create_sha256(content)
                if doc_id in seen_hashes:
                    skipped_ids.append(doc_id)
                    messages.append(
                        f"Duplikat im Ordner uebersprungen: {relative_name}"
                    )
                    continue
                seen_hashes.add(doc_id)

                existing = self._db.get_document(doc_id, self._active_environment_id())
                if existing is not None:
                    if existing.status == DocumentStatus.done and existing.chunk_count > 0:
                        skipped_ids.append(doc_id)
                        messages.append(
                            f"Unveraendert (Hash gleich), uebersprungen: {relative_name}"
                        )
                        continue
                    if existing.status in (DocumentStatus.queued, DocumentStatus.processing):
                        if self._enqueue_job(doc_id, JobType.reindex):
                            queued_ids.append(doc_id)
                            messages.append(
                                f"Verarbeitung erneut angestossen: {relative_name}"
                            )
                        else:
                            skipped_ids.append(doc_id)
                            messages.append(
                                f"Bereits in der aktuellen Verarbeitungsqueue: {relative_name}"
                            )
                        continue

                stored = self._fs.copy_to_managed_storage(
                    relative_name, file_bytes=content
                )
                doc_id = stored["docId"]
                self._db.upsert_document(
                    environment_id=self._active_environment_id(),
                    doc_id=doc_id,
                    file_name=stored["fileName"],
                    file_path=stored["destinationPath"],
                    file_hash=stored["fileHash"],
                    file_type=stored["extension"] or "unknown",
                    status=DocumentStatus.queued,
                    tags=options.tags,
                    source=options.source,
                    corpus_path=self._fs.get_corpus_path(doc_id),
                    size_bytes=stored["sizeBytes"],
                )
                self._enqueue_job(doc_id, JobType.reindex)
                queued_ids.append(doc_id)
            except Exception as exc:
                _logger.exception("add_documents_from_folder_path file=%s", absolute_path)
                messages.append(f"Fehler bei {relative_name}: {exc}")

        asyncio.get_event_loop().call_soon(
            lambda: asyncio.ensure_future(self._process_queue())
        )
        return (
            AddDocumentsResult(
                queued_doc_ids=queued_ids,
                skipped_doc_ids=skipped_ids,
                messages=messages,
            ),
            file_count,
            next_offset,
            done,
        )

    async def remove_document(self, doc_id: str) -> None:
        doc = self._db.get_document(doc_id, self._active_environment_id())
        if not doc:
            return
        self._vs.remove_document(self._active_pg().db_table_name, doc_id)
        self._fs.delete_document_artifacts(doc_id)
        self._db.delete_document(doc_id)

    async def remove_documents(self, doc_ids: list[str]) -> None:
        for doc_id in doc_ids:
            await self.remove_document(doc_id)

    async def remove_not_ingested_documents(self) -> int:
        """
        Entfernt alle Dokumente des aktiven Environments, die nicht fertig eingelesen sind:
        status != done oder chunk_count <= 0.
        """
        docs = self._db.list_documents(self._active_environment_id())
        to_remove = [
            doc.doc_id
            for doc in docs
            if not (doc.status == DocumentStatus.done and doc.chunk_count > 0)
        ]
        for doc_id in to_remove:
            await self.remove_document(doc_id)
        return len(to_remove)

    async def reindex_document(self, doc_id: str) -> None:
        self._enqueue_job(doc_id, JobType.reindex)
        asyncio.get_event_loop().call_soon(lambda: asyncio.ensure_future(self._process_queue()))

    async def reindex_documents(self, doc_ids: list[str]) -> None:
        for doc_id in doc_ids:
            self._enqueue_job(doc_id, JobType.reindex)
        asyncio.get_event_loop().call_soon(lambda: asyncio.ensure_future(self._process_queue()))

    async def get_corpus(self, doc_id: str) -> str:
        doc = self._db.get_document(doc_id, self._active_environment_id())
        if not doc:
            raise ValueError("Dokument nicht gefunden.")
        return self._fs.read_text_file(doc.corpus_path)

    async def save_corpus(self, doc_id: str, jsonl_content: str) -> None:
        doc = self._db.get_document(doc_id, self._active_environment_id())
        if not doc:
            raise ValueError("Dokument nicht gefunden.")
        lines = [line for line in jsonl_content.split("\n") if line.strip()]
        self._fs.write_corpus_jsonl(doc_id, lines)
        self._db.set_document_status(doc_id, DocumentStatus.queued)

    def get_settings(self) -> AppSettings:
        return self._settings

    def _merge_db_passwords_from_stored(self, incoming: AppSettings) -> AppSettings:
        """Leeres dbPassword im Formular ueberschreibt nicht das zuletzt gespeicherte Passwort (wie pgAdmin)."""
        by_id = {e.environment_id: e for e in self._settings.postgres_environments}
        merged_envs: list[PostgresEnvironment] = []
        for env in incoming.postgres_environments:
            prev = by_id.get(env.environment_id)
            if (
                prev is not None
                and env.vector_backend == "postgres"
                and (env.db_password is None or str(env.db_password).strip() == "")
            ):
                merged_envs.append(env.model_copy(update={"db_password": prev.db_password}))
            else:
                merged_envs.append(env)
        return incoming.model_copy(update={"postgres_environments": merged_envs})

    async def save_settings(self, settings: AppSettings) -> AppSettings:
        merged = self._merge_db_passwords_from_stored(settings)
        self._settings = persist_settings(merged)
        self._is_db_validated = False
        try:
            self._rebuild_vector_store()
        except Exception as exc:
            # Settings sollen speicherbar bleiben, auch wenn das gewaehlte Backend lokal noch fehlt.
            _logger.warning(
                "vector store konnte nach save_settings nicht initialisiert werden (wird im Connection Test sichtbar): %s",
                exc,
            )
        from .dependencies import get_chat_service

        try:
            get_chat_service().update_settings(self._settings)
            self._sync_chat_vector_store()
        except RuntimeError:
            pass
        return self._settings

    def is_database_connection_ready(self) -> bool:
        return self._is_db_validated

    async def test_database_connection(
        self,
        working_settings: AppSettings | None = None,
    ) -> dict:
        """
        Testet die Vektor-Datenbank der aktiven Umgebung (Postgres+pgvector, SQLite embedded oder Qdrant embedded).
        Wenn working_settings gesetzt ist (Formular aus der UI), werden diese Werte genutzt —
        bei Erfolg werden sie persistiert (wie „Speichern“ nach erfolgreichem Test).
        """
        merged_working: AppSettings | None = None
        if working_settings is not None:
            merged_working = self._merge_db_passwords_from_stored(working_settings)
            app_for_pg = merged_working
        else:
            app_for_pg = self._settings
        pg = app_for_pg.get_active_postgres()
        base = get_app_paths()["base"]
        base.mkdir(parents=True, exist_ok=True)

        try:
            if pg.vector_backend == "postgres":
                import psycopg2

                conn = psycopg2.connect(
                    host=pg.db_host,
                    port=pg.db_port,
                    dbname=pg.db_name,
                    user=pg.db_user,
                    password=pg.db_password,
                    connect_timeout=15,
                )
                conn.autocommit = True
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
                conn.close()
                vs = PostgresVectorStore(
                    host=pg.db_host,
                    port=pg.db_port,
                    database=pg.db_name,
                    user=pg.db_user,
                    password=pg.db_password,
                    schema=pg.db_schema,
                )
                vs.ensure_schema(pg.db_table_name)
                self._vs = vs
            elif pg.vector_backend == "sqlite_embedded":
                from .vector_store.sqlite_embedded import SqliteEmbeddedVectorStore

                p = resolve_sqlite_path(pg, base)
                vs = SqliteEmbeddedVectorStore(p)
                vs.ensure_schema(pg.db_table_name)
                self._vs = vs
            elif pg.vector_backend == "qdrant_embedded":
                from .vector_store.qdrant_embedded import QdrantEmbeddedVectorStore

                p = resolve_qdrant_path(pg, base)
                vs = QdrantEmbeddedVectorStore(p)
                vs.ensure_schema(pg.db_table_name)
                self._vs = vs
            else:
                self._is_db_validated = False
                return {"status": "error", "message": f"Unbekannter vectorBackend: {pg.vector_backend}"}
        except ImportError as exc:
            self._is_db_validated = False
            return {
                "status": "error",
                "message": (
                    "connection test failed: "
                    f"{exc} | Python interpreter: {sys.executable} | "
                    "Installiere Pakete genau in dieser Umgebung, z. B. "
                    f"\"{sys.executable}\" -m pip install qdrant-client"
                ),
            }
        except Exception as exc:
            self._is_db_validated = False
            return {"status": "error", "message": f"connection test failed: {exc}"}

        self._is_db_validated = True
        if merged_working is not None:
            self._settings = persist_settings(merged_working)
            from .dependencies import get_chat_service

            try:
                get_chat_service().update_settings(self._settings)
            except RuntimeError:
                pass
        # Immer: Chat nutzt dieselbe Vector-Store-Instanz wie Ingest (z. B. neues SQLite nach Test).
        self._sync_chat_vector_store()
        msg = self._connection_test_success_message(pg, base)
        return {"status": "ok", "message": msg}

    @staticmethod
    def _connection_test_success_message(pg: PostgresEnvironment, base_dir: Path) -> str:
        if pg.vector_backend == "postgres":
            return (
                f"connection test success, schema ready "
                f"({pg.db_schema}.{pg.db_table_name}, {pg.db_name}@{pg.db_host})"
            )
        if pg.vector_backend == "sqlite_embedded":
            return f"connection test success, sqlite embedded ready ({resolve_sqlite_path(pg, base_dir)})"
        if pg.vector_backend == "qdrant_embedded":
            return f"connection test success, qdrant embedded ready ({resolve_qdrant_path(pg, base_dir)})"
        return "connection test success"

    async def run_health_check(self) -> dict:
        vc = self._vs.health_check()
        pw = {"status": "ok", "message": "Python Worker ist bereit."}
        return {"postgres": vc, "vectorDatabase": vc, "pythonWorker": pw}

    def export_documents_as_csv(self) -> str:
        docs = self._db.list_documents(self._active_environment_id())
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "docId", "fileName", "fileType", "status",
                "chunkCount", "source", "tags", "createdAt", "updatedAt",
            ],
        )
        writer.writeheader()
        for doc in docs:
            writer.writerow(
                {
                    "docId": doc.doc_id,
                    "fileName": doc.file_name,
                    "fileType": doc.file_type,
                    "status": doc.status.value,
                    "chunkCount": doc.chunk_count,
                    "source": doc.source,
                    "tags": ",".join(doc.tags),
                    "createdAt": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(doc.created_at / 1000)
                    ),
                    "updatedAt": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(doc.updated_at / 1000)
                    ),
                }
            )
        return output.getvalue()

    def _emit_progress(self, payload: ProgressEventPayload) -> None:
        for subscriber in self._progress_subscribers:
            subscriber(payload)

    def _ensure_db_validated(self) -> None:
        if not self._is_db_validated:
            raise RuntimeError(
                "Bitte zuerst Connection Test erfolgreich ausfuehren."
            )

    def _enqueue_job(self, doc_id: str, job_type: JobType) -> bool:
        """Neuen Job einreihen. False, wenn fuer doc_id bereits ein Eintrag in der Queue ist."""
        if any(j.get("docId") == doc_id for j in self._queue):
            return False
        job_id = str(uuid.uuid4())
        self._queue.append({"jobId": job_id, "docId": doc_id, "type": job_type})
        self._db.upsert_job(
            environment_id=self._active_environment_id(),
            job_id=job_id,
            doc_id=doc_id,
            job_type=job_type,
            status=JobStatus.queued,
            progress=0,
            message="Job eingeplant.",
        )
        return True

    async def _process_queue(self) -> None:
        if self._is_processing:
            return
        self._is_processing = True
        try:
            while self._queue:
                job = self._queue.pop(0)
                await self._process_single_job(job)
        finally:
            self._is_processing = False

    async def _process_single_job(self, job: dict) -> None:
        doc_id = job["docId"]
        job_id = job["jobId"]
        job_type = job["type"]
        env_id = self._active_environment_id()

        doc = self._db.get_document(doc_id, env_id)
        if not doc:
            return

        self._db.upsert_job(
            environment_id=env_id,
            job_id=job_id, doc_id=doc_id, job_type=job_type,
            status=JobStatus.running, progress=0.05, message="Verarbeitung gestartet.",
        )
        self._db.set_document_status(doc_id, DocumentStatus.processing)
        self._emit_progress(ProgressEventPayload(
            docId=doc_id, jobId=job_id, type=job_type,
            progress=0.05, message="Verarbeitung gestartet.", status=JobStatus.running,
        ))

        try:
            self._vs.remove_document(self._active_pg().db_table_name, doc_id)
            self._emit_progress(ProgressEventPayload(
                docId=doc_id, jobId=job_id, type=job_type,
                progress=0.12, message="Bestehende Vektoren bereinigt.", status=JobStatus.running,
            ))

            corpus_lines = self._try_load_corpus(doc.corpus_path, doc_id)
            if self._contains_binary_pdf(corpus_lines):
                corpus_lines = []

            if not corpus_lines:
                parsed = await run_in_worker_pool(
                    parse_document,
                    doc.file_path,
                    self._settings.chunk_size,
                    self._settings.chunk_overlap,
                )
                if not parsed.get("ok"):
                    raise RuntimeError(parsed.get("error", "Parsing fehlgeschlagen."))

                corpus_lines = []
                for chunk in parsed["chunks"]:
                    corpus_lines.append(
                        {
                            "chunkId": create_sha256(f"{doc_id}:{chunk['chunkIndex']}"),
                            "documentId": doc_id,
                            "chunkIndex": chunk["chunkIndex"],
                            "text": chunk["text"],
                            "metadata": {**chunk.get("metadata", {}), "sourcePath": doc.file_path},
                        }
                    )
                serialized = [json.dumps(line) for line in corpus_lines]
                self._fs.write_corpus_jsonl(doc_id, serialized)

                if self._settings.store_markdown:
                    md = "\n\n".join(
                        f"## Chunk {line['chunkIndex']}\n\n{line['text']}"
                        for line in corpus_lines
                    )
                    self._fs.write_corpus_markdown(doc_id, md)

            self._emit_progress(ProgressEventPayload(
                docId=doc_id, jobId=job_id, type=job_type,
                progress=0.45, message="Corpus gespeichert.", status=JobStatus.running,
            ))

            embedding_inputs = [
                (line, (line.get("text", "") if isinstance(line.get("text"), str) else str(line.get("text", ""))).strip())
                for line in corpus_lines
            ]
            embedding_inputs = [(line, text) for line, text in embedding_inputs if text]

            if not embedding_inputs:
                raise RuntimeError("Keine gueltigen Text-Chunks fuer Embeddings vorhanden.")

            n_chunks = len(embedding_inputs)
            _logger.info(
                "job %s: embeddings start doc=%s… chunks=%s",
                job_id[:8],
                doc_id[:12],
                n_chunks,
            )
            embedding_result = await run_in_worker_pool(
                embed_texts,
                self._settings.embedding_model,
                [text for _, text in embedding_inputs],
            )
            if not embedding_result.get("ok"):
                raise RuntimeError(embedding_result.get("error", "Embedding fehlgeschlagen."))

            vectors = embedding_result["vectors"]
            if not vectors:
                raise RuntimeError("Keine Embeddings erzeugt.")

            _logger.info(
                "job %s: pg vector upsert start doc=%s… vectors=%s",
                job_id[:8],
                doc_id[:12],
                len(vectors),
            )
            self._vs.ensure_schema(self._active_pg().db_table_name)
            payloads = [
                {
                    "documentId": doc_id,
                    "chunkIndex": line["chunkIndex"],
                    "sourcePath": doc.file_path,
                    "sourceModifiedUnixSeconds": int(doc.updated_at / 1000),
                    "text": line.get("text", ""),
                    "tags": doc.tags,
                    # URL pro Chunk bevorzugen: zuerst aus Chunk-Text ("Quelle: ..."),
                    # dann canonicalUrl (falls verfügbar), sonst doc.source (Fallback).
                    "source": (
                        _extract_source_url_from_chunk_text(str(line.get("text", "")))
                        or _normalize_source_url((line.get("metadata") or {}).get("canonicalUrl"))
                        or _normalize_source_url(doc.source)
                    ),
                    "fileName": doc.file_name,
                }
                for line, _ in embedding_inputs
            ]
            self._vs.upsert_document_chunks(
                self._active_pg().db_table_name, doc_id, vectors, payloads,
            )

            self._db.set_document_index_result(doc_id, len(vectors))
            self._db.upsert_job(
                environment_id=env_id,
                job_id=job_id, doc_id=doc_id, job_type=job_type,
                status=JobStatus.done, progress=1, message="Indexierung erfolgreich abgeschlossen.",
            )
            self._emit_progress(ProgressEventPayload(
                docId=doc_id, jobId=job_id, type=job_type,
                progress=1, message="Indexierung erfolgreich abgeschlossen.", status=JobStatus.done,
            ))

        except Exception as exc:
            msg = str(exc)
            self._db.set_document_status(doc_id, DocumentStatus.error, msg)
            self._db.upsert_job(
                environment_id=env_id,
                job_id=job_id, doc_id=doc_id, job_type=job_type,
                status=JobStatus.error, progress=1, message=msg,
            )
            self._emit_progress(ProgressEventPayload(
                docId=doc_id, jobId=job_id, type=job_type,
                progress=1, message=msg, status=JobStatus.error,
            ))

    def _try_load_corpus(self, corpus_path: str, doc_id: str) -> list[dict]:
        try:
            raw = self._fs.read_text_file(corpus_path)
            rows = [line.strip() for line in raw.split("\n") if line.strip()]
            result: list[dict] = []
            for idx, row in enumerate(rows):
                parsed = json.loads(row)
                result.append(
                    {
                        "chunkId": parsed.get("chunkId") or create_sha256(f"{doc_id}:{idx}"),
                        "documentId": parsed.get("documentId") or doc_id,
                        "chunkIndex": int(parsed.get("chunkIndex", idx)),
                        "text": str(parsed.get("text", "")),
                        "metadata": parsed.get("metadata", {}),
                    }
                )
            return result
        except Exception:
            return []

    @staticmethod
    def _contains_binary_pdf(corpus_lines: list[dict]) -> bool:
        return any(
            str(line.get("text", "")).lstrip().startswith("%PDF-")
            for line in corpus_lines
        )
