import { useEffect, useRef, useState } from "react";
import type { ChatMessage, ChatSettings, ContextChunk, ChatResponse } from "@ragchat/shared";
import { useI18n } from "./i18n";

interface DisplayMessage {
  role: "user" | "assistant";
  content: string;
  sources?: ContextChunk[];
  metrics?: ChatResponse["metrics"];
}

interface ChatEnvSettings {
  activePostgresEnvironmentId: string;
  postgresEnvironments: Array<{
    id: string;
    name: string;
    dbHost: string;
    dbPort: number;
    dbName: string;
    dbUser: string;
    dbPassword: string;
    dbSchema: string;
    dbTableName: string;
  }>;
}

const DEFAULT_SETTINGS: ChatSettings = {
  llmApiKey: "ollama",
  llmBaseUrl: "http://localhost:11434/v1",
  llmModel: "llama3.2",
  temperature: 0.3,
  maxTokens: 2048,
  topK: 5,
  maxChunksPerSource: 2,
  minEvidenceSimilarity: 0.43,
  systemPrompt:
    "You are a helpful assistant that answers questions based on provided documents. Always cite the source file name when possible. Be precise and thorough.",
  encryptionKey: ""
};

export default function App() {
  const { t, locale, setLocale } = useI18n();
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [settings, setSettings] = useState<ChatSettings>(DEFAULT_SETTINGS);
  const [notification, setNotification] = useState<{ type: "error" | "success"; text: string } | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [appSettings, setAppSettings] = useState<ChatEnvSettings | null>(null);
  const [copiedMessageIndex, setCopiedMessageIndex] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    void loadSettings();
    void checkHealth();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  async function loadSettings(): Promise<void> {
    try {
      const loaded = await window.chatApi.getChatSettings();
      setSettings(loaded);
      const app = await window.chatApi.getSettings();
      setAppSettings(app);
    } catch {
      // API might not be reachable yet
    }
  }

  async function changeEnvironment(nextId: string): Promise<void> {
    if (!appSettings) return;
    try {
      const saved = await window.chatApi.saveSettings({
        ...appSettings,
        activePostgresEnvironmentId: nextId
      });
      setAppSettings(saved);
      showNotification("success", `Environment aktiv: ${nextId}`);
    } catch (err) {
      showNotification("error", `${t("notify.error")}: ${err}`);
    }
  }

  function normalizeHttpUrl(raw: string): string | null {
    let u = raw.trim();
    if (!u) return null;
    // Kaputte Extraktion: "ahttps://..." (z. B. Rest von <a href=...)
    if (/^ahttps?:\/\//i.test(u)) {
      u = u.slice(1);
    }
    // Alte Werte aus DB: .../index.md -> Root-Seite fürs Öffnen
    u = u.replace(/\/index\.(?:md|html?|htm)$/i, "/");
    if (/^https?:\/\//i.test(u)) return u;
    if (u.startsWith("www.")) return `https://${u}`;
    return null;
  }

  /** URLs aus MD/HTML: <a href="...">, href="...", [text](url), source: ... */
  function extractUrlFromChunkText(text: string): string | null {
    const t = text || "";
    const patterns: RegExp[] = [
      /<a\s[^>]*\bhref\s*=\s*["']([^"']+)["']/gi,
      /\bhref\s*=\s*["'](https?:\/\/[^"']+)["']/gi,
      /\[[^\]]*]\((https?:\/\/[^)\s]+)\)/g,
      /(?:^|\n)\s*(?:source|url)\s*:\s*(?:<a[^>]*\bhref\s*=\s*["'])?(https?:\/\/[^\s"'<>\]]+)/i,
      /(?:^|\n)\s*(?:source|url)\s*:\s*(https?:\/\/[^\s)\]]+)/i,
      /(?:^|\n)\s*(?:source|url)\s*:\s*(www\.[^\s)\]"'<>\]]+)/i
    ];
    for (const re of patterns) {
      re.lastIndex = 0;
      let m: RegExpExecArray | null;
      while ((m = re.exec(t)) !== null) {
        const g = m[1] ?? m[0];
        const n = normalizeHttpUrl(g);
        if (n) return n;
      }
    }
    const bare = t.match(/https?:\/\/[^\s)\]"'<>\]]+/i);
    if (bare?.[0]) {
      const n = normalizeHttpUrl(bare[0]);
      if (n) return n;
    }
    return null;
  }

  function sourceToUrl(src: ContextChunk): string | null {
    const fromFields = [src.sourcePath || "", src.source || "", src.fileName || ""];
    for (const raw of fromFields) {
      const candidate = raw.trim();
      if (!candidate) continue;
      const fromHtml = extractUrlFromChunkText(candidate);
      if (fromHtml) return fromHtml;
      const n = normalizeHttpUrl(candidate);
      if (n) return n;
    }

    return extractUrlFromChunkText(src.text || "");
  }

  async function checkHealth(): Promise<void> {
    try {
      await window.chatApi.healthCheck();
      setIsConnected(true);
    } catch {
      setIsConnected(false);
    }
  }

  function showNotification(type: "error" | "success", text: string): void {
    setNotification({ type, text });
    setTimeout(() => setNotification(null), 4000);
  }

  async function saveSettings(): Promise<void> {
    try {
      const saved = await window.chatApi.saveChatSettings(settings);
      setSettings(saved);
      showNotification("success", t("notify.settingsSaved"));
    } catch (err) {
      showNotification("error", `${t("notify.error")}: ${err}`);
    }
  }

  async function sendMessage(): Promise<void> {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    const userMessage: DisplayMessage = { role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    const history: ChatMessage[] = messages.map((m) => ({
      role: m.role,
      content: m.content
    }));

    try {
      const response = await window.chatApi.sendMessage(trimmed, history, locale);
      const assistantMessage: DisplayMessage = {
        role: "assistant",
        content: response.answer,
        sources: response.contextChunks,
        metrics: response.metrics
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage: DisplayMessage = {
        role: "assistant",
        content: `${t("chat.error")}: ${err}`
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendMessage();
    }
  }

  function handleTextareaInput(e: React.ChangeEvent<HTMLTextAreaElement>): void {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }

  function clearChat(): void {
    setMessages([]);
  }

  function formatElapsed(ms: number | undefined): string {
    if (!ms || ms <= 0) return "-";
    return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${ms} ms`;
  }

  async function copyMessageContent(content: string, idx: number): Promise<void> {
    const text = content?.trim() || "";
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopiedMessageIndex(idx);
      setTimeout(() => setCopiedMessageIndex((old) => (old === idx ? null : old)), 1400);
    } catch {
      showNotification("error", "Kopieren fehlgeschlagen");
    }
  }

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>{t("app.title")}</h1>
          <p>{t("app.subtitle")}</p>
        </div>

        <div className="sidebar-section">
          <h2>{t("sidebar.llmConfig")}</h2>

          {appSettings && appSettings.postgresEnvironments.length > 0 && (
            <div className="setting-field">
              <label>Environment</label>
              <select
                value={appSettings.activePostgresEnvironmentId}
                onChange={(e) => void changeEnvironment(e.target.value)}
              >
                {appSettings.postgresEnvironments.map((env: ChatEnvSettings["postgresEnvironments"][number]) => (
                  <option key={env.id} value={env.id}>
                    {env.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="setting-field">
            <label>{t("sidebar.apiKey")}</label>
            <input
              type="password"
              value={settings.llmApiKey}
              onChange={(e) => setSettings((s) => ({ ...s, llmApiKey: e.target.value }))}
              placeholder="sk-..."
            />
          </div>

          <div className="setting-field">
            <label>{t("sidebar.baseUrl")}</label>
            <input
              value={settings.llmBaseUrl}
              onChange={(e) => setSettings((s) => ({ ...s, llmBaseUrl: e.target.value }))}
            />
          </div>

          <div className="setting-field">
            <label>{t("sidebar.model")}</label>
            <input
              value={settings.llmModel}
              onChange={(e) => setSettings((s) => ({ ...s, llmModel: e.target.value }))}
            />
          </div>

          <div className="setting-field">
            <label>{t("sidebar.temperature")} ({settings.temperature})</label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="2"
              value={settings.temperature}
              onChange={(e) => setSettings((s) => ({ ...s, temperature: parseFloat(e.target.value) || 0 }))}
            />
          </div>

          <div className="setting-field">
            <label>{t("sidebar.maxTokens")}</label>
            <input
              type="number"
              value={settings.maxTokens}
              onChange={(e) => setSettings((s) => ({ ...s, maxTokens: parseInt(e.target.value) || 2048 }))}
            />
          </div>

          <div className="setting-field">
            <label>{t("sidebar.topK")}</label>
            <input
              type="number"
              min="1"
              max="20"
              value={settings.topK}
              onChange={(e) => setSettings((s) => ({ ...s, topK: parseInt(e.target.value) || 5 }))}
            />
          </div>

          <div className="setting-field">
            <label>{t("sidebar.maxChunksPerSource")}</label>
            <input
              type="number"
              min="1"
              max="20"
              value={settings.maxChunksPerSource ?? 2}
              onChange={(e) => setSettings((s) => ({ ...s, maxChunksPerSource: parseInt(e.target.value) || 2 }))}
            />
          </div>

          <div className="setting-field">
            <label>{t("sidebar.minEvidenceSimilarity")}</label>
            <input
              type="number"
              min="0"
              max="1"
              step="0.01"
              value={settings.minEvidenceSimilarity ?? 0.43}
              onChange={(e) => setSettings((s) => ({ ...s, minEvidenceSimilarity: Number(e.target.value) }))}
            />
          </div>

          <div className="setting-field">
            <label>{t("sidebar.systemPrompt")}</label>
            <textarea
              value={settings.systemPrompt}
              onChange={(e) => setSettings((s) => ({ ...s, systemPrompt: e.target.value }))}
              rows={3}
            />
          </div>

          <div className="setting-field">
            <label>{t("sidebar.language")}</label>
            <div className="lang-switcher">
              <button
                className={`lang-toggle ${locale === "de" ? "active" : ""}`}
                onClick={() => setLocale("de")}
                type="button"
              >
                DE
              </button>
              <button
                className={`lang-toggle ${locale === "en" ? "active" : ""}`}
                onClick={() => setLocale("en")}
                type="button"
              >
                EN
              </button>
            </div>
          </div>
        </div>

        <div className="sidebar-actions">
          <button className="btn btn-primary" onClick={() => void saveSettings()}>
            {t("sidebar.saveSettings")}
          </button>
          <button className="btn btn-danger" onClick={clearChat}>
            {t("sidebar.clearChat")}
          </button>
        </div>

        <div className="status-indicator">
          <span className={`status-dot ${isConnected ? "connected" : ""}`} />
          {isConnected ? t("status.connected") : t("status.disconnected")}
        </div>
      </aside>

      <main className="chat-area">
        {notification && (
          <div className={`notification ${notification.type}`}>{notification.text}</div>
        )}

        <div className="chat-messages">
          {messages.length === 0 && !isLoading && (
            <div className="empty-state">
              <div className="icon">&#128172;</div>
              <p>{t("chat.emptyState")}</p>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role}`}>
              <div className="message-avatar">{msg.role === "user" ? t("chat.you") : t("chat.ai")}</div>
              <div className="message-content">
                {msg.role === "assistant" && (
                  <button
                    type="button"
                    className={`copy-result-btn ${copiedMessageIndex === idx ? "copied" : ""}`}
                    onClick={() => void copyMessageContent(msg.content, idx)}
                    title="Ergebnis kopieren"
                    aria-label="Ergebnis kopieren"
                  >
                    {copiedMessageIndex === idx ? "✓" : "📋"}
                  </button>
                )}
                {msg.content}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="message-sources">
                    <details>
                      <summary>
                        {msg.sources.length} {t("chat.sourcesUsed")}
                      </summary>
                      {msg.sources.map((src, sIdx) => (
                        <div key={sIdx} className="source-item">
                          {src.fileName} | Chunk {src.chunkIndex} |{" "}
                          {(src.similarity * 100).toFixed(1)}% {t("chat.relevance")}
                          {sourceToUrl(src) && (
                            <>
                              {" "}
                              |{" "}
                              <button
                                type="button"
                                className="source-external-link"
                                onClick={() => {
                                  const u = sourceToUrl(src);
                                  if (u) {
                                    void window.chatApi.openExternal(u);
                                  }
                                }}
                              >
                                Website
                              </button>
                            </>
                          )}
                        </div>
                      ))}
                    </details>
                  </div>
                )}
                {msg.metrics && (
                  <div className="message-metrics">
                    <strong>{t("chat.metrics")}:</strong>{" "}
                    {t("chat.metrics.elapsed")}: {formatElapsed(msg.metrics.elapsedMs)} |{" "}
                    {t("chat.metrics.promptTokens")}: {msg.metrics.promptTokens ?? 0} |{" "}
                    {t("chat.metrics.completionTokens")}: {msg.metrics.completionTokens ?? 0} |{" "}
                    {t("chat.metrics.totalTokens")}: {msg.metrics.totalTokens ?? 0} |{" "}
                    {t("chat.metrics.tokensPerSecond")}:{" "}
                    {typeof msg.metrics.tokensPerSecond === "number"
                      ? msg.metrics.tokensPerSecond.toFixed(2)
                      : "0.00"}
                  </div>
                )}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="message assistant">
              <div className="message-avatar">{t("chat.ai")}</div>
              <div className="message-content">
                <div className="typing-indicator">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-area">
          <div className="chat-input-wrapper">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleTextareaInput}
              onKeyDown={handleKeyDown}
              placeholder={t("chat.placeholder")}
              rows={1}
              disabled={isLoading}
            />
            <button
              className="send-btn"
              onClick={() => void sendMessage()}
              disabled={isLoading || !input.trim()}
              title="Send"
            >
              &#10148;
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
