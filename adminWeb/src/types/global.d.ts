import type { AppSettings, DocumentRecord, JobRecord, ProgressEventPayload, UploadOptions } from "@rag/shared";

export type OllamaModelRow = { name: string; size: number | null; modifiedAt: string | null };
export type OllamaModelsResult = { ollamaBaseUrl: string; models: OllamaModelRow[] };

export type ChatSettings = {
  llmApiKey: string;
  llmBaseUrl: string;
  llmModel: string;
  temperature: number;
  maxTokens: number;
  topK: number;
  rerankSimilarityWeight: number;
  rerankLexicalWeight: number;
  rerankNumericWeight: number;
  systemPrompt: string;
  encryptionKey: string;
};

/** Antwort von POST /api/documents/upload (Main-Prozess leitet durch). */
export type DocumentUploadResult = {
  queuedDocIds: string[];
  skippedDocIds: string[];
  messages: string[];
};

export interface ConnectionConfig {
  apiBaseUrl: string;
  apiKey: string;
}

export type ConnectionTestResult = { ok: boolean; isAdmin: boolean; message: string };

export type ApiKeyListItem = {
  keyId: string;
  label: string;
  isAdmin: boolean;
  createdAt: number;
  lastUsedAt?: number | null;
  revokedAt?: number | null;
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
      /** Browser-only: Dateien direkt hochladen (Drag&Drop / FileList). */
      uploadBrowserFiles?: (files: File[], options: UploadOptions) => Promise<DocumentUploadResult>;
      reindexDocument: (docId: string) => Promise<{ ok: true }>;
      reindexDocuments: (docIds: string[]) => Promise<{ ok: true }>;
      startFamilyReindex?: (body?: {
        familyId?: string;
        sourceEnvironmentId?: string;
      }) => Promise<{
        runId?: string;
        status: string;
        familyId?: string;
        familyName?: string;
        instanceTotal?: number;
        instanceIndex?: number;
        documentTotal?: number;
        documentIndex?: number;
        currentEnvironmentName?: string;
        message?: string;
        error?: string;
      }>;
      getFamilyReindexStatus?: () => Promise<{
        status: string;
        familyId?: string;
        familyName?: string;
        instanceTotal?: number;
        instanceIndex?: number;
        documentTotal?: number;
        documentIndex?: number;
        currentEnvironmentName?: string;
        message?: string;
        error?: string;
      }>;
      cancelFamilyReindex?: () => Promise<unknown>;
      removeDocument: (docId: string) => Promise<{ ok: true }>;
      removeDocuments: (docIds: string[]) => Promise<{ ok: true }>;
      removeNotIngestedDocuments: () => Promise<{ ok: true; removedCount: number }>;
      getCorpus: (docId: string) => Promise<string>;
      saveCorpus: (docId: string, jsonlContent: string) => Promise<{ ok: true }>;
      getSettings: () => Promise<AppSettings>;
      saveSettings: (settings: AppSettings) => Promise<AppSettings>;
      testDatabaseConnection: (
        settings?: AppSettings
      ) => Promise<{ status: "ok" | "error"; message: string }>;
      getDatabaseConnectionState: () => Promise<{ ready: boolean }>;
      listOllamaModels: () => Promise<OllamaModelsResult>;
      getChatSettings: () => Promise<ChatSettings>;
      saveChatSettings: (settings: ChatSettings) => Promise<ChatSettings>;
      runHealthCheck: () => Promise<{
        postgres: { status: "ok" | "error"; message: string };
        vectorDatabase?: { status: "ok" | "error"; message: string };
        pythonWorker: { status: "ok" | "error"; message: string };
      }>;
      exportDocumentsCsv: () => Promise<string>;
      onJobProgress: (handler: (event: ProgressEventPayload) => void) => () => void;
      connectionGet: () => Promise<ConnectionConfig | null>;
      connectionSave: (config: ConnectionConfig) => Promise<ConnectionConfig>;
      connectionTest: (config: ConnectionConfig) => Promise<ConnectionTestResult>;
      listApiKeys: () => Promise<ApiKeyListItem[]>;
      createApiKey: (label: string, isAdmin?: boolean) => Promise<ApiKeyListItem & { apiKey: string }>;
      revokeApiKey: (keyId: string) => Promise<{ ok: true }>;
      startBatchTest: (
        file: File,
        options?: {
          evaluateAnswers?: boolean;
          language?: string;
          settingsId?: string;
          settingsName?: string;
          environmentId?: string;
          familyId?: string;
          runAllInstances?: boolean;
          chatSettings?: Record<string, unknown>;
          evalJudge?: Record<string, unknown>;
          questionsFile?: File;
        }
      ) => Promise<import("./BulkTestPanel").BatchRun>;
      getBatchTestRun: (runId: string) => Promise<import("./BulkTestPanel").BatchRun>;
      listBatchTestRuns: (params?: {
        limit?: number;
        sortBy?: string;
        sortDir?: string;
      }) => Promise<{ runs: import("./BulkTestPanel").BatchRun[] }>;
      deleteBatchTestRun: (runId: string) => Promise<{ ok: true }>;
      cancelBatchTest: (runId: string) => Promise<import("./BulkTestPanel").BatchRun>;
      getBatchTestDefaults: () => Promise<{
        chatSettings: Record<string, unknown>;
        evalJudge: Record<string, unknown>;
        activeEnvironmentId?: string;
        activeEnvironmentName?: string;
        activeFamilyId?: string;
        environments?: Array<{
          id: string;
          name: string;
          vectorBackend?: string;
          familyId?: string;
          familyName?: string;
          embeddingModel?: string;
          chunkSize?: number;
          chunkOverlap?: number;
        }>;
        families?: Array<{
          familyId: string;
          familyName: string;
          instanceCount: number;
          instanceIds: string[];
        }>;
      }>;
      listBatchTestSettings: () => Promise<{
        settings: import("./BulkTestPanel").BatchTestSettings[];
      }>;
      saveBatchTestSettings: (body: {
        settingsId?: string | null;
        name: string;
        chatSettings: Record<string, unknown>;
        evalJudge: Record<string, unknown>;
      }) => Promise<import("./BulkTestPanel").BatchTestSettings>;
      deleteBatchTestSettings: (settingsId: string) => Promise<{ ok: true }>;
      copyBatchTestSettingsFromRun: (
        runId: string,
        name?: string
      ) => Promise<import("./BulkTestPanel").BatchTestSettings>;
    };
  }
}

export {};
