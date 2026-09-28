import type { ChatFeedbackRequest, ChatFeedbackRecord, ChatLocale, ChatMessage, ChatResponse, ChatSettings } from "@ragchat/shared";

const DEFAULT_BASE_URL = "http://localhost:8000";

export interface PostgresEnvironment {
  id: string;
  name: string;
  vectorBackend?: "postgres" | "sqlite_embedded" | "qdrant_embedded";
  dbHost: string;
  dbPort: number;
  dbName: string;
  dbUser: string;
  dbPassword: string;
  dbSchema: string;
  dbTableName: string;
  sqliteFilePath?: string;
  qdrantLocalPath?: string;
}

export interface AppSettings {
  activePostgresEnvironmentId: string;
  postgresEnvironments: PostgresEnvironment[];
}

export class ChatApiClient {
  private baseUrl: string;
  private apiKey: string;

  public constructor(baseUrl = DEFAULT_BASE_URL, apiKey = "") {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }

  public setCredentials(baseUrl: string, apiKey: string): void {
    this.baseUrl = baseUrl.trim().replace(/\/$/, "");
    this.apiKey = apiKey.trim();
  }

  private authHeaders(extra: Record<string, string> = {}): Record<string, string> {
    const headers: Record<string, string> = { ...extra };
    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey;
    }
    return headers;
  }

  public async sendMessage(
    message: string,
    history: ChatMessage[],
    language?: ChatLocale
  ): Promise<ChatResponse> {
    return this.post<ChatResponse>("/api/chat", {
      message,
      history,
      language,
      clientSource: "chatbot"
    });
  }

  public async submitFeedback(
    requestId: string,
    feedback: ChatFeedbackRequest
  ): Promise<ChatFeedbackRecord> {
    return this.post<ChatFeedbackRecord>(
      `/api/chat/requests/${encodeURIComponent(requestId)}/feedback`,
      feedback
    );
  }

  public async getChatSettings(): Promise<ChatSettings> {
    return this.get<ChatSettings>("/api/chat/settings");
  }

  public async saveChatSettings(settings: ChatSettings): Promise<ChatSettings> {
    return this.put<ChatSettings>("/api/chat/settings", settings);
  }

  public async healthCheck(): Promise<{ status: string; message: string }> {
    return this.get("/api/health");
  }

  public async getAppSettings(): Promise<AppSettings> {
    return this.get<AppSettings>("/api/settings");
  }

  public async saveAppSettings(settings: AppSettings): Promise<AppSettings> {
    return this.put<AppSettings>("/api/settings", settings);
  }

  public static async testConnection(
    baseUrl: string,
    apiKey: string
  ): Promise<{ ok: boolean; isAdmin: boolean; message: string }> {
    const url = baseUrl.trim().replace(/\/$/, "");
    try {
      const response = await fetch(`${url}/api/auth/me`, {
        headers: { "X-API-Key": apiKey.trim() }
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

  private async get<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      headers: this.authHeaders()
    });
    if (!response.ok) {
      throw new Error(`GET ${path} fehlgeschlagen: ${response.status}`);
    }
    return response.json() as Promise<T>;
  }

  private async post<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: this.authHeaders(body ? { "Content-Type": "application/json" } : {}),
      body: body ? JSON.stringify(body) : undefined
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(`POST ${path} fehlgeschlagen: ${response.status} ${text}`);
    }
    return response.json() as Promise<T>;
  }

  private async put<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "PUT",
      headers: this.authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body)
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(`PUT ${path} fehlgeschlagen: ${response.status} ${text}`);
    }
    return response.json() as Promise<T>;
  }
}
