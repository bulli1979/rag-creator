/**
 * Browser-Bridge für die Admin-UI ohne Electron.
 * Stellt dieselbe `window.ragApi`-Oberfläche bereit (fetch + X-API-Key + localStorage + Backend-Sync).
 */
import type { AppSettings, ProgressEventPayload, UploadOptions } from "@rag/shared";
import {
  getOrCreateAdminWebClientId,
  logAdminWebEvent,
  syncConnectionToBackend
} from "./adminWebStore";
import type {
  ChatSettings,
  ConnectionConfig,
  ConnectionTestResult,
  DocumentUploadResult,
  OllamaModelsResult
} from "./types/global";
import type { BatchRun } from "./BulkTestPanel";

const STORAGE_KEY = "rag_admin_web_connection_v1";
const DEFAULT_BASE_URL = "http://localhost:8000";
const UPLOAD_FILES_PER_BATCH = 12;
const FOLDER_TOKEN_PREFIX = "browser-folder:";

type UploadResult = DocumentUploadResult & { fileCount?: number };

function authHeaders(apiKey: string, extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  return headers;
}

async function readJson<T>(response: Response, label: string): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${label} fehlgeschlagen: ${response.status} ${text}`);
  }
  return response.json() as Promise<T>;
}

function pickFiles(options: { multiple?: boolean; directory?: boolean }): Promise<File[]> {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.multiple = options.multiple !== false;
    if (options.directory) {
      input.setAttribute("webkitdirectory", "");
      input.setAttribute("directory", "");
    }
    input.style.display = "none";
    document.body.appendChild(input);
    input.addEventListener(
      "change",
      () => {
        const files = Array.from(input.files ?? []);
        input.remove();
        resolve(files);
      },
      { once: true }
    );
    input.addEventListener(
      "cancel",
      () => {
        input.remove();
        resolve([]);
      },
      { once: true }
    );
    input.click();
  });
}

export function installBrowserRagApi(): void {
  if (typeof window === "undefined" || window.ragApi) {
    return;
  }

  let baseUrl = DEFAULT_BASE_URL;
  let apiKey = "";
  let progressAbort: AbortController | null = null;
  const folderFiles = new Map<string, File[]>();

  function setCredentials(url: string, key: string): void {
    baseUrl = url.trim().replace(/\/$/, "") || DEFAULT_BASE_URL;
    apiKey = key.trim();
  }

  async function apiGet<T>(path: string): Promise<T> {
    const response = await fetch(`${baseUrl}${path}`, { headers: authHeaders(apiKey) });
    return readJson<T>(response, `GET ${path}`);
  }

  async function apiSend<T>(method: string, path: string, body?: unknown): Promise<T> {
    const response = await fetch(`${baseUrl}${path}`, {
      method,
      headers: authHeaders(apiKey, body !== undefined ? { "Content-Type": "application/json" } : {}),
      body: body !== undefined ? JSON.stringify(body) : undefined
    });
    return readJson<T>(response, `${method} ${path}`);
  }

  async function apiDelete(path: string): Promise<void> {
    const response = await fetch(`${baseUrl}${path}`, {
      method: "DELETE",
      headers: authHeaders(apiKey)
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(`DELETE ${path} fehlgeschlagen: ${response.status} ${text}`);
    }
  }

  async function uploadFileBatch(files: File[], options: UploadOptions): Promise<UploadResult> {
    if (files.length === 0) {
      return { queuedDocIds: [], skippedDocIds: [], messages: [] };
    }
    const allQueued: string[] = [];
    const allSkipped: string[] = [];
    const allMessages: string[] = [];

    for (let offset = 0; offset < files.length; offset += UPLOAD_FILES_PER_BATCH) {
      const slice = files.slice(offset, offset + UPLOAD_FILES_PER_BATCH);
      const formData = new FormData();
      for (const file of slice) {
        const name =
          (file as File & { webkitRelativePath?: string }).webkitRelativePath?.replace(/^\/+/, "") ||
          file.name;
        formData.append("files", file, name);
      }
      formData.append("tags", (options.tags ?? []).join(","));
      formData.append("source", options.source || "lokal");
      if (options.embeddingModel?.trim()) {
        formData.append("embeddingModel", options.embeddingModel.trim());
      }

      const response = await fetch(`${baseUrl}/api/documents/upload`, {
        method: "POST",
        headers: authHeaders(apiKey),
        body: formData
      });
      const part = await readJson<{
        queuedDocIds?: string[];
        skippedDocIds?: string[];
        messages?: string[];
      }>(response, "Upload");
      allQueued.push(...(part.queuedDocIds ?? []));
      allSkipped.push(...(part.skippedDocIds ?? []));
      allMessages.push(...(part.messages ?? []));
    }

    return {
      queuedDocIds: allQueued,
      skippedDocIds: allSkipped,
      messages: allMessages,
      fileCount: files.length
    };
  }

  async function testConnection(config: ConnectionConfig): Promise<ConnectionTestResult> {
    const url = config.apiBaseUrl.trim().replace(/\/$/, "");
    try {
      const response = await fetch(`${url}/api/auth/me`, {
        headers: { "X-API-Key": config.apiKey.trim() }
      });
      if (!response.ok) {
        const text = await response.text();
        return { ok: false, isAdmin: false, message: `HTTP ${response.status}: ${text}` };
      }
      const data = (await response.json()) as { isAdmin?: boolean; label?: string };
      return {
        ok: true,
        isAdmin: Boolean(data.isAdmin),
        message: data.label ? `Verbunden (${data.label})` : "Verbunden"
      };
    } catch (err) {
      return {
        ok: false,
        isAdmin: false,
        message: err instanceof Error ? err.message : String(err)
      };
    }
  }

  window.ragApi = {
    connectionGet: async () => {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) {
          return null;
        }
        const parsed = JSON.parse(raw) as Partial<ConnectionConfig>;
        const apiBaseUrl = String(parsed.apiBaseUrl ?? "").trim();
        const key = String(parsed.apiKey ?? "").trim();
        if (!apiBaseUrl || !key) {
          return null;
        }
        return { apiBaseUrl, apiKey: key };
      } catch {
        return null;
      }
    },

    connectionSave: async (config) => {
      const normalized: ConnectionConfig = {
        apiBaseUrl: config.apiBaseUrl.trim().replace(/\/$/, ""),
        apiKey: config.apiKey.trim()
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
      setCredentials(normalized.apiBaseUrl, normalized.apiKey);
      void syncConnectionToBackend(normalized.apiBaseUrl, normalized.apiKey, normalized);
      void logAdminWebEvent(normalized.apiBaseUrl, normalized.apiKey, "connection_saved", {
        apiBaseUrl: normalized.apiBaseUrl,
        clientId: getOrCreateAdminWebClientId()
      });
      return normalized;
    },

    connectionTest: (config) => testConnection(config),

    listDocuments: () => apiGet("/api/documents"),
    listJobs: () => apiGet("/api/jobs"),

    pickAndUploadDocuments: async (options) => {
      const files = await pickFiles({ multiple: true, directory: false });
      if (files.length === 0) {
        return { queuedDocIds: [], skippedDocIds: [], messages: ["Abgebrochen."] };
      }
      return uploadFileBatch(files, options);
    },

    pickFolder: async () => {
      const files = await pickFiles({ multiple: true, directory: true });
      if (files.length === 0) {
        return { canceled: true as const };
      }
      const token = `${FOLDER_TOKEN_PREFIX}${Date.now()}`;
      folderFiles.set(token, files);
      const label =
        (files[0] as File & { webkitRelativePath?: string }).webkitRelativePath?.split("/")[0] ||
        "Ordner";
      return { canceled: false as const, folderPath: `${token}|${label}` };
    },

    uploadFolderFromPath: async (folderPath, options) => {
      const token = folderPath.split("|")[0] ?? folderPath;
      const files = folderFiles.get(token);
      if (!files?.length) {
        throw new Error(
          "Ordnerauswahl im Browser abgelaufen — bitte Ordner erneut wählen und einlesen."
        );
      }
      const result = await uploadFileBatch(files, options);
      folderFiles.delete(token);
      return { ...result, fileCount: files.length };
    },

    pickFolderAndUploadDocuments: async (options) => {
      const pick = await window.ragApi.pickFolder();
      if (pick.canceled) {
        return { queuedDocIds: [], skippedDocIds: [], messages: [], fileCount: 0 };
      }
      return window.ragApi.uploadFolderFromPath(pick.folderPath, options);
    },

    uploadFiles: async (filePaths, options) => {
      // Electron übergibt Pfade; im Browser nur sinnvoll, wenn zuvor Files geparkt wurden.
      const files: File[] = [];
      for (const p of filePaths) {
        if (p.startsWith(FOLDER_TOKEN_PREFIX)) {
          const stored = folderFiles.get(p.split("|")[0] ?? p);
          if (stored) {
            files.push(...stored);
          }
        }
      }
      if (files.length === 0) {
        throw new Error(
          "Im Browser bitte Dateien über „Dokumente hinzufügen“, Ordner-Einlesen oder Drag&Drop laden."
        );
      }
      return uploadFileBatch(files, options);
    },

    uploadBrowserFiles: (files, options) => uploadFileBatch(files, options),

    reindexDocument: async (docId) => {
      await apiSend("POST", `/api/documents/${encodeURIComponent(docId)}/reindex`);
      return { ok: true as const };
    },
    reindexDocuments: async (docIds) => {
      await apiSend("POST", "/api/documents/reindex-bulk", { docIds });
      return { ok: true as const };
    },
    startFamilyReindex: (body) =>
      apiSend("POST", "/api/documents/family-reindex", body || {}),
    getFamilyReindexStatus: () => apiGet("/api/documents/family-reindex/status"),
    cancelFamilyReindex: () => apiSend("POST", "/api/documents/family-reindex/cancel"),
    removeDocument: async (docId) => {
      await apiDelete(`/api/documents/${encodeURIComponent(docId)}`);
      return { ok: true as const };
    },
    removeDocuments: async (docIds) => {
      await apiSend("POST", "/api/documents/remove-bulk", { docIds });
      return { ok: true as const };
    },
    removeNotIngestedDocuments: () =>
      apiSend<{ ok: true; removedCount: number }>("POST", "/api/documents/remove-not-ingested"),

    getCorpus: async (docId) => {
      const response = await fetch(`${baseUrl}/api/corpus/${encodeURIComponent(docId)}`, {
        headers: authHeaders(apiKey)
      });
      if (!response.ok) {
        throw new Error(`Corpus laden fehlgeschlagen: ${response.status}`);
      }
      return response.text();
    },
    saveCorpus: async (docId, jsonlContent) => {
      await apiSend("PUT", `/api/corpus/${encodeURIComponent(docId)}`, { content: jsonlContent });
      return { ok: true as const };
    },

    getSettings: () => apiGet<AppSettings>("/api/settings"),
    saveSettings: (settings) => apiSend<AppSettings>("PUT", "/api/settings", settings),
    testDatabaseConnection: (settings) =>
      apiSend("POST", "/api/database/test-connection", { settings: settings ?? null }),
    getDatabaseConnectionState: () => apiGet("/api/database/connection-state"),

    listOllamaModels: () => apiGet<OllamaModelsResult>("/api/llm/ollama/models"),
    getChatSettings: () => apiGet<ChatSettings>("/api/chat/settings"),
    saveChatSettings: (settings) => apiSend<ChatSettings>("PUT", "/api/chat/settings", settings),

    runHealthCheck: () => apiGet("/api/health"),

    exportDocumentsCsv: async () => {
      const response = await fetch(`${baseUrl}/api/documents/export/csv`, {
        headers: authHeaders(apiKey)
      });
      if (!response.ok) {
        throw new Error(`CSV Export fehlgeschlagen: ${response.status}`);
      }
      return response.text();
    },

    onJobProgress: (handler) => {
      progressAbort?.abort();
      progressAbort = new AbortController();
      const signal = progressAbort.signal;
      const keyQuery = apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : "";

      const connect = (): void => {
        fetch(`${baseUrl}/api/jobs/progress${keyQuery}`, {
          signal,
          headers: authHeaders(apiKey, { Accept: "text/event-stream" })
        })
          .then(async (response) => {
            if (!response.ok || !response.body) {
              return;
            }
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            while (true) {
              const { done, value } = await reader.read();
              if (done) {
                break;
              }
              buffer += decoder.decode(value, { stream: true });
              const lines = buffer.split("\n");
              buffer = lines.pop() ?? "";
              let currentEventType = "";
              for (const line of lines) {
                if (line.startsWith("event:")) {
                  currentEventType = line.slice(6).trim();
                } else if (line.startsWith("data:") && currentEventType === "progress") {
                  const data = line.slice(5).trim();
                  if (data) {
                    try {
                      handler(JSON.parse(data) as ProgressEventPayload);
                    } catch {
                      // ignore
                    }
                  }
                  currentEventType = "";
                }
              }
            }
            if (!signal.aborted) {
              setTimeout(connect, 2000);
            }
          })
          .catch(() => {
            if (!signal.aborted) {
              setTimeout(connect, 2000);
            }
          });
      };

      connect();
      return () => {
        progressAbort?.abort();
        progressAbort = null;
      };
    },

    listApiKeys: () => apiGet("/api/admin/keys"),
    createApiKey: (label, isAdmin = false) =>
      apiSend("POST", "/api/admin/keys", { label, isAdmin }),
    revokeApiKey: async (keyId) => {
      await apiDelete(`/api/admin/keys/${encodeURIComponent(keyId)}`);
      return { ok: true as const };
    },

    startBatchTest: async (file, options): Promise<BatchRun> => {
      const formData = new FormData();
      formData.append("file", file, file.name);
      formData.append("evaluateAnswers", options?.evaluateAnswers ? "true" : "false");
      if (options?.language) {
        formData.append("language", options.language);
      }
      if (options?.settingsId) {
        formData.append("settingsId", options.settingsId);
      }
      if (options?.settingsName) {
        formData.append("settingsName", options.settingsName);
      }
      if (options?.chatSettings) {
        formData.append("chatSettingsJson", JSON.stringify(options.chatSettings));
      }
      if (options?.evalJudge) {
        formData.append("evalJudgeJson", JSON.stringify(options.evalJudge));
      }
      if (options?.environmentId) {
        formData.append("environmentId", options.environmentId);
      }
      if (options?.familyId) {
        formData.append("familyId", options.familyId);
      }
      if (options?.runAllInstances) {
        formData.append("runAllInstances", "true");
      }
      if (options?.questionsFile) {
        formData.append("questionsFile", options.questionsFile, options.questionsFile.name);
      }
      const response = await fetch(`${baseUrl}/api/batch-test/runs`, {
        method: "POST",
        headers: authHeaders(apiKey),
        body: formData
      });
      return readJson<BatchRun>(response, "POST /api/batch-test/runs");
    },

    getBatchTestRun: (runId): Promise<BatchRun> =>
      apiGet<BatchRun>(`/api/batch-test/runs/${encodeURIComponent(runId)}`),

    listBatchTestRuns: (params): Promise<{ runs: BatchRun[] }> => {
      const qs = new URLSearchParams();
      if (params?.limit) qs.set("limit", String(params.limit));
      if (params?.sortBy) qs.set("sortBy", params.sortBy);
      if (params?.sortDir) qs.set("sortDir", params.sortDir);
      const suffix = qs.toString() ? `?${qs}` : "";
      return apiGet(`/api/batch-test/runs${suffix}`);
    },

    deleteBatchTestRun: async (runId) => {
      await apiDelete(`/api/batch-test/runs/${encodeURIComponent(runId)}`);
      return { ok: true as const };
    },

    cancelBatchTest: (runId): Promise<BatchRun> =>
      apiSend<BatchRun>("POST", `/api/batch-test/runs/${encodeURIComponent(runId)}/cancel`),

    getBatchTestDefaults: () => apiGet("/api/batch-test/defaults"),

    listBatchTestSettings: () => apiGet("/api/batch-test/settings"),

    saveBatchTestSettings: (body) => apiSend("POST", "/api/batch-test/settings", body),

    deleteBatchTestSettings: async (settingsId) => {
      await apiDelete(`/api/batch-test/settings/${encodeURIComponent(settingsId)}`);
      return { ok: true as const };
    },

    copyBatchTestSettingsFromRun: (runId, name) =>
      apiSend("POST", `/api/batch-test/settings/from-run/${encodeURIComponent(runId)}`, {
        name: name || null
      })
  };

  // Bereits gespeicherte Verbindung sofort anwenden
  void window.ragApi.connectionGet().then((stored) => {
    if (stored) {
      setCredentials(stored.apiBaseUrl, stored.apiKey);
    }
  });
}
