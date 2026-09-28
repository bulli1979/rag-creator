import { BrowserWindow, dialog, ipcMain } from "electron";
import type { AppSettings, UploadOptions } from "@rag/shared";
import { ApiClient } from "./services/apiClient.js";
import {
  loadConnectionConfig,
  saveConnectionConfig,
  type ConnectionConfig
} from "./services/connectionConfigStore.js";

async function uploadFolderContents(
  getApiClient: () => ApiClient,
  folderPath: string,
  options: UploadOptions
): Promise<{
  queuedDocIds: string[];
  skippedDocIds: string[];
  messages: string[];
  fileCount: number;
}> {
  console.log("[ipc] uploadFolderContents: root =", folderPath);
  try {
    const upload = await getApiClient().uploadFolderPath(folderPath, options);
    console.log("[ipc] uploadFolderContents: queued doc ids =", upload.queuedDocIds?.length ?? 0);
    return upload;
  } catch (err) {
    console.error("[ipc] uploadFolderContents: uploadFolderPath failed", err);
    throw err;
  }
}

export function registerIpcHandlers(mainWindow: BrowserWindow, getApiClient: () => ApiClient): void {
  let stopProgress: (() => void) | null = null;

  const bindProgress = () => {
    stopProgress?.();
    stopProgress = getApiClient().subscribeProgress((event) => {
      if (!mainWindow.isDestroyed()) {
        mainWindow.webContents.send("jobs:progress", event);
      }
    });
  };

  bindProgress();

  ipcMain.handle("connection:get", async () => loadConnectionConfig());

  ipcMain.handle("connection:save", async (_event, config: ConnectionConfig) => {
    const saved = await saveConnectionConfig(config);
    getApiClient().setCredentials(saved.apiBaseUrl, saved.apiKey);
    bindProgress();
    return saved;
  });

  ipcMain.handle("connection:test", async (_event, config: ConnectionConfig) => {
    return ApiClient.testConnection(config.apiBaseUrl, config.apiKey);
  });

  ipcMain.handle("auth:me", () => getApiClient().getAuthMe());

  ipcMain.handle("admin:keys:list", () => getApiClient().listApiKeys());
  ipcMain.handle("admin:keys:create", async (_event, label: string, isAdmin = false) =>
    getApiClient().createApiKey(label, isAdmin)
  );
  ipcMain.handle("admin:keys:revoke", async (_event, keyId: string) => {
    await getApiClient().revokeApiKey(keyId);
    return { ok: true as const };
  });

  ipcMain.handle("documents:list", () => getApiClient().listDocuments());
  ipcMain.handle("jobs:list", () => getApiClient().listJobs());

  ipcMain.handle("documents:pick-and-upload", async (_event, options: UploadOptions) => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ["openFile", "multiSelections"],
      title: "Dokumente auswaehlen"
    });
    if (result.canceled || result.filePaths.length === 0) {
      return { queuedDocIds: [], skippedDocIds: [], messages: [] };
    }
    return getApiClient().uploadFiles(result.filePaths, options);
  });

  ipcMain.handle("documents:upload-files", async (_event, filePaths: string[], options: UploadOptions) => {
    return getApiClient().uploadFiles(filePaths, options);
  });

  ipcMain.handle("documents:pick-folder", async () => {
    try {
      console.log("[ipc] documents:pick-folder: opening directory dialog …");
      const result = await dialog.showOpenDialog(mainWindow, {
        properties: ["openDirectory"],
        title: "Ordner fuer Einlesen auswaehlen"
      });
      console.log(
        "[ipc] documents:pick-folder: canceled=%s paths=%s",
        result.canceled,
        result.filePaths?.length ?? 0
      );
      if (result.canceled || result.filePaths.length === 0) {
        return { canceled: true as const };
      }
      const folderPath = result.filePaths[0]?.trim();
      if (!folderPath) {
        console.warn("[ipc] documents:pick-folder: first path empty");
        return { canceled: true as const };
      }
      console.log("[ipc] documents:pick-folder: selected", folderPath);
      return { canceled: false as const, folderPath };
    } catch (err) {
      console.error("[ipc] documents:pick-folder: ERROR", err);
      throw err;
    }
  });

  ipcMain.handle(
    "documents:upload-folder-from-path",
    async (_event, folderPath: string, options: UploadOptions) => {
      try {
        if (!folderPath?.trim()) {
          throw new Error("upload-folder-from-path: leerer folderPath");
        }
        console.log("[ipc] documents:upload-folder-from-path:", folderPath.trim());
        return await uploadFolderContents(getApiClient, folderPath.trim(), options);
      } catch (err) {
        console.error("[ipc] documents:upload-folder-from-path: ERROR", err);
        throw err;
      }
    }
  );

  ipcMain.handle("documents:pick-folder-and-upload", async (_event, options: UploadOptions) => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ["openDirectory"],
      title: "Ordner indexieren (rekursiv)"
    });
    if (result.canceled || result.filePaths.length === 0) {
      return { queuedDocIds: [], skippedDocIds: [], messages: [], fileCount: 0 };
    }
    const folderPath = result.filePaths[0];
    if (!folderPath) {
      return { queuedDocIds: [], skippedDocIds: [], messages: [], fileCount: 0 };
    }
    return uploadFolderContents(getApiClient, folderPath, options);
  });

  ipcMain.handle("documents:reindex", async (_event, docId: string) => {
    return getApiClient().reindexDocument(docId);
  });

  ipcMain.handle("documents:reindex-bulk", async (_event, docIds: string[]) => {
    return getApiClient().reindexDocuments(docIds);
  });

  ipcMain.handle("documents:remove", async (_event, docId: string) => {
    return getApiClient().removeDocument(docId);
  });

  ipcMain.handle("documents:remove-bulk", async (_event, docIds: string[]) => {
    return getApiClient().removeDocuments(docIds);
  });
  ipcMain.handle("documents:remove-not-ingested", async () => {
    return getApiClient().removeNotIngestedDocuments();
  });

  ipcMain.handle("corpus:get", async (_event, docId: string) => getApiClient().getCorpus(docId));
  ipcMain.handle("corpus:save", async (_event, docId: string, jsonlContent: string) => {
    return getApiClient().saveCorpus(docId, jsonlContent);
  });

  ipcMain.handle("settings:get", () => getApiClient().getSettings());
  ipcMain.handle("settings:save", async (_event, settings: AppSettings) => getApiClient().saveSettings(settings));
  ipcMain.handle("database:test-connection", async (_event, settings?: AppSettings) => {
    try {
      return await getApiClient().testDatabaseConnection(settings);
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : String(err);
      return {
        status: "error" as const,
        message: `${detail} Hinweis: documentApi starten (FastAPI, z. B. Port 8000) oder Verbindung prüfen.`
      };
    }
  });
  ipcMain.handle("database:connection-state", () => getApiClient().getDatabaseConnectionState());
  ipcMain.handle("llm:list-ollama-models", () => getApiClient().listOllamaModels());
  ipcMain.handle("chat:settings:get", () => getApiClient().getChatSettings());
  ipcMain.handle("chat:settings:save", async (_event, settings) => getApiClient().saveChatSettings(settings));
  ipcMain.handle("health:check", () => getApiClient().runHealthCheck());
  ipcMain.handle("documents:export-csv", () => getApiClient().exportDocumentsCsv());
}
