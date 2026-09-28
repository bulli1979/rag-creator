import { ipcMain } from "electron";
import type { ChatFeedbackRequest, ChatLocale, ChatMessage, ChatSettings } from "@ragchat/shared";
import { ChatApiClient, type AppSettings } from "./services/chatApiClient.js";
import {
  loadConnectionConfig,
  saveConnectionConfig,
  type ConnectionConfig
} from "./services/connectionConfigStore.js";

export function registerIpcHandlers(getApiClient: () => ChatApiClient): void {
  ipcMain.handle("connection:get", async () => loadConnectionConfig());

  ipcMain.handle("connection:save", async (_event, config: ConnectionConfig) => {
    const saved = await saveConnectionConfig(config);
    getApiClient().setCredentials(saved.apiBaseUrl, saved.apiKey);
    return saved;
  });

  ipcMain.handle("connection:test", async (_event, config: ConnectionConfig) => {
    return ChatApiClient.testConnection(config.apiBaseUrl, config.apiKey);
  });

  ipcMain.handle(
    "chat:send",
    async (
      _event,
      message: string,
      history: ChatMessage[],
      language?: ChatLocale
    ) => {
      return getApiClient().sendMessage(message, history, language);
    }
  );

  ipcMain.handle("chat:settings:get", () => {
    return getApiClient().getChatSettings();
  });

  ipcMain.handle("chat:settings:save", async (_event, settings: ChatSettings) => {
    return getApiClient().saveChatSettings(settings);
  });

  ipcMain.handle("chat:health", () => {
    return getApiClient().healthCheck();
  });

  ipcMain.handle("settings:get", () => {
    return getApiClient().getAppSettings();
  });

  ipcMain.handle("settings:save", async (_event, settings: AppSettings) => {
    return getApiClient().saveAppSettings(settings);
  });

  ipcMain.handle("shell:open-external", async (_event, url: string) => {
    const u = String(url ?? "").trim();
    if (!/^https?:\/\//i.test(u)) {
      throw new Error("Nur http(s)-URLs erlaubt.");
    }
    const { shell } = await import("electron");
    await shell.openExternal(u);
  });

  ipcMain.handle(
    "chat:feedback:submit",
    async (_event, requestId: string, feedback: ChatFeedbackRequest) => {
      return getApiClient().submitFeedback(requestId, feedback);
    }
  );
}
