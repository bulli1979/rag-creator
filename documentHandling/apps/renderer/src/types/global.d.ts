import type { AppSettings, DocumentRecord, JobRecord, ProgressEventPayload, UploadOptions } from "@rag/shared";

/** Antwort von POST /api/documents/upload (Main-Prozess leitet durch). */
export type DocumentUploadResult = {
  queuedDocIds: string[];
  skippedDocIds: string[];
  messages: string[];
};

declare global {
  interface Window {
    ragApi: {
      listDocuments: () => Promise<DocumentRecord[]>;
      listJobs: () => Promise<JobRecord[]>;
      pickAndUploadDocuments: (options: UploadOptions) => Promise<DocumentUploadResult>;
      pickFolder: () => Promise<{ canceled: true } | { canceled: false; folderPath: string }>;
      uploadFolderFromPath: (
        folderPath: string,
        options: UploadOptions
      ) => Promise<DocumentUploadResult & { fileCount: number }>;
      pickFolderAndUploadDocuments: (options: UploadOptions) => Promise<DocumentUploadResult & { fileCount: number }>;
      uploadFiles: (filePaths: string[], options: UploadOptions) => Promise<DocumentUploadResult>;
      reindexDocument: (docId: string) => Promise<{ ok: true }>;
      reindexDocuments: (docIds: string[]) => Promise<{ ok: true }>;
      removeDocument: (docId: string) => Promise<{ ok: true }>;
      removeDocuments: (docIds: string[]) => Promise<{ ok: true }>;
      getCorpus: (docId: string) => Promise<string>;
      saveCorpus: (docId: string, jsonlContent: string) => Promise<{ ok: true }>;
      getSettings: () => Promise<AppSettings>;
      saveSettings: (settings: AppSettings) => Promise<AppSettings>;
      testDatabaseConnection: (
        settings?: AppSettings
      ) => Promise<{ status: "ok" | "error"; message: string }>;
      getDatabaseConnectionState: () => Promise<{ ready: boolean }>;
      runHealthCheck: () => Promise<{
        postgres: { status: "ok" | "error"; message: string };
        pythonWorker: { status: "ok" | "error"; message: string };
      }>;
      exportDocumentsCsv: () => Promise<string>;
      onJobProgress: (handler: (event: ProgressEventPayload) => void) => () => void;
    };
  }
}

export {};
