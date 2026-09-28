export type DocumentStatus = "queued" | "processing" | "done" | "error";
export type JobType = "parse" | "embed" | "index" | "delete" | "reindex";
export type JobStatus = "queued" | "running" | "done" | "error";

export interface DocumentRecord {
  docId: string;
  fileName: string;
  filePath: string;
  fileHash: string;
  fileType: string;
  createdAt: number;
  updatedAt: number;
  status: DocumentStatus;
  errorMessage: string | null;
  chunkCount: number;
  tags: string[];
  source: string;
  corpusPath: string;
  lastIndexedAt: number | null;
  sizeBytes: number;
}

export interface JobRecord {
  jobId: string;
  docId: string;
  type: JobType;
  status: JobStatus;
  progress: number;
  createdAt: number;
  updatedAt: number;
  message: string;
}

export type VectorBackend = "postgres" | "sqlite_embedded" | "qdrant_embedded";

export interface PostgresEnvironment {
  id: string;
  name: string;
  /** Gemeinsame ID einer logischen Umgebung (Matrix-Instanzen teilen familyId). */
  familyId: string;
  familyName: string;
  /** Vektor-Speicher: Postgres, SQLite ohne Server oder Qdrant lokal. */
  vectorBackend: VectorBackend;
  dbHost: string;
  dbPort: number;
  dbName: string;
  dbUser: string;
  dbPassword: string;
  /** Postgres-Schema fuer die Vektor-Tabelle (z. B. public, rag_a, rag_b). */
  dbSchema: string;
  /** Tabellen-/Collection-Name (Postgres, SQLite, Qdrant). */
  dbTableName: string;
  /** Relativ zu ~/RAGIngestStudio oder absolut; leer = automatisch vector_sqlite/<id>.sqlite */
  sqliteFilePath: string;
  /** Relativ zu ~/RAGIngestStudio oder absolut; leer = automatisch vector_qdrant/<id>/ */
  qdrantLocalPath: string;
  embeddingModel: string;
  chunkSize: number;
  chunkOverlap: number;
  isMatrixVariant?: boolean;
}

export interface AppSettings {
  activePostgresEnvironmentId: string;
  postgresEnvironments: PostgresEnvironment[];
  chunkSize: number;
  chunkOverlap: number;
  embeddingModel: string;
  storeMarkdown: boolean;
}

/** Fallback, wenn die API (documentApi) nicht erreichbar ist. */
export const defaultAppSettings: AppSettings = {
  activePostgresEnvironmentId: "default",
  postgresEnvironments: [
    {
      id: "default",
      name: "Standard",
      familyId: "default",
      familyName: "Standard",
      vectorBackend: "postgres",
      dbHost: "localhost",
      dbPort: 5432,
      dbName: "rag",
      dbUser: "postgres",
      dbPassword: "",
      dbSchema: "public",
      dbTableName: "rag_documents",
      sqliteFilePath: "",
      qdrantLocalPath: "",
      embeddingModel: "paraphrase-multilingual-MiniLM-L12-v2",
      chunkSize: 900,
      chunkOverlap: 15,
      isMatrixVariant: false
    }
  ],
  chunkSize: 900,
  chunkOverlap: 15,
  embeddingModel: "paraphrase-multilingual-MiniLM-L12-v2",
  storeMarkdown: true
};

/** Kuratierte Embedding-Modelle (384-dim, kompatibel zu Qdrant embedded). */
export type EmbeddingModelOption = {
  id: string;
  label: string;
  dimensions: number;
  languages: string;
  recommended?: boolean;
  description?: string;
};

export const EMBEDDING_MODEL_OPTIONS: EmbeddingModelOption[] = [
  {
    id: "paraphrase-multilingual-MiniLM-L12-v2",
    label: "Multilingual MiniLM L12",
    dimensions: 384,
    languages: "de, en, multilingual",
    recommended: true,
    description: "Empfohlen für Deutsch (Flexion/Tempus) und gemischte Corpora."
  },
  {
    id: "all-MiniLM-L6-v2",
    label: "MiniLM L6 (Englisch)",
    dimensions: 384,
    languages: "en",
    description: "Schnell, vor allem Englisch — bisheriger Projekt-Default."
  },
  {
    id: "all-MiniLM-L12-v2",
    label: "MiniLM L12 (Englisch)",
    dimensions: 384,
    languages: "en",
    description: "Etwas stärker als L6, weiterhin englisch-lastig."
  },
  {
    id: "paraphrase-MiniLM-L6-v2",
    label: "Paraphrase MiniLM L6",
    dimensions: 384,
    languages: "en",
    description: "Gut für semantische Ähnlichkeit / Paraphrasen (EN)."
  },
  {
    id: "intfloat/multilingual-e5-small",
    label: "E5 Small (multilingual)",
    dimensions: 384,
    languages: "de, en, multilingual",
    description: "Stark multilingual; etwas langsamer beim ersten Download."
  }
];

export const DEFAULT_EMBEDDING_MODEL_ID = "paraphrase-multilingual-MiniLM-L12-v2";

export interface UploadOptions {
  tags: string[];
  source: string;
  /** Optional: setzt AppSettings.embeddingModel für diesen Upload (+ Chat). */
  embeddingModel?: string;
}

export interface CorpusLine {
  chunkId: string;
  documentId: string;
  chunkIndex: number;
  text: string;
  metadata: Record<string, unknown>;
}

export interface SearchFilters {
  searchText: string;
  status?: DocumentStatus;
  fileType?: string;
  tag?: string;
}

export interface ProgressEventPayload {
  docId: string;
  jobId: string;
  type: JobType;
  progress: number;
  message: string;
  status: JobStatus;
}
