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


class PostgresEnvironment(BaseModel):
    """Eine adressierbare Postgres-Zielumgebung (eigene DB und/oder Schema + Tabelle)."""

    environment_id: str = Field(alias="id")
    name: str = Field("Standard", alias="name")
    db_host: str = Field("localhost", alias="dbHost")
    db_port: int = Field(5432, alias="dbPort")
    db_name: str = Field("rag", alias="dbName")
    db_user: str = Field("postgres", alias="dbUser")
    db_password: str = Field("", alias="dbPassword")
    db_schema: str = Field("public", alias="dbSchema")
    db_table_name: str = Field("rag_documents", alias="dbTableName")

    model_config = {"populate_by_name": True}


class AppSettings(BaseModel):
    active_postgres_environment_id: str = Field("default", alias="activePostgresEnvironmentId")
    postgres_environments: list[PostgresEnvironment] = Field(
        default_factory=list,
        alias="postgresEnvironments",
    )
    chunk_size: int = Field(900, alias="chunkSize")
    chunk_overlap: int = Field(150, alias="chunkOverlap")
    embedding_model: str = Field("all-MiniLM-L6-v2", alias="embeddingModel")
    store_markdown: bool = Field(True, alias="storeMarkdown")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _ensure_active_environment(self) -> AppSettings:
        if not self.postgres_environments:
            raise ValueError("Mindestens eine Postgres-Umgebung ist erforderlich.")
        ids = {env.environment_id for env in self.postgres_environments}
        if self.active_postgres_environment_id not in ids:
            self.active_postgres_environment_id = next(iter(ids))
        return self

    def get_active_postgres(self) -> PostgresEnvironment:
        for env in self.postgres_environments:
            if env.environment_id == self.active_postgres_environment_id:
                return env
        return self.postgres_environments[0]


class DatabaseTestRequest(BaseModel):
    """POST /database/test-connection: aktuelle Formular-Einstellungen testen (ohne vorher Speichern)."""

    settings: AppSettings | None = None

    model_config = {"populate_by_name": True}


class UploadOptions(BaseModel):
    tags: list[str] = Field(default_factory=list)
    source: str = "lokal"


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


class ChatResponse(BaseModel):
    answer: str
    context_chunks: list[dict] = Field(default_factory=list, alias="contextChunks")
    encrypted_payload: str = Field("", alias="encryptedPayload")

    model_config = {"populate_by_name": True}


class ChatSettings(BaseModel):
    llm_api_key: str = Field("ollama", alias="llmApiKey")
    llm_base_url: str = Field("http://localhost:11434/v1", alias="llmBaseUrl")
    llm_model: str = Field("llama3.2", alias="llmModel")
    temperature: float = 0.3
    max_tokens: int = Field(2048, alias="maxTokens")
    top_k: int = Field(5, alias="topK")
    system_prompt: str = Field(
        "You are a helpful assistant that answers questions based on provided documents. "
        "Always cite the source file name when possible. Be precise and thorough.",
        alias="systemPrompt",
    )
    encryption_key: str = Field("", alias="encryptionKey")

    model_config = {"populate_by_name": True}
