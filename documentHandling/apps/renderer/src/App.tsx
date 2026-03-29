import { useEffect, useMemo, useRef, useState } from "react";
import {
  defaultAppSettings,
  type AppSettings,
  type DocumentRecord,
  type PostgresEnvironment,
  type ProgressEventPayload
} from "@rag/shared";
import { useI18n } from "./i18n";

interface UploadFormState {
  tagsInput: string;
  source: string;
}

function parseTags(tagsInput: string): string[] {
  return tagsInput
    .split(",")
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
}

function formatErrorDetail(err: unknown): string {
  if (err instanceof Error) {
    const c = err.cause;
    const causeStr = c instanceof Error ? ` | Cause: ${c.message}` : "";
    return `${err.name}: ${err.message}${causeStr}`;
  }
  return typeof err === "object" && err !== null ? JSON.stringify(err) : String(err);
}

function getActivePostgresEnv(settings: AppSettings): PostgresEnvironment | undefined {
  return settings.postgresEnvironments.find((env) => env.id === settings.activePostgresEnvironmentId);
}

function updateActivePostgresEnv(settings: AppSettings, patch: Partial<PostgresEnvironment>): AppSettings {
  const activeId = settings.activePostgresEnvironmentId;
  return {
    ...settings,
    postgresEnvironments: settings.postgresEnvironments.map((env) =>
      env.id === activeId ? { ...env, ...patch } : env
    )
  };
}

function addPostgresEnvironment(settings: AppSettings): AppSettings {
  const newId = crypto.randomUUID();
  const template = getActivePostgresEnv(settings) ?? settings.postgresEnvironments[0];
  if (!template) {
    return settings;
  }
  const clone: PostgresEnvironment = {
    ...template,
    id: newId,
    name: `${template.name} (Kopie)`
  };
  return {
    ...settings,
    postgresEnvironments: [...settings.postgresEnvironments, clone],
    activePostgresEnvironmentId: newId
  };
}

function removePostgresEnvironment(settings: AppSettings, id: string): AppSettings {
  const remaining = settings.postgresEnvironments.filter((env) => env.id !== id);
  const firstRemaining = remaining[0];
  if (remaining.length === 0 || !firstRemaining) {
    return settings;
  }
  const nextActive =
    settings.activePostgresEnvironmentId === id ? firstRemaining.id : settings.activePostgresEnvironmentId;
  return {
    ...settings,
    postgresEnvironments: remaining,
    activePostgresEnvironmentId: nextActive
  };
}

export default function App() {
  const { t, locale, setLocale } = useI18n();
  const tRef = useRef(t);
  tRef.current = t;
  const [activeTab, setActiveTab] = useState<"documents" | "settings">("documents");
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [searchText, setSearchText] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [tagFilter, setTagFilter] = useState<string>("all");
  const [uploadFormState, setUploadFormState] = useState<UploadFormState>({ tagsInput: "", source: "lokal" });
  const [settings, setSettings] = useState<AppSettings>(defaultAppSettings);
  const [isConnectionReady, setIsConnectionReady] = useState(false);
  const [healthMessage, setHealthMessage] = useState("");
  const [connectionTestRunning, setConnectionTestRunning] = useState(false);
  const [connectionTestLastResponse, setConnectionTestLastResponse] = useState<string>("");
  const [corpusDocumentId, setCorpusDocumentId] = useState<string | null>(null);
  const [corpusContent, setCorpusContent] = useState("");
  const [progressEvents, setProgressEvents] = useState<ProgressEventPayload[]>([]);
  const [isDropActive, setIsDropActive] = useState(false);
  const [selectedFolderPath, setSelectedFolderPath] = useState<string | null>(null);
  const [folderIngestRunning, setFolderIngestRunning] = useState(false);
  const [folderActionLog, setFolderActionLog] = useState<string>("");

  function appendFolderLog(line: string): void {
    const stamp = new Date().toLocaleTimeString();
    const row = `[${stamp}] ${line}`;
    console.info(`[rag folder] ${row}`);
    setFolderActionLog((prev) => {
      const next = prev ? `${prev}\n${row}` : row;
      return next.length > 6000 ? next.slice(-6000) : next;
    });
  }

  async function reloadDocuments(): Promise<void> {
    if (!window.ragApi) {
      return;
    }
    const listedDocuments = await window.ragApi.listDocuments();
    setDocuments(listedDocuments);
  }

  useEffect(() => {
    const api = typeof window !== "undefined" ? window.ragApi : undefined;
    if (!api) {
      setHealthMessage(tRef.current("settings.loadError"));
      return undefined;
    }

    let alive = true;
    void reloadDocuments().catch(() => {
      if (alive) {
        setDocuments([]);
      }
    });

    void (async () => {
      let loadedSettings: AppSettings;
      try {
        loadedSettings = await api.getSettings();
      } catch (err: unknown) {
        console.error("getSettings", err);
        if (!alive) {
          return;
        }
        loadedSettings = defaultAppSettings;
        setSettings(defaultAppSettings);
        setHealthMessage(tRef.current("settings.loadError"));
      }
      if (!alive) {
        return;
      }
      setSettings(loadedSettings);

      const activeEnv = getActivePostgresEnv(loadedSettings);
      const hasDbConfig =
        activeEnv !== undefined &&
        activeEnv.dbHost.trim().length > 0 &&
        activeEnv.dbName.trim().length > 0 &&
        activeEnv.dbUser.trim().length > 0 &&
        Number(activeEnv.dbPort) > 0;

      try {
        const state = await api.getDatabaseConnectionState();
        if (!alive) {
          return;
        }
        if (state.ready) {
          setIsConnectionReady(true);
          return;
        }
      } catch {
        if (!alive) {
          return;
        }
      }

      if (!hasDbConfig) {
        if (alive) {
          setIsConnectionReady(false);
        }
        return;
      }

      if (alive) {
        setConnectionTestRunning(true);
      }
      try {
        const result = await api.testDatabaseConnection(loadedSettings);
        if (!alive) {
          return;
        }
        setIsConnectionReady(result.status === "ok");
        setHealthMessage(result.message);
        setConnectionTestLastResponse(JSON.stringify(result, null, 2));
      } catch (err: unknown) {
        console.error("testDatabaseConnection", err);
        if (!alive) {
          return;
        }
        setIsConnectionReady(false);
        const detail = err instanceof Error ? err.message : String(err);
        setHealthMessage(tRef.current("settings.connectionTestError"));
        setConnectionTestLastResponse(detail);
      } finally {
        if (alive) {
          setConnectionTestRunning(false);
        }
      }
    })();

    let unsubscribe: (() => void) | undefined;
    try {
      unsubscribe = api.onJobProgress((progressEvent) => {
        setProgressEvents((oldEvents) => [progressEvent, ...oldEvents].slice(0, 25));
        void reloadDocuments();
      });
    } catch (err) {
      console.error("onJobProgress", err);
    }

    return () => {
      alive = false;
      unsubscribe?.();
    };
    // Nur beim Mount: kein erneuter Lauf bei Locale-Wechsel (vermeidet abgebrochene Requests / hängende UI).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const availableTags = useMemo(
    () => Array.from(new Set(documents.flatMap((document) => document.tags))).sort((left, right) => left.localeCompare(right)),
    [documents]
  );

  useEffect(() => {
    if (typeFilter === "all") {
      return;
    }
    const types = new Set(documents.map((d) => d.fileType));
    if (!types.has(typeFilter)) {
      setTypeFilter("all");
    }
  }, [documents, typeFilter]);

  useEffect(() => {
    if (tagFilter === "all") {
      return;
    }
    if (!documents.some((d) => d.tags.includes(tagFilter))) {
      setTagFilter("all");
    }
  }, [documents, tagFilter]);

  const filteredDocuments = useMemo(
    () =>
      documents.filter((document) => {
        if (statusFilter !== "all" && document.status !== statusFilter) return false;
        if (typeFilter !== "all" && document.fileType !== typeFilter) return false;
        if (tagFilter !== "all" && !document.tags.includes(tagFilter)) return false;
        if (searchText.trim().length === 0) return true;
        const normalizedSearch = searchText.toLowerCase();
        return (
          document.fileName.toLowerCase().includes(normalizedSearch) ||
          document.docId.toLowerCase().includes(normalizedSearch) ||
          document.source.toLowerCase().includes(normalizedSearch)
        );
      }),
    [documents, searchText, statusFilter, typeFilter, tagFilter]
  );

  async function uploadWithPicker(): Promise<void> {
    if (!window.ragApi) {
      appendFolderLog("pick files: ragApi fehlt");
      setHealthMessage(t("upload.noRagApi"));
      return;
    }
    if (!isConnectionReady) {
      appendFolderLog("pick files: Verbindung nicht bereit");
      setHealthMessage(t("settings.testFirst"));
      return;
    }
    appendFolderLog("pick files: Dialog öffnen …");
    try {
      const up = await window.ragApi.pickAndUploadDocuments({
        tags: parseTags(uploadFormState.tagsInput),
        source: uploadFormState.source.trim() || "lokal"
      });
      appendFolderLog(
        `pick files: eingeplant=${up.queuedDocIds.length} uebersprungen=${up.skippedDocIds.length}`
      );
      for (const m of up.messages) {
        appendFolderLog(`pick files: ${m}`);
      }
      appendFolderLog("pick files: Upload abgeschlossen");
      await reloadDocuments();
    } catch (err) {
      const detail = formatErrorDetail(err);
      console.error("[rag] pickAndUploadDocuments", err);
      appendFolderLog(`pick files FEHLER: ${detail}`);
      setHealthMessage(`${t("upload.filePickError")} ${detail}`);
    }
  }

  async function pickFolderOnly(): Promise<void> {
    if (!window.ragApi) {
      appendFolderLog("pickFolder: ragApi fehlt (Preload/Electron?)");
      setHealthMessage(t("upload.noRagApi"));
      return;
    }
    if (typeof window.ragApi.pickFolder !== "function") {
      appendFolderLog("pickFolder: API pickFolder fehlt — apps/main neu bauen, preload.cjs prüfen");
      setHealthMessage(t("upload.pickFolderUnavailable"));
      return;
    }
    if (!isConnectionReady) {
      appendFolderLog("pickFolder: Verbindung nicht bereit (Settings → Connection Test)");
      setHealthMessage(t("settings.testFirst"));
      return;
    }
    appendFolderLog("pickFolder: Dialog öffnen …");
    try {
      const res = await window.ragApi.pickFolder();
      appendFolderLog(`pickFolder: Rohantwort ${JSON.stringify(res)}`);
      if (!res || typeof res !== "object") {
        throw new Error(`Unerwartete Antwort: ${String(res)}`);
      }
      if ("canceled" in res && res.canceled) {
        appendFolderLog("pickFolder: abgebrochen (Dialog)");
        return;
      }
      if (!("folderPath" in res) || typeof res.folderPath !== "string") {
        throw new Error("Antwort ohne folderPath");
      }
      const picked = res.folderPath.trim();
      if (!picked) {
        appendFolderLog("pickFolder: leerer Pfad");
        setHealthMessage(t("upload.folderPickEmptyPath"));
        return;
      }
      setSelectedFolderPath(picked);
      appendFolderLog(`pickFolder: OK → ${picked}`);
      setHealthMessage(t("upload.folderPickReady"));
    } catch (err) {
      const detail = formatErrorDetail(err);
      console.error("[rag] pickFolder", err);
      appendFolderLog(`pickFolder FEHLER: ${detail}`);
      setHealthMessage(`${t("upload.folderError")} ${detail}`);
    }
  }

  async function startFolderIngestFromSelection(): Promise<void> {
    if (!window.ragApi) {
      appendFolderLog("uploadFolder: ragApi fehlt");
      setHealthMessage(t("upload.noRagApi"));
      return;
    }
    if (typeof window.ragApi.uploadFolderFromPath !== "function") {
      appendFolderLog("uploadFolder: uploadFolderFromPath fehlt");
      setHealthMessage(t("upload.uploadFolderUnavailable"));
      return;
    }
    if (!selectedFolderPath) {
      appendFolderLog("uploadFolder: kein Ordner gewählt");
      setHealthMessage(t("upload.folderIngestNoFolder"));
      return;
    }
    if (!isConnectionReady) {
      appendFolderLog("uploadFolder: Verbindung nicht bereit");
      setHealthMessage(t("settings.testFirst"));
      return;
    }
    setFolderIngestRunning(true);
    appendFolderLog(`uploadFolder: Start für „${selectedFolderPath}“`);
    try {
      const result = await window.ragApi.uploadFolderFromPath(selectedFolderPath, {
        tags: parseTags(uploadFormState.tagsInput),
        source: uploadFormState.source.trim() || "lokal"
      });
      appendFolderLog(
        `uploadFolder: fileCount=${result.fileCount} queued=${result.queuedDocIds.length} skipped=${result.skippedDocIds.length}`
      );
      for (const m of result.messages) {
        appendFolderLog(`uploadFolder: ${m}`);
      }
      if (result.fileCount === 0) {
        setHealthMessage(t("upload.folderEmpty"));
      } else {
        setHealthMessage(t("upload.folderQueued", String(result.fileCount), String(result.queuedDocIds.length)));
        setSelectedFolderPath(null);
      }
      await reloadDocuments();
    } catch (err) {
      const detail = formatErrorDetail(err);
      console.error("[rag] uploadFolderFromPath", err);
      appendFolderLog(`uploadFolder FEHLER: ${detail}`);
      setHealthMessage(`${t("upload.folderError")} ${detail}`);
    } finally {
      setFolderIngestRunning(false);
      appendFolderLog("uploadFolder: Ende (finally)");
    }
  }

  function onOrdnerEinlesenClick(): void {
    if (folderIngestRunning) {
      appendFolderLog("Ordner einlesen: noch aktiv, ignoriert");
      return;
    }
    void startFolderIngestFromSelection();
  }

  async function uploadFromDrop(filePaths: string[]): Promise<void> {
    if (filePaths.length === 0) return;
    if (!window.ragApi) {
      appendFolderLog("drop: ragApi fehlt");
      setHealthMessage(t("upload.noRagApi"));
      return;
    }
    if (!isConnectionReady) {
      appendFolderLog("drop: Verbindung nicht bereit");
      setHealthMessage(t("settings.testFirst"));
      return;
    }
    appendFolderLog(`drop: ${filePaths.length} Datei(en)`);
    try {
      const up = await window.ragApi.uploadFiles(filePaths, {
        tags: parseTags(uploadFormState.tagsInput),
        source: uploadFormState.source.trim() || "lokal"
      });
      appendFolderLog(
        `drop: eingeplant=${up.queuedDocIds.length} uebersprungen=${up.skippedDocIds.length}`
      );
      for (const m of up.messages) {
        appendFolderLog(`drop: ${m}`);
      }
      appendFolderLog("drop: Upload OK");
      await reloadDocuments();
    } catch (err) {
      const detail = formatErrorDetail(err);
      console.error("[rag] uploadFromDrop", err);
      appendFolderLog(`drop FEHLER: ${detail}`);
      setHealthMessage(`${t("upload.dropError")} ${detail}`);
    }
  }

  async function openCorpusEditor(docId: string): Promise<void> {
    const loadedCorpus = await window.ragApi.getCorpus(docId);
    setCorpusDocumentId(docId);
    setCorpusContent(loadedCorpus);
  }

  async function saveCorpusAndReindex(): Promise<void> {
    if (!corpusDocumentId) return;
    await window.ragApi.saveCorpus(corpusDocumentId, corpusContent);
    await window.ragApi.reindexDocument(corpusDocumentId);
    await reloadDocuments();
  }

  async function removeSingleDocument(docId: string): Promise<void> {
    await window.ragApi.removeDocument(docId);
    setSelectedDocumentIds((oldIds) => oldIds.filter((entry) => entry !== docId));
    await reloadDocuments();
  }

  async function reindexSelectedDocuments(): Promise<void> {
    if (selectedDocumentIds.length === 0) return;
    await window.ragApi.reindexDocuments(selectedDocumentIds);
    await reloadDocuments();
  }

  async function removeSelectedDocuments(): Promise<void> {
    if (selectedDocumentIds.length === 0) return;
    await window.ragApi.removeDocuments(selectedDocumentIds);
    setSelectedDocumentIds([]);
    await reloadDocuments();
  }

  async function saveSettings(): Promise<void> {
    const persisted = await window.ragApi.saveSettings(settings);
    setSettings(persisted);
    setIsConnectionReady(false);
    setHealthMessage(t("settings.saved"));
  }

  async function runConnectionTest(): Promise<void> {
    if (!window.ragApi) {
      setHealthMessage(t("settings.loadError"));
      return;
    }
    setConnectionTestRunning(true);
    try {
      const result = await window.ragApi.testDatabaseConnection(settings);
      setIsConnectionReady(result.status === "ok");
      setHealthMessage(result.message);
      setConnectionTestLastResponse(JSON.stringify(result, null, 2));
    } catch (err: unknown) {
      console.error("testDatabaseConnection", err);
      setIsConnectionReady(false);
      const detail = err instanceof Error ? err.message : String(err);
      setHealthMessage(t("settings.connectionTestError"));
      setConnectionTestLastResponse(detail);
    } finally {
      setConnectionTestRunning(false);
    }
  }

  async function exportCsv(): Promise<void> {
    const csvContent = await window.ragApi.exportDocumentsCsv();
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchorElement = document.createElement("a");
    anchorElement.href = url;
    anchorElement.download = "rag-ingest-documents.csv";
    anchorElement.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div className="top-bar-left">
          <h1>{t("app.title")}</h1>
          <div className="tab-row">
            <button
              type="button"
              className={`tab-button ${activeTab === "documents" ? "active" : ""}`}
              onClick={() => setActiveTab("documents")}
            >
              {t("tabs.documents")}
            </button>
            <button
              type="button"
              className={`tab-button ${activeTab === "settings" ? "active" : ""}`}
              onClick={() => setActiveTab("settings")}
            >
              {t("tabs.settings")}
            </button>
          </div>
        </div>
        <div className="button-row">
          {activeTab === "documents" && (
            <>
              <button type="button" onClick={() => void uploadWithPicker()}>
                {t("header.addDocuments")}
              </button>
              <button onClick={() => void reindexSelectedDocuments()} disabled={selectedDocumentIds.length === 0}>
                {t("header.reindexSelected")}
              </button>
              <button onClick={() => void removeSelectedDocuments()} disabled={selectedDocumentIds.length === 0}>
                {t("header.removeSelected")}
              </button>
              <button onClick={() => void exportCsv()}>{t("header.exportCsv")}</button>
            </>
          )}
          <div className="lang-switcher">
            <span>{t("settings.language")}:</span>
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
      </header>

      {activeTab === "documents" && (
        <>
          <section
            className={`drop-zone ${isDropActive ? "drop-zone-active" : ""}`}
            onDragOver={(event) => {
              if (!isConnectionReady) return;
              event.preventDefault();
              setIsDropActive(true);
            }}
            onDragLeave={() => setIsDropActive(false)}
            onDrop={(event) => {
              if (!isConnectionReady) return;
              event.preventDefault();
              setIsDropActive(false);
              const droppedFilePaths = Array.from(event.dataTransfer.files)
                .map((file) => (file as File & { path?: string }).path)
                .filter((value): value is string => Boolean(value));
              void uploadFromDrop(droppedFilePaths);
            }}
          >
            {isConnectionReady ? t("drop.ready") : t("drop.locked")}
          </section>

          <section className="panel panel-folder-ingest" aria-label={t("upload.folderSectionTitle")}>
            <h2 className="panel-folder-ingest__title">{t("upload.folderSectionTitle")}</h2>
            <div className="folder-toolbar-visible">
              <button type="button" onClick={() => void pickFolderOnly()}>
                {t("header.addFolder")}
              </button>
              <button
                type="button"
                className={`btn-folder-start${!selectedFolderPath || !isConnectionReady ? " btn-folder-start--muted" : ""}`}
                disabled={folderIngestRunning}
                title={
                  selectedFolderPath ? selectedFolderPath : t("header.folderIngestNeedPick")
                }
                onClick={() => onOrdnerEinlesenClick()}
              >
                {folderIngestRunning ? t("header.folderIngestRunning") : t("header.startFolderIngest")}
              </button>
              {selectedFolderPath ? (
                <>
                  <span className="folder-pick-path folder-pick-path--block" title={selectedFolderPath}>
                    {selectedFolderPath}
                  </span>
                  <button
                    type="button"
                    className="btn-folder-clear"
                    disabled={folderIngestRunning}
                    onClick={() => {
                      setSelectedFolderPath(null);
                      setHealthMessage("");
                      appendFolderLog("Auswahl aufgehoben");
                    }}
                  >
                    {t("header.clearFolderPick")}
                  </button>
                </>
              ) : null}
            </div>
            <p className="upload-hint">{t("upload.folderHint")}</p>
            {healthMessage ? (
              <p className="upload-hint upload-status folder-ingest-status" role="status">
                {healthMessage}
              </p>
            ) : null}
            <div className="folder-action-log-header">
              <span className="upload-hint">{t("upload.actionLogTitle")}</span>
              <button
                type="button"
                className="btn-folder-clear"
                onClick={() => setFolderActionLog("")}
              >
                {t("upload.actionLogClear")}
              </button>
            </div>
            {folderActionLog ? (
              <pre className="folder-action-log" aria-live="polite">
                {folderActionLog}
              </pre>
            ) : (
              <p className="upload-hint folder-action-log-placeholder">{t("upload.actionLogEmpty")}</p>
            )}
          </section>

          <section className="panel">
            <h2>{t("upload.title")}</h2>
            <div className="input-grid">
              <label>
                {t("upload.tags")}
                <input
                  value={uploadFormState.tagsInput}
                  onChange={(event) => setUploadFormState((old) => ({ ...old, tagsInput: event.target.value }))}
                />
              </label>
              <label>
                {t("upload.source")}
                <input
                  value={uploadFormState.source}
                  onChange={(event) => setUploadFormState((old) => ({ ...old, source: event.target.value }))}
                />
              </label>
            </div>
          </section>

          <section className="panel">
        <h2>{t("doclist.title")}</h2>
        <div className="input-grid filter-grid">
          <label>
            {t("doclist.search")}
            <input value={searchText} onChange={(event) => setSearchText(event.target.value)} />
          </label>
          <label>
            {t("doclist.status")}
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="all">{t("doclist.all")}</option>
              <option value="queued">queued</option>
              <option value="processing">processing</option>
              <option value="done">done</option>
              <option value="error">error</option>
            </select>
          </label>
          <label>
            {t("doclist.type")}
            <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
              <option value="all">{t("doclist.all")}</option>
              {Array.from(new Set(documents.map((document) => document.fileType))).map((fileType) => (
                <option key={fileType} value={fileType}>
                  {fileType}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("doclist.tag")}
            <select value={tagFilter} onChange={(event) => setTagFilter(event.target.value)}>
              <option value="all">{t("doclist.all")}</option>
              {availableTags.map((tag) => (
                <option key={tag} value={tag}>
                  {tag}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th />
                <th>{t("doclist.file")}</th>
                <th>docId</th>
                <th>{t("doclist.type")}</th>
                <th>{t("doclist.status")}</th>
                <th>{t("doclist.chunks")}</th>
                <th>{t("doclist.size")}</th>
                <th>{t("doclist.tags")}</th>
                <th>{t("doclist.source")}</th>
                <th>{t("doclist.lastProcessed")}</th>
                <th>{t("doclist.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {filteredDocuments.map((document) => {
                const isSelected = selectedDocumentIds.includes(document.docId);
                return (
                  <tr key={document.docId}>
                    <td>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={(event) => {
                          setSelectedDocumentIds((oldDocumentIds) =>
                            event.target.checked
                              ? [...oldDocumentIds, document.docId]
                              : oldDocumentIds.filter((entry) => entry !== document.docId)
                          );
                        }}
                      />
                    </td>
                    <td>{document.fileName}</td>
                    <td className="mono-cell">{document.docId.slice(0, 12)}...</td>
                    <td>{document.fileType}</td>
                    <td>{document.status}</td>
                    <td>{document.chunkCount}</td>
                    <td>{Math.round(document.sizeBytes / 1024)} KB</td>
                    <td>{document.tags.join(", ")}</td>
                    <td>{document.source}</td>
                    <td>{document.lastIndexedAt ? new Date(document.lastIndexedAt).toLocaleString() : "-"}</td>
                    <td className="action-column">
                      <button onClick={() => void openCorpusEditor(document.docId)}>{t("doclist.viewCorpus")}</button>
                      <button onClick={() => void window.ragApi.reindexDocument(document.docId)}>{t("doclist.reindex")}</button>
                      <button onClick={() => void removeSingleDocument(document.docId)}>{t("doclist.remove")}</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
          </section>

          <section className="panel">
            <h2>{t("jobs.title")}</h2>
            <div className="events-list">
              {progressEvents.map((event) => (
                <div key={`${event.jobId}-${event.progress}-${event.status}`} className="event-card">
                  <strong>{event.type}</strong> | {event.status} | {Math.round(event.progress * 100)}%
                  <div>{event.docId.slice(0, 12)}... - {event.message}</div>
                </div>
              ))}
            </div>
          </section>

          {corpusDocumentId ? (
            <section className="panel">
              <h2>{t("corpus.title")} - {corpusDocumentId}</h2>
              <textarea value={corpusContent} onChange={(event) => setCorpusContent(event.target.value)} rows={18} />
              <div className="button-row">
                <button onClick={() => void saveCorpusAndReindex()}>{t("corpus.saveAndReindex")}</button>
                <button
                  onClick={() => {
                    setCorpusDocumentId(null);
                    setCorpusContent("");
                  }}
                >
                  {t("corpus.close")}
                </button>
              </div>
            </section>
          ) : null}
        </>
      )}

      {activeTab === "settings" && (
        <section className="panel">
          <h2>{t("settings.title")}</h2>
            <div className="input-grid">
              <div className="button-row" style={{ gridColumn: "1 / -1" }}>
                <label style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
                  {t("settings.activePostgresEnv")}
                  <select
                    value={settings.activePostgresEnvironmentId}
                    onChange={(event) => {
                      const nextId = event.target.value;
                      setSettings((old) => (old ? { ...old, activePostgresEnvironmentId: nextId } : old));
                      setIsConnectionReady(false);
                    }}
                  >
                    {settings.postgresEnvironments.map((env) => (
                      <option key={env.id} value={env.id}>
                        {env.name} ({env.id})
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  onClick={() => {
                    setSettings((old) => (old ? addPostgresEnvironment(old) : old));
                    setIsConnectionReady(false);
                  }}
                >
                  {t("settings.addPostgresEnv")}
                </button>
                <button
                  type="button"
                  disabled={settings.postgresEnvironments.length < 2}
                  onClick={() => {
                    setSettings((old) =>
                      old ? removePostgresEnvironment(old, old.activePostgresEnvironmentId) : old
                    );
                    setIsConnectionReady(false);
                  }}
                >
                  {t("settings.removePostgresEnv")}
                </button>
              </div>
              <label>
                {t("settings.envName")}
                <input
                  value={getActivePostgresEnv(settings)?.name ?? ""}
                  onChange={(event) =>
                    setSettings((old) => (old ? updateActivePostgresEnv(old, { name: event.target.value }) : old))
                  }
                />
              </label>
              <label>
                {t("settings.dbHost")}
                <input
                  value={getActivePostgresEnv(settings)?.dbHost ?? ""}
                  onChange={(event) =>
                    setSettings((old) => (old ? updateActivePostgresEnv(old, { dbHost: event.target.value }) : old))
                  }
                />
              </label>
              <label>
                {t("settings.dbPort")}
                <input
                  type="number"
                  value={getActivePostgresEnv(settings)?.dbPort ?? 5432}
                  onChange={(event) =>
                    setSettings((old) =>
                      old ? updateActivePostgresEnv(old, { dbPort: Number(event.target.value) || 5432 }) : old
                    )
                  }
                />
              </label>
              <label>
                {t("settings.dbName")}
                <input
                  value={getActivePostgresEnv(settings)?.dbName ?? ""}
                  onChange={(event) =>
                    setSettings((old) => (old ? updateActivePostgresEnv(old, { dbName: event.target.value }) : old))
                  }
                />
              </label>
              <label>
                {t("settings.dbSchema")}
                <input
                  value={getActivePostgresEnv(settings)?.dbSchema ?? "public"}
                  onChange={(event) =>
                    setSettings((old) => (old ? updateActivePostgresEnv(old, { dbSchema: event.target.value }) : old))
                  }
                />
              </label>
              <label>
                {t("settings.dbUser")}
                <input
                  value={getActivePostgresEnv(settings)?.dbUser ?? ""}
                  onChange={(event) =>
                    setSettings((old) => (old ? updateActivePostgresEnv(old, { dbUser: event.target.value }) : old))
                  }
                />
              </label>
              <label>
                {t("settings.dbPassword")}
                <input
                  type="password"
                  value={getActivePostgresEnv(settings)?.dbPassword ?? ""}
                  onChange={(event) =>
                    setSettings((old) => (old ? updateActivePostgresEnv(old, { dbPassword: event.target.value }) : old))
                  }
                />
              </label>
              <label>
                {t("settings.vectorTable")}
                <input
                  value={getActivePostgresEnv(settings)?.dbTableName ?? ""}
                  onChange={(event) =>
                    setSettings((old) =>
                      old ? updateActivePostgresEnv(old, { dbTableName: event.target.value }) : old
                    )
                  }
                />
              </label>
              <label>
                {t("settings.chunkSize")}
                <input
                  type="number"
                  value={settings.chunkSize}
                  onChange={(event) =>
                    setSettings((old) => (old ? { ...old, chunkSize: Number(event.target.value) } : old))
                  }
                />
              </label>
              <label>
                {t("settings.chunkOverlap")}
                <input
                  type="number"
                  value={settings.chunkOverlap}
                  onChange={(event) =>
                    setSettings((old) => (old ? { ...old, chunkOverlap: Number(event.target.value) } : old))
                  }
                />
              </label>
              <label>
                {t("settings.embeddingModel")}
                <input
                  value={settings.embeddingModel}
                  onChange={(event) =>
                    setSettings((old) => (old ? { ...old, embeddingModel: event.target.value } : old))
                  }
                />
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={settings.storeMarkdown}
                  onChange={(event) =>
                    setSettings((old) => (old ? { ...old, storeMarkdown: event.target.checked } : old))
                  }
                />
                {t("settings.storeMarkdown")}
              </label>
              <p className="upload-hint">{t("settings.connectionTestUsesForm")}</p>
              <p className="upload-hint">{t("settings.passwordKeepHint")}</p>
              <div className="button-row connection-test-actions">
                <button type="button" onClick={() => void saveSettings()} disabled={connectionTestRunning}>
                  {t("settings.save")}
                </button>
                <button
                  type="button"
                  className={`btn-connection-test${connectionTestRunning ? " btn-connection-test--running" : ""}`}
                  onClick={() => void runConnectionTest()}
                  disabled={connectionTestRunning}
                  aria-busy={connectionTestRunning}
                >
                  {connectionTestRunning ? (
                    <>
                      <span className="btn-connection-test__spinner" aria-hidden />
                      <span>{t("settings.connectionTestRunning")}</span>
                    </>
                  ) : (
                    t("settings.connectionTest")
                  )}
                </button>
              </div>
              {healthMessage || connectionTestRunning ? (
                <p
                  className={`connection-feedback${
                    connectionTestRunning
                      ? " connection-feedback--busy"
                      : isConnectionReady
                        ? " connection-feedback--ok"
                        : " connection-feedback--err"
                  }`}
                  role="status"
                >
                  {connectionTestRunning ? t("settings.connectionTestRunningDetail") : healthMessage}
                </p>
              ) : null}
              {connectionTestLastResponse.trim().length > 0 ? (
                <div className="connection-test-response-wrap">
                  <div className="connection-test-response-label">{t("settings.connectionTestResponse")}</div>
                  <pre className="connection-test-response">{connectionTestLastResponse}</pre>
                </div>
              ) : null}
            </div>
        </section>
      )}
    </div>
  );
}
