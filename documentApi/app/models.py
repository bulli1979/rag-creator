from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class DocumentStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    done = "done"
    error = "error"


class JobType(str, Enum):
    parse = "parse"
    embed = "embed"
    index = "index"
    delete = "delete"
    reindex = "reindex"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    error = "error"


class DocumentRecord(BaseModel):
    doc_id: str = Field(alias="docId")
    file_name: str = Field(alias="fileName")
    file_path: str = Field(alias="filePath")
    file_hash: str = Field(alias="fileHash")
    file_type: str = Field(alias="fileType")
    created_at: int = Field(alias="createdAt")
    updated_at: int = Field(alias="updatedAt")
    status: DocumentStatus
    error_message: str | None = Field(None, alias="errorMessage")
    chunk_count: int = Field(0, alias="chunkCount")
    tags: list[str] = Field(default_factory=list)
    source: str = ""
    corpus_path: str = Field("", alias="corpusPath")
    last_indexed_at: int | None = Field(None, alias="lastIndexedAt")
    size_bytes: int = Field(0, alias="sizeBytes")

    model_config = {"populate_by_name": True}


class JobRecord(BaseModel):
    job_id: str = Field(alias="jobId")
    doc_id: str = Field(alias="docId")
    type: JobType
    status: JobStatus
    progress: float
    created_at: int = Field(alias="createdAt")
    updated_at: int = Field(alias="updatedAt")
    message: str = ""

    model_config = {"populate_by_name": True}


VectorBackend = Literal["postgres", "sqlite_embedded", "qdrant_embedded"]


def clamp_overlap_percent(value: int | float | None, *, default: int = 15) -> int:
    """Chunk-Overlap als Prozent der Chunk-Größe (0–90)."""
    if value is None:
        return default
    try:
        pct = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(90, pct))


def overlap_chars_from_percent(chunk_size: int, overlap_percent: int) -> int:
    """Wandelt Overlap-% in Zeichen für den Sliding-Window-Cutter um."""
    size = max(1, int(chunk_size or 1))
    pct = clamp_overlap_percent(overlap_percent)
    chars = int(size * pct / 100)
    return max(0, min(size - 1, chars))


def migrate_overlap_value_to_percent(overlap: int | float | None, chunk_size: int) -> int:
    """Alte Absolute-Zeichen-Overlaps (typ. 100–200) → Prozent; Werte ≤40 bleiben Prozent."""
    if overlap is None:
        return 15
    try:
        raw = int(overlap)
    except (TypeError, ValueError):
        return 15
    cs = max(1, int(chunk_size or 900))
    # Absolute Zeichen-Overlaps in diesem Projekt waren typischerweise ≥50
    if raw > 40 or (raw >= 50 and cs >= 400):
        return clamp_overlap_percent(round(raw * 100 / cs))
    return clamp_overlap_percent(raw)


class PostgresEnvironment(BaseModel):
    """Eine adressierbare Zielumgebung: Postgres (pgvector) oder eingebettete Vektor-Backends ohne Server."""

    environment_id: str = Field(alias="id")
    name: str = Field("Standard", alias="name")
    # Familie = logische Umgebung; mehrere Instanzen = Embedding/Chunk-Matrix
    family_id: str = Field("", alias="familyId")
    family_name: str = Field("", alias="familyName")
    vector_backend: VectorBackend = Field("postgres", alias="vectorBackend")
    db_host: str = Field("localhost", alias="dbHost")
    db_port: int = Field(5432, alias="dbPort")
    db_name: str = Field("rag", alias="dbName")
    db_user: str = Field("postgres", alias="dbUser")
    db_password: str = Field("", alias="dbPassword")
    db_schema: str = Field("public", alias="dbSchema")
    db_table_name: str = Field("rag_documents", alias="dbTableName")
    # Eingebettet: SQLite-Datei (leer = automatisch unter ~/RAGIngestStudio/vector_sqlite/<id>.sqlite)
    sqlite_file_path: str = Field("", alias="sqliteFilePath")
    # Eingebettet: Qdrant lokal ohne Server (leer = ~/RAGIngestStudio/vector_qdrant/<id>/)
    qdrant_local_path: str = Field("", alias="qdrantLocalPath")
    embedding_model: str = Field(
        "paraphrase-multilingual-MiniLM-L12-v2", alias="embeddingModel"
    )
    chunk_size: int = Field(900, alias="chunkSize")
    # Überlappung in Prozent der Chunk-Größe (0–90)
    chunk_overlap: int = Field(15, alias="chunkOverlap")
    is_matrix_variant: bool = Field(False, alias="isMatrixVariant")

    model_config = {"populate_by_name": True}


class AppSettings(BaseModel):
    active_postgres_environment_id: str = Field("default", alias="activePostgresEnvironmentId")
    postgres_environments: list[PostgresEnvironment] = Field(
        default_factory=list,
        alias="postgresEnvironments",
    )
    chunk_size: int = Field(900, alias="chunkSize")
    # Überlappung in Prozent der Chunk-Größe (0–90); Spiegel der aktiven Instanz
    chunk_overlap: int = Field(15, alias="chunkOverlap")
    embedding_model: str = Field("paraphrase-multilingual-MiniLM-L12-v2", alias="embeddingModel")
    store_markdown: bool = Field(True, alias="storeMarkdown")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _ensure_active_environment(self) -> AppSettings:
        if not self.postgres_environments:
            raise ValueError("Mindestens eine Postgres-Umgebung ist erforderlich.")
        # Migration: family/embedding/chunk pro Env auffüllen
        fixed: list[PostgresEnvironment] = []
        for env in self.postgres_environments:
            updates: dict = {}
            if not (env.family_id or "").strip():
                updates["family_id"] = env.environment_id
            if not (env.family_name or "").strip():
                updates["family_name"] = env.name or env.environment_id
            if not (env.embedding_model or "").strip():
                updates["embedding_model"] = self.embedding_model
            if not env.chunk_size or env.chunk_size <= 0:
                updates["chunk_size"] = self.chunk_size
            if env.chunk_overlap is None or env.chunk_overlap < 0:
                updates["chunk_overlap"] = self.chunk_overlap
            else:
                # immer auf 0–90 Prozent clampen
                clamped = max(0, min(90, int(env.chunk_overlap)))
                if clamped != env.chunk_overlap:
                    updates["chunk_overlap"] = clamped
            fixed.append(env.model_copy(update=updates) if updates else env)
        self.postgres_environments = fixed
        self.chunk_overlap = max(0, min(90, int(self.chunk_overlap)))

        ids = {env.environment_id for env in self.postgres_environments}
        if self.active_postgres_environment_id not in ids:
            self.active_postgres_environment_id = next(iter(ids))
        return self

    def get_active_postgres(self) -> PostgresEnvironment:
        for env in self.postgres_environments:
            if env.environment_id == self.active_postgres_environment_id:
                return env
        return self.postgres_environments[0]

    def sync_globals_from_active_env(self) -> AppSettings:
        """Spiegelt Embedding/Chunk der aktiven Instanz auf die globalen AppSettings-Felder."""
        env = self.get_active_postgres()
        return self.model_copy(
            update={
                "embedding_model": env.embedding_model or self.embedding_model,
                "chunk_size": int(env.chunk_size or self.chunk_size),
                "chunk_overlap": int(env.chunk_overlap if env.chunk_overlap is not None else self.chunk_overlap),
            }
        )

    def list_family_instances(self, family_id: str) -> list[PostgresEnvironment]:
        fid = (family_id or "").strip()
        if not fid:
            return []
        return [e for e in self.postgres_environments if (e.family_id or e.environment_id) == fid]


class DatabaseTestRequest(BaseModel):
    """POST /database/test-connection: aktuelle Formular-Einstellungen testen (ohne vorher Speichern)."""

    settings: AppSettings | None = None

    model_config = {"populate_by_name": True}


class UploadOptions(BaseModel):
    tags: list[str] = Field(default_factory=list)
    source: str = "lokal"
    embedding_model: str | None = Field(None, alias="embeddingModel")

    model_config = {"populate_by_name": True}


class UploadFolderRequest(BaseModel):
    folder_path: str = Field(alias="folderPath")
    tags: list[str] = Field(default_factory=list)
    source: str = "lokal"
    embedding_model: str | None = Field(None, alias="embeddingModel")
    offset: int = 0
    batch_size: int = Field(default=400, alias="batchSize")

    model_config = {"populate_by_name": True}


class AddDocumentsResult(BaseModel):
    """Antwort POST /api/documents/upload (inkl. uebersprungener Duplikate)."""

    queued_doc_ids: list[str] = Field(alias="queuedDocIds")
    skipped_doc_ids: list[str] = Field(default_factory=list, alias="skippedDocIds")
    messages: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class CorpusLine(BaseModel):
    chunk_id: str = Field(alias="chunkId")
    document_id: str = Field(alias="documentId")
    chunk_index: int = Field(alias="chunkIndex")
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class ProgressEventPayload(BaseModel):
    doc_id: str = Field(alias="docId")
    job_id: str = Field(alias="jobId")
    type: JobType
    progress: float
    message: str
    status: JobStatus

    model_config = {"populate_by_name": True}


class ConnectionTestResult(BaseModel):
    status: str
    message: str


class HealthCheckResult(BaseModel):
    postgres: ConnectionTestResult
    python_worker: ConnectionTestResult = Field(alias="pythonWorker")

    model_config = {"populate_by_name": True}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    language: Literal["de", "en"] | None = None
    client_source: str | None = Field(None, alias="clientSource")

    model_config = {"populate_by_name": True}


class ChatResponse(BaseModel):
    answer: str
    context_chunks: list[dict] = Field(default_factory=list, alias="contextChunks")
    encrypted_payload: str = Field("", alias="encryptedPayload")
    metrics: dict[str, float | int] = Field(default_factory=dict)
    request_id: str = Field("", alias="requestId")

    model_config = {"populate_by_name": True}


class ChatFeedbackRequest(BaseModel):
    helpful: bool | None = None
    rating: int | None = Field(None, ge=1, le=5)
    comment: str | None = None

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _require_score(self) -> ChatFeedbackRequest:
        if self.helpful is None and self.rating is None:
            raise ValueError("helpful oder rating ist erforderlich.")
        return self


class ChatFeedbackRecord(BaseModel):
    feedback_id: str = Field(alias="feedbackId")
    request_id: str = Field(alias="requestId")
    helpful: bool | None = None
    rating: int | None = None
    comment: str | None = None
    created_at: int = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class ChatRequestRecord(BaseModel):
    request_id: str = Field(alias="requestId")
    environment_id: str = Field(alias="environmentId")
    message: str
    language: str | None = None
    answer: str | None = None
    client_source: str | None = Field(None, alias="clientSource")
    status: str
    error_message: str | None = Field(None, alias="errorMessage")
    llm_model: str | None = Field(None, alias="llmModel")
    top_k: int | None = Field(None, alias="topK")
    context_chunk_count: int = Field(0, alias="contextChunkCount")
    metrics: dict[str, float | int] = Field(default_factory=dict)
    created_at: int = Field(alias="createdAt")
    feedback: ChatFeedbackRecord | None = None

    model_config = {"populate_by_name": True}


class ChatSettings(BaseModel):
    llm_api_key: str = Field("ollama", alias="llmApiKey")
    llm_base_url: str = Field("http://localhost:11434/v1", alias="llmBaseUrl")
    llm_model: str = Field("llama3.2", alias="llmModel")
    temperature: float = 0.3
    max_tokens: int = Field(2048, alias="maxTokens")
    top_k: int = Field(5, alias="topK")
    # Relative weights for retrieval rerank (normalized at runtime).
    # Defaults favour embedding similarity (aligned with how chunks are indexed).
    rerank_similarity_weight: float = Field(0.90, ge=0.0, alias="rerankSimilarityWeight")
    rerank_lexical_weight: float = Field(0.05, ge=0.0, alias="rerankLexicalWeight")
    rerank_numeric_weight: float = Field(0.05, ge=0.0, alias="rerankNumericWeight")
    # Optional: vector-search candidate pool before rerank. None → topK*4 (max 30).
    retrieval_candidate_k: int | None = Field(None, ge=1, alias="retrievalCandidateK")
    system_prompt: str = Field(
        "You are a helpful assistant that answers questions based on provided documents. "
        "Always cite the source file name when possible. Be precise and thorough.",
        alias="systemPrompt",
    )
    encryption_key: str = Field("", alias="encryptionKey")

    model_config = {"populate_by_name": True}


class ApiKeyRecord(BaseModel):
    key_id: str = Field(alias="keyId")
    label: str
    is_admin: bool = Field(alias="isAdmin")
    created_at: int = Field(alias="createdAt")
    last_used_at: int | None = Field(None, alias="lastUsedAt")
    revoked_at: int | None = Field(None, alias="revokedAt")

    model_config = {"populate_by_name": True}


class CreateApiKeyRequest(BaseModel):
    label: str = "client"
    is_admin: bool = Field(False, alias="isAdmin")

    model_config = {"populate_by_name": True}


class ApiKeyCreated(ApiKeyRecord):
    api_key: str = Field(alias="apiKey")

    model_config = {"populate_by_name": True}


# --- Admin-Web (eigene Persistenz, getrennt von Electron/localStorage) ---


class AdminWebClient(BaseModel):
    client_id: str = Field(alias="clientId")
    label: str = ""
    user_agent: str | None = Field(None, alias="userAgent")
    created_at: int = Field(alias="createdAt")
    last_seen_at: int = Field(alias="lastSeenAt")

    model_config = {"populate_by_name": True}


class AdminWebClientUpsert(BaseModel):
    client_id: str | None = Field(None, alias="clientId")
    label: str = "admin-web"
    user_agent: str | None = Field(None, alias="userAgent")

    model_config = {"populate_by_name": True}


class AdminWebConnection(BaseModel):
    connection_id: str = Field(alias="connectionId")
    client_id: str = Field(alias="clientId")
    name: str = "default"
    api_base_url: str = Field(alias="apiBaseUrl")
    api_key: str = Field(alias="apiKey")
    is_default: bool = Field(False, alias="isDefault")
    created_at: int = Field(alias="createdAt")
    updated_at: int = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class AdminWebConnectionUpsert(BaseModel):
    connection_id: str | None = Field(None, alias="connectionId")
    name: str = "default"
    api_base_url: str = Field(alias="apiBaseUrl")
    api_key: str = Field(alias="apiKey")
    is_default: bool = Field(True, alias="isDefault")

    model_config = {"populate_by_name": True}


class AdminWebPreference(BaseModel):
    client_id: str = Field(alias="clientId")
    pref_key: str = Field(alias="prefKey")
    pref_value: dict | list | str | int | float | bool | None = Field(alias="prefValue")
    updated_at: int = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class AdminWebPreferenceUpsert(BaseModel):
    pref_key: str = Field(alias="prefKey")
    pref_value: dict | list | str | int | float | bool | None = Field(alias="prefValue")

    model_config = {"populate_by_name": True}


class AdminWebEvent(BaseModel):
    event_id: str = Field(alias="eventId")
    client_id: str | None = Field(None, alias="clientId")
    event_type: str = Field(alias="eventType")
    payload: dict | None = None
    created_at: int = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class AdminWebEventCreate(BaseModel):
    event_type: str = Field(alias="eventType")
    payload: dict | None = None

    model_config = {"populate_by_name": True}
