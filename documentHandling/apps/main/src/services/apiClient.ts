import fs from "node:fs/promises";
import path from "node:path";
import type { AppSettings, DocumentRecord, JobRecord, ProgressEventPayload, UploadOptions } from "@rag/shared";

const DEFAULT_BASE_URL = "http://localhost:8000";
/** Standard: localhost kann bei Indexierung kurz blockiert wirken — 15s war zu knapp. */
const DEFAULT_REQUEST_TIMEOUT_MS = 60_000;
/** Große JSON-Listen (tausende Docs) / Corpus / CSV. */
const READ_HEAVY_TIMEOUT_MS = 180_000;
/** Viele Dateien auf einmal → RAM + Socket-Puffer; kleinere Batches = weniger ENOBUFS. */
const UPLOAD_FILES_PER_BATCH = 12;
/** Pause zwischen Batches: TCP-/Kernelpuffer können sich leeren (gegen ENOBUFS). */
const INTER_BATCH_DELAY_MS = 500;
/** Pro Batch (Multipart kann groß sein). */
const UPLOAD_BATCH_TIMEOUT_MS = 900_000;
/** Transiente Netzwerkfehler (Puffer, Reset, Timeout). */
const UPLOAD_BATCH_MAX_ATTEMPTS = 10;
const UPLOAD_RETRY_BASE_MS = 3_000;
const UPLOAD_RETRY_MAX_MS = 120_000;

export class ApiClient {
  private baseUrl: string;
  private abortController: AbortController | null = null;

  public constructor(baseUrl = DEFAULT_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  private static fetchErrorDetail(err: unknown): string {
    const parts: string[] = [];
    let cur: unknown = err;
    for (let i = 0; i < 6 && cur instanceof Error; i += 1) {
      if (cur.message.trim().length > 0) {
        parts.push(cur.message.trim());
      }
      cur = cur.cause;
    }
    return parts.length > 0 ? parts.join(" — ") : String(err);
  }

  private static async sleep(ms: number): Promise<void> {
    await new Promise((resolve) => {
      setTimeout(resolve, ms);
    });
  }

  /** Fehler bei Massen-Uploads, bei denen ein erneuter Versuch oft hilft. */
  private static isUploadTransientError(err: unknown): boolean {
    const blob = err instanceof Error ? `${err.name} ${err.message}` : String(err);
    const detail = ApiClient.fetchErrorDetail(err);
    const text = `${blob} ${detail}`;
    return /ENOBUFS|EPIPE|ECONNRESET|ETIMEDOUT|ESOCKETTIMEDOUT|socket hang up|fetch failed|ECONNABORTED|UND_ERR_SOCKET|Timeout nach|AbortError|network/i.test(
      text
    );
  }

  private async fetchWithTimeout(
    url: string,
    init: RequestInit = {},
    timeoutMs: number = DEFAULT_REQUEST_TIMEOUT_MS,
    errorContext: "default" | "upload" = "default"
  ): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, {
        ...init,
        signal: init.signal ?? controller.signal
      });
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        const msg = `Anfrage-Timeout nach ${timeoutMs / 1000}s: ${url}`;
        if (errorContext === "upload" && ApiClient.isUploadTransientError(err)) {
          throw new Error(`${msg} (Upload — erneuter Versuch möglich)`);
        }
        throw new Error(msg);
      }
      const isFetchFailed =
        err instanceof TypeError &&
        (err.message === "fetch failed" || err.message.includes("fetch failed"));
      if (isFetchFailed) {
        const detail = ApiClient.fetchErrorDetail(err);
        if (errorContext === "upload") {
          if (/ENOBUFS|No buffer space|EPIPE|ECONNRESET/i.test(detail)) {
            throw new Error(
              `Upload: Netzwerk-/Systempuffer kurz voll (z. B. ENOBUFS). API läuft oft weiter — Pause und Wiederholung. ${detail}`
            );
          }
          throw new Error(
            `Upload fehlgeschlagen gegen ${this.baseUrl}. Prüfe documentApi; bei vielen Dateien erneut versuchen. ${detail}`
          );
        }
        throw new Error(
          `API nicht erreichbar unter ${this.baseUrl}. documentApi (FastAPI) gestartet? ${detail}`
        );
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  public async listDocuments(): Promise<DocumentRecord[]> {
    return this.get<DocumentRecord[]>("/api/documents", READ_HEAVY_TIMEOUT_MS);
  }

  public async listJobs(): Promise<JobRecord[]> {
    return this.get<JobRecord[]>("/api/jobs", READ_HEAVY_TIMEOUT_MS);
  }

  /**
   * @param pathForFormFilename Optional: z. B. relativer Pfad unter dem gewählten Ordner (eindeutige Namen in Unterordnern).
   * Ordner mit tausenden Dateien: mehrere Requests à {@link UPLOAD_FILES_PER_BATCH} Dateien (RAM-Schonung).
   */
  public async uploadFiles(
    filePaths: string[],
    options: UploadOptions,
    pathForFormFilename?: (absolutePath: string) => string
  ): Promise<{ queuedDocIds: string[]; skippedDocIds: string[]; messages: string[] }> {
    if (filePaths.length === 0) {
      return { queuedDocIds: [], skippedDocIds: [], messages: [] };
    }
    const totalBatches = Math.ceil(filePaths.length / UPLOAD_FILES_PER_BATCH);
    const allQueued: string[] = [];
    const allSkipped: string[] = [];
    const allMessages: string[] = [];
    for (let offset = 0; offset < filePaths.length; offset += UPLOAD_FILES_PER_BATCH) {
      const batchIndex = Math.floor(offset / UPLOAD_FILES_PER_BATCH) + 1;
      const slice = filePaths.slice(offset, offset + UPLOAD_FILES_PER_BATCH);
      console.log(
        `[apiClient] upload batch ${batchIndex}/${totalBatches}: ${slice.length} Dateien (Offset ${offset})`
      );
      const part = await this.uploadFilesSingleRequestWithRetry(slice, options, pathForFormFilename, batchIndex);
      allQueued.push(...part.queuedDocIds);
      if (part.skippedDocIds?.length) {
        allSkipped.push(...part.skippedDocIds);
      }
      if (part.messages?.length) {
        allMessages.push(...part.messages);
        for (const m of part.messages) {
          console.log(`[apiClient] upload: ${m}`);
        }
      }
      if (offset + UPLOAD_FILES_PER_BATCH < filePaths.length) {
        await ApiClient.sleep(INTER_BATCH_DELAY_MS);
      }
    }
    console.log(
      `[apiClient] upload fertig: ${allQueued.length} neu eingeplant, ${allSkipped.length} uebersprungen`
    );
    return { queuedDocIds: allQueued, skippedDocIds: allSkipped, messages: allMessages };
  }

  private async uploadFilesSingleRequestWithRetry(
    filePaths: string[],
    options: UploadOptions,
    pathForFormFilename: ((absolutePath: string) => string) | undefined,
    batchIndex: number
  ): Promise<{
    queuedDocIds: string[];
    skippedDocIds?: string[];
    messages?: string[];
  }> {
    let lastErr: unknown;
    for (let attempt = 1; attempt <= UPLOAD_BATCH_MAX_ATTEMPTS; attempt += 1) {
      try {
        return await this.uploadFilesSingleRequest(filePaths, options, pathForFormFilename);
      } catch (err) {
        lastErr = err;
        const msg = err instanceof Error ? err.message : String(err);
        const transient = ApiClient.isUploadTransientError(err);
        console.warn(
          `[apiClient] batch ${batchIndex} Versuch ${attempt}/${UPLOAD_BATCH_MAX_ATTEMPTS} fehlgeschlagen (transient=${transient}): ${msg}`
        );
        if (!transient || attempt === UPLOAD_BATCH_MAX_ATTEMPTS) {
          break;
        }
        const backoff = Math.min(
          UPLOAD_RETRY_MAX_MS,
          Math.round(UPLOAD_RETRY_BASE_MS * 1.55 ** (attempt - 1))
        );
        console.log(`[apiClient] batch ${batchIndex}: warte ${backoff}ms vor erneutem Versuch …`);
        await ApiClient.sleep(backoff);
      }
    }
    throw lastErr instanceof Error ? lastErr : new Error(String(lastErr));
  }

  private async uploadFilesSingleRequest(
    filePaths: string[],
    options: UploadOptions,
    pathForFormFilename?: (absolutePath: string) => string
  ): Promise<{
    queuedDocIds: string[];
    skippedDocIds?: string[];
    messages?: string[];
  }> {
    const formData = new FormData();

    for (const filePath of filePaths) {
      const buffer = await fs.readFile(filePath);
      const blob = new Blob([buffer]);
      const fileName = pathForFormFilename ? pathForFormFilename(filePath) : path.basename(filePath);
      formData.append("files", blob, fileName);
    }

    formData.append("tags", options.tags.join(","));
    formData.append("source", options.source || "lokal");

    const response = await this.fetchWithTimeout(
      `${this.baseUrl}/api/documents/upload`,
      {
        method: "POST",
        body: formData
      },
      UPLOAD_BATCH_TIMEOUT_MS,
      "upload"
    );
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Upload fehlgeschlagen: ${response.status} ${body}`);
    }
    const data = (await response.json()) as {
      queuedDocIds: string[];
      skippedDocIds?: string[];
      messages?: string[];
    };
    return {
      queuedDocIds: data.queuedDocIds ?? [],
      skippedDocIds: data.skippedDocIds ?? [],
      messages: data.messages ?? []
    };
  }

  public async removeDocument(docId: string): Promise<{ ok: true }> {
    await this.delete(`/api/documents/${encodeURIComponent(docId)}`);
    return { ok: true };
  }

  public async removeDocuments(docIds: string[]): Promise<{ ok: true }> {
    await this.post("/api/documents/remove-bulk", { docIds });
    return { ok: true };
  }

  public async reindexDocument(docId: string): Promise<{ ok: true }> {
    await this.post(`/api/documents/${encodeURIComponent(docId)}/reindex`);
    return { ok: true };
  }

  public async reindexDocuments(docIds: string[]): Promise<{ ok: true }> {
    await this.post("/api/documents/reindex-bulk", { docIds });
    return { ok: true };
  }

  public async getCorpus(docId: string): Promise<string> {
    const response = await this.fetchWithTimeout(
      `${this.baseUrl}/api/corpus/${encodeURIComponent(docId)}`,
      {},
      READ_HEAVY_TIMEOUT_MS
    );
    if (!response.ok) {
      throw new Error(`Corpus laden fehlgeschlagen: ${response.status}`);
    }
    return response.text();
  }

  public async saveCorpus(docId: string, jsonlContent: string): Promise<{ ok: true }> {
    await this.put(`/api/corpus/${encodeURIComponent(docId)}`, { content: jsonlContent });
    return { ok: true };
  }

  public async getSettings(): Promise<AppSettings> {
    return this.get<AppSettings>("/api/settings");
  }

  public async saveSettings(settings: AppSettings): Promise<AppSettings> {
    return this.put<AppSettings>("/api/settings", settings);
  }

  public async testDatabaseConnection(
    settings?: AppSettings
  ): Promise<{ status: "ok" | "error"; message: string }> {
    return this.post<{ status: "ok" | "error"; message: string }>("/api/database/test-connection", {
      settings: settings ?? null
    });
  }

  public async getDatabaseConnectionState(): Promise<{ ready: boolean }> {
    return this.get<{ ready: boolean }>("/api/database/connection-state");
  }

  public async runHealthCheck(): Promise<{
    postgres: { status: "ok" | "error"; message: string };
    pythonWorker: { status: "ok" | "error"; message: string };
  }> {
    return this.get("/api/health");
  }

  public async exportDocumentsCsv(): Promise<string> {
    const response = await this.fetchWithTimeout(
      `${this.baseUrl}/api/documents/export/csv`,
      {},
      READ_HEAVY_TIMEOUT_MS
    );
    if (!response.ok) {
      throw new Error(`CSV Export fehlgeschlagen: ${response.status}`);
    }
    return response.text();
  }

  public subscribeProgress(handler: (event: ProgressEventPayload) => void): () => void {
    this.abortController = new AbortController();
    const signal = this.abortController.signal;

    const connect = () => {
      fetch(`${this.baseUrl}/api/jobs/progress`, { signal, headers: { Accept: "text/event-stream" } })
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
                    // skip malformed events
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
      this.abortController?.abort();
      this.abortController = null;
    };
  }

  private async get<T>(path: string, timeoutMs: number = DEFAULT_REQUEST_TIMEOUT_MS): Promise<T> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}${path}`, {}, timeoutMs);
    if (!response.ok) {
      throw new Error(`GET ${path} fehlgeschlagen: ${response.status}`);
    }
    return response.json() as Promise<T>;
  }

  private async post<T>(path: string, body?: unknown): Promise<T> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(`POST ${path} fehlgeschlagen: ${response.status} ${text}`);
    }
    return response.json() as Promise<T>;
  }

  private async put<T>(path: string, body: unknown): Promise<T> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}${path}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(`PUT ${path} fehlgeschlagen: ${response.status} ${text}`);
    }
    return response.json() as Promise<T>;
  }

  private async delete(path: string): Promise<void> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}${path}`, { method: "DELETE" });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(`DELETE ${path} fehlgeschlagen: ${response.status} ${text}`);
    }
  }
}
