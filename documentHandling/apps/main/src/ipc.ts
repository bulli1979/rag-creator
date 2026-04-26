import { BrowserWindow, dialog, ipcMain } from "electron";
import type { AppSettings, UploadOptions } from "@rag/shared";
import { ApiClient } from "./services/apiClient.js";

async function uploadFolderContents(
  apiClient: ApiClient,
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
    const upload = await apiClient.uploadFolderPath(folderPath, options);
    console.log("[ipc] uploadFolderContents: queued doc ids =", upload.queuedDocIds?.length ?? 0);
    return upload;
  } catch (err) {
    console.error("[ipc] uploadFolderContents: uploadFolderPath failed", err);
    throw err;
  }
}

export function registerIpcHandlers(mainWindow: BrowserWindow, apiClient: ApiClient): void {
  ipcMain.handle("documents:list", () => apiClient.listDocuments());
  ipcMain.handle("jobs:list", () => apiClient.listJobs());

  ipcMain.handle("documents:pick-and-upload", async (_event, options: UploadOptions) => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ["openFile", "multiSelections"],
      title: "Dokumente auswaehlen"
    });
    if (result.canceled || result.filePaths.length === 0) {
      return { queuedDocIds: [], skippedDocIds: [], messages: [] };
    }
    return apiClient.uploadFiles(result.filePaths, options);
  });

  ipcMain.handle("documents:upload-files", async (_event, filePaths: string[], options: UploadOptions) => {
    return apiClient.uploadFiles(filePaths, options);
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
        return await uploadFolderContents(apiClient, folderPath.trim(), options);
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
    return uploadFolderContents(apiClient, folderPath, options);
  });

  ipcMain.handle("documents:reindex", async (_event, docId: string) => {
    return apiClient.reindexDocument(docId);
  });

  ipcMain.handle("documents:reindex-bulk", async (_event, docIds: string[]) => {
    return apiClient.reindexDocuments(docIds);
  });

  ipcMain.handle("documents:remove", async (_event, docId: string) => {
    return apiClient.removeDocument(docId);
  });

  ipcMain.handle("documents:remove-bulk", async (_event, docIds: string[]) => {
    return apiClient.removeDocuments(docIds);
  });
  ipcMain.handle("documents:remove-not-ingested", async () => {
    return apiClient.removeNotIngestedDocuments();
  });

  ipcMain.handle("corpus:get", async (_event, docId: string) => apiClient.getCorpus(docId));
  ipcMain.handle("corpus:save", async (_event, docId: string, jsonlContent: string) => {
    return apiClient.saveCorpus(docId, jsonlContent);
  });

  ipcMain.handle("settings:get", () => apiClient.getSettings());
  ipcMain.handle("settings:save", async (_event, settings: AppSettings) => apiClient.saveSettings(settings));
  ipcMain.handle("database:test-connection", async (_event, settings?: AppSettings) => {
    try {
      return await apiClient.testDatabaseConnection(settings);
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : String(err);
      return {
        status: "error" as const,
        message: `${detail} Hinweis: documentApi starten (FastAPI, z. B. Port 8000) oder RAG_API_URL setzen.`
      };
    }
  });
  ipcMain.handle("database:connection-state", () => apiClient.getDatabaseConnectionState());
  ipcMain.handle("llm:list-ollama-models", () => apiClient.listOllamaModels());
  ipcMain.handle("health:check", () => apiClient.runHealthCheck());
  ipcMain.handle("documents:export-csv", () => apiClient.exportDocumentsCsv());

  apiClient.subscribeProgress((event) => {
    if (!mainWindow.isDestroyed()) {
      mainWindow.webContents.send("jobs:progress", event);
    }
  });
}
