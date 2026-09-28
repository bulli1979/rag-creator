const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("ragApi", {
  listDocuments: () => ipcRenderer.invoke("documents:list"),
  listJobs: () => ipcRenderer.invoke("jobs:list"),
  pickAndUploadDocuments: (options) => ipcRenderer.invoke("documents:pick-and-upload", options),
  pickFolder: () => ipcRenderer.invoke("documents:pick-folder"),
  uploadFolderFromPath: (folderPath, options) =>
    ipcRenderer.invoke("documents:upload-folder-from-path", folderPath, options),
  pickFolderAndUploadDocuments: (options) => ipcRenderer.invoke("documents:pick-folder-and-upload", options),
  uploadFiles: (filePaths, options) => ipcRenderer.invoke("documents:upload-files", filePaths, options),
  reindexDocument: (docId) => ipcRenderer.invoke("documents:reindex", docId),
  reindexDocuments: (docIds) => ipcRenderer.invoke("documents:reindex-bulk", docIds),
  removeDocument: (docId) => ipcRenderer.invoke("documents:remove", docId),
  removeDocuments: (docIds) => ipcRenderer.invoke("documents:remove-bulk", docIds),
  removeNotIngestedDocuments: () => ipcRenderer.invoke("documents:remove-not-ingested"),
  getCorpus: (docId) => ipcRenderer.invoke("corpus:get", docId),
  saveCorpus: (docId, jsonlContent) => ipcRenderer.invoke("corpus:save", docId, jsonlContent),
  getSettings: () => ipcRenderer.invoke("settings:get"),
  saveSettings: (settings) => ipcRenderer.invoke("settings:save", settings),
  testDatabaseConnection: (settings) => ipcRenderer.invoke("database:test-connection", settings),
  getDatabaseConnectionState: () => ipcRenderer.invoke("database:connection-state"),
  listOllamaModels: () => ipcRenderer.invoke("llm:list-ollama-models"),
  runHealthCheck: () => ipcRenderer.invoke("health:check"),
  exportDocumentsCsv: () => ipcRenderer.invoke("documents:export-csv"),
  onJobProgress: (handler) => {
    const wrappedHandler = (_event, payload) => handler(payload);
    ipcRenderer.on("jobs:progress", wrappedHandler);
    return () => ipcRenderer.removeListener("jobs:progress", wrappedHandler);
  }
});
