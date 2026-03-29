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

export interface PostgresEnvironment {
  id: string;
  name: string;
  dbHost: string;
  dbPort: number;
  dbName: string;
  dbUser: string;
  dbPassword: string;
  /** Postgres-Schema fuer die Vektor-Tabelle (z. B. public, rag_a, rag_b). */
  dbSchema: string;
  dbTableName: string;
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
      dbHost: "localhost",
      dbPort: 5432,
      dbName: "rag",
      dbUser: "postgres",
      dbPassword: "",
      dbSchema: "public",
      dbTableName: "rag_documents"
    }
  ],
  chunkSize: 900,
  chunkOverlap: 150,
  embeddingModel: "all-MiniLM-L6-v2",
  storeMarkdown: true
};

export interface UploadOptions {
  tags: string[];
  source: string;
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
