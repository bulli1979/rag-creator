const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("chatApi", {
  sendMessage: (message, history, language) => ipcRenderer.invoke("chat:send", message, history, language),
  getChatSettings: () => ipcRenderer.invoke("chat:settings:get"),
  saveChatSettings: (settings) => ipcRenderer.invoke("chat:settings:save", settings),
  healthCheck: () => ipcRenderer.invoke("chat:health"),
  getSettings: () => ipcRenderer.invoke("settings:get"),
  saveSettings: (settings) => ipcRenderer.invoke("settings:save", settings),
  openExternal: (url) => ipcRenderer.invoke("shell:open-external", url),
  submitFeedback: (requestId, feedback) =>
    ipcRenderer.invoke("chat:feedback:submit", requestId, feedback),
  connectionGet: () => ipcRenderer.invoke("connection:get"),
  connectionSave: (config) => ipcRenderer.invoke("connection:save", config),
  connectionTest: (config) => ipcRenderer.invoke("connection:test", config)
});
