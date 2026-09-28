import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { defaultAppSettings } from "@rag/shared";
import { useI18n } from "./i18n";
function parseTags(tagsInput) {
    return tagsInput
        .split(",")
        .map((entry) => entry.trim())
        .filter((entry) => entry.length > 0);
}
function formatBytes(n) {
    if (n == null || n < 0 || !Number.isFinite(n)) {
        return "—";
    }
    const units = ["B", "KB", "MB", "GB", "TB"];
    let value = n;
    let unitIndex = 0;
    while (value >= 1024 && unitIndex < units.length - 1) {
        value /= 1024;
        unitIndex += 1;
    }
    return unitIndex === 0 ? `${Math.round(value)} ${units[unitIndex]}` : `${value.toFixed(1)} ${units[unitIndex]}`;
}
function formatErrorDetail(err) {
    if (err instanceof Error) {
        const c = err.cause;
        const causeStr = c instanceof Error ? ` | Cause: ${c.message}` : "";
        return `${err.name}: ${err.message}${causeStr}`;
    }
    return typeof err === "object" && err !== null ? JSON.stringify(err) : String(err);
}
function getActivePostgresEnv(settings) {
    return settings.postgresEnvironments.find((env) => env.id === settings.activePostgresEnvironmentId);
}
function updateActivePostgresEnv(settings, patch) {
    const activeId = settings.activePostgresEnvironmentId;
    return {
        ...settings,
        postgresEnvironments: settings.postgresEnvironments.map((env) => env.id === activeId ? { ...env, ...patch } : env)
    };
}
function addPostgresEnvironment(settings) {
    const newId = crypto.randomUUID();
    const template = getActivePostgresEnv(settings) ?? settings.postgresEnvironments[0];
    if (!template) {
        return settings;
    }
    const clone = {
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
function removePostgresEnvironment(settings, id) {
    const remaining = settings.postgresEnvironments.filter((env) => env.id !== id);
    const firstRemaining = remaining[0];
    if (remaining.length === 0 || !firstRemaining) {
        return settings;
    }
    const nextActive = settings.activePostgresEnvironmentId === id ? firstRemaining.id : settings.activePostgresEnvironmentId;
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
    const [activeTab, setActiveTab] = useState("documents");
    const [documents, setDocuments] = useState([]);
    const [selectedDocumentIds, setSelectedDocumentIds] = useState([]);
    const [searchText, setSearchText] = useState("");
    const [statusFilter, setStatusFilter] = useState("all");
    const [typeFilter, setTypeFilter] = useState("all");
    const [tagFilter, setTagFilter] = useState("all");
    const [uploadFormState, setUploadFormState] = useState({ tagsInput: "", source: "lokal" });
    const [settings, setSettings] = useState(defaultAppSettings);
    const [isConnectionReady, setIsConnectionReady] = useState(false);
    const [healthMessage, setHealthMessage] = useState("");
    const [connectionTestRunning, setConnectionTestRunning] = useState(false);
    const [connectionTestLastResponse, setConnectionTestLastResponse] = useState("");
    const [corpusDocumentId, setCorpusDocumentId] = useState(null);
    const [corpusContent, setCorpusContent] = useState("");
    const [progressEvents, setProgressEvents] = useState([]);
    const [isDropActive, setIsDropActive] = useState(false);
    const [selectedFolderPath, setSelectedFolderPath] = useState(null);
    const [folderIngestRunning, setFolderIngestRunning] = useState(false);
    const [folderActionLog, setFolderActionLog] = useState("");
    const [reindexAllRunning, setReindexAllRunning] = useState(false);
    const [ollamaModels, setOllamaModels] = useState([]);
    const [ollamaModelsBaseUrl, setOllamaModelsBaseUrl] = useState("");
    const [ollamaModelsLoading, setOllamaModelsLoading] = useState(false);
    const [ollamaModelsError, setOllamaModelsError] = useState("");
    const loadOllamaModels = useCallback(async () => {
        if (!window.ragApi?.listOllamaModels) {
            setOllamaModelsError(t("models.apiUnavailable"));
            return;
        }
        setOllamaModelsLoading(true);
        setOllamaModelsError("");
        try {
            const res = await window.ragApi.listOllamaModels();
            setOllamaModels(res.models);
            setOllamaModelsBaseUrl(res.ollamaBaseUrl);
        }
        catch (err) {
            setOllamaModelsError(err instanceof Error ? err.message : String(err));
            setOllamaModels([]);
            setOllamaModelsBaseUrl("");
        }
        finally {
            setOllamaModelsLoading(false);
        }
    }, [t]);
    useEffect(() => {
        if (activeTab !== "models") {
            return undefined;
        }
        void loadOllamaModels();
        return undefined;
    }, [activeTab, loadOllamaModels]);
    function appendFolderLog(line) {
        const stamp = new Date().toLocaleTimeString();
        const row = `[${stamp}] ${line}`;
        console.info(`[rag folder] ${row}`);
        setFolderActionLog((prev) => {
            const next = prev ? `${prev}\n${row}` : row;
            return next.length > 6000 ? next.slice(-6000) : next;
        });
    }
    async function reloadDocuments() {
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
            let loadedSettings;
            try {
                loadedSettings = await api.getSettings();
            }
            catch (err) {
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
            const vb = activeEnv?.vectorBackend ?? "postgres";
            const hasDbConfig = activeEnv !== undefined &&
                (vb !== "postgres" ||
                    (activeEnv.dbHost.trim().length > 0 &&
                        activeEnv.dbName.trim().length > 0 &&
                        activeEnv.dbUser.trim().length > 0 &&
                        Number(activeEnv.dbPort) > 0));
            try {
                const state = await api.getDatabaseConnectionState();
                if (!alive) {
                    return;
                }
                if (state.ready) {
                    setIsConnectionReady(true);
                    return;
                }
            }
            catch {
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
            }
            catch (err) {
                console.error("testDatabaseConnection", err);
                if (!alive) {
                    return;
                }
                setIsConnectionReady(false);
                const detail = err instanceof Error ? err.message : String(err);
                setHealthMessage(tRef.current("settings.connectionTestError"));
                setConnectionTestLastResponse(detail);
            }
            finally {
                if (alive) {
                    setConnectionTestRunning(false);
                }
            }
        })();
        let unsubscribe;
        try {
            unsubscribe = api.onJobProgress((progressEvent) => {
                setProgressEvents((oldEvents) => [progressEvent, ...oldEvents].slice(0, 25));
                void reloadDocuments();
            });
        }
        catch (err) {
            console.error("onJobProgress", err);
        }
        return () => {
            alive = false;
            unsubscribe?.();
        };
        // Nur beim Mount: kein erneuter Lauf bei Locale-Wechsel (vermeidet abgebrochene Requests / hängende UI).
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    const availableTags = useMemo(() => Array.from(new Set(documents.flatMap((document) => document.tags))).sort((left, right) => left.localeCompare(right)), [documents]);
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
    const filteredDocuments = useMemo(() => documents.filter((document) => {
        if (statusFilter !== "all" && document.status !== statusFilter)
            return false;
        if (typeFilter !== "all" && document.fileType !== typeFilter)
            return false;
        if (tagFilter !== "all" && !document.tags.includes(tagFilter))
            return false;
        if (searchText.trim().length === 0)
            return true;
        const normalizedSearch = searchText.toLowerCase();
        return (document.fileName.toLowerCase().includes(normalizedSearch) ||
            document.docId.toLowerCase().includes(normalizedSearch) ||
            document.source.toLowerCase().includes(normalizedSearch));
    }), [documents, searchText, statusFilter, typeFilter, tagFilter]);
    const activePgEnvResolved = getActivePostgresEnv(settings);
    const activeVectorBackend = activePgEnvResolved?.vectorBackend ?? "postgres";
    async function uploadWithPicker() {
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
            appendFolderLog(`pick files: eingeplant=${up.queuedDocIds.length} uebersprungen=${up.skippedDocIds.length}`);
            for (const m of up.messages) {
                appendFolderLog(`pick files: ${m}`);
            }
            appendFolderLog("pick files: Upload abgeschlossen");
            await reloadDocuments();
        }
        catch (err) {
            const detail = formatErrorDetail(err);
            console.error("[rag] pickAndUploadDocuments", err);
            appendFolderLog(`pick files FEHLER: ${detail}`);
            setHealthMessage(`${t("upload.filePickError")} ${detail}`);
        }
    }
    async function pickFolderOnly() {
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
        }
        catch (err) {
            const detail = formatErrorDetail(err);
            console.error("[rag] pickFolder", err);
            appendFolderLog(`pickFolder FEHLER: ${detail}`);
            setHealthMessage(`${t("upload.folderError")} ${detail}`);
        }
    }
    async function startFolderIngestFromSelection() {
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
            appendFolderLog(`uploadFolder: fileCount=${result.fileCount} queued=${result.queuedDocIds.length} skipped=${result.skippedDocIds.length}`);
            for (const m of result.messages) {
                appendFolderLog(`uploadFolder: ${m}`);
            }
            if (result.fileCount === 0) {
                setHealthMessage(t("upload.folderEmpty"));
            }
            else {
                setHealthMessage(t("upload.folderQueued", String(result.fileCount), String(result.queuedDocIds.length)));
                setSelectedFolderPath(null);
            }
            await reloadDocuments();
        }
        catch (err) {
            const detail = formatErrorDetail(err);
            console.error("[rag] uploadFolderFromPath", err);
            appendFolderLog(`uploadFolder FEHLER: ${detail}`);
            setHealthMessage(`${t("upload.folderError")} ${detail}`);
        }
        finally {
            setFolderIngestRunning(false);
            appendFolderLog("uploadFolder: Ende (finally)");
        }
    }
    function onOrdnerEinlesenClick() {
        if (folderIngestRunning) {
            appendFolderLog("Ordner einlesen: noch aktiv, ignoriert");
            return;
        }
        void startFolderIngestFromSelection();
    }
    async function uploadFromDrop(filePaths) {
        if (filePaths.length === 0)
            return;
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
            appendFolderLog(`drop: eingeplant=${up.queuedDocIds.length} uebersprungen=${up.skippedDocIds.length}`);
            for (const m of up.messages) {
                appendFolderLog(`drop: ${m}`);
            }
            appendFolderLog("drop: Upload OK");
            await reloadDocuments();
        }
        catch (err) {
            const detail = formatErrorDetail(err);
            console.error("[rag] uploadFromDrop", err);
            appendFolderLog(`drop FEHLER: ${detail}`);
            setHealthMessage(`${t("upload.dropError")} ${detail}`);
        }
    }
    async function openCorpusEditor(docId) {
        const loadedCorpus = await window.ragApi.getCorpus(docId);
        setCorpusDocumentId(docId);
        setCorpusContent(loadedCorpus);
    }
    async function saveCorpusAndReindex() {
        if (!corpusDocumentId)
            return;
        await window.ragApi.saveCorpus(corpusDocumentId, corpusContent);
        await window.ragApi.reindexDocument(corpusDocumentId);
        await reloadDocuments();
    }
    async function removeSingleDocument(docId) {
        await window.ragApi.removeDocument(docId);
        setSelectedDocumentIds((oldIds) => oldIds.filter((entry) => entry !== docId));
        await reloadDocuments();
    }
    async function reindexSelectedDocuments() {
        if (selectedDocumentIds.length === 0)
            return;
        await window.ragApi.reindexDocuments(selectedDocumentIds);
        await reloadDocuments();
    }
    async function reindexAllDocuments() {
        if (!window.ragApi) {
            setHealthMessage(t("upload.noRagApi"));
            return;
        }
        if (!isConnectionReady) {
            setHealthMessage(t("settings.testFirst"));
            return;
        }
        const ids = documents.map((d) => d.docId);
        if (ids.length === 0) {
            setHealthMessage(t("header.reindexAllNone"));
            return;
        }
        if (!window.confirm(t("header.reindexAllConfirm", String(ids.length)))) {
            return;
        }
        setReindexAllRunning(true);
        try {
            await window.ragApi.reindexDocuments(ids);
            await reloadDocuments();
            setHealthMessage(t("header.reindexAllStarted", String(ids.length)));
        }
        catch (err) {
            const detail = formatErrorDetail(err);
            console.error("[rag] reindexAllDocuments", err);
            setHealthMessage(detail);
        }
        finally {
            setReindexAllRunning(false);
        }
    }
    async function removeSelectedDocuments() {
        if (selectedDocumentIds.length === 0)
            return;
        await window.ragApi.removeDocuments(selectedDocumentIds);
        setSelectedDocumentIds([]);
        await reloadDocuments();
    }
    async function removeNotIngestedDocuments() {
        const res = await window.ragApi.removeNotIngestedDocuments();
        setSelectedDocumentIds([]);
        await reloadDocuments();
        appendFolderLog(`cleanup: ${res.removedCount} nicht eingelesene Dokumente entfernt`);
        setHealthMessage(`Nicht eingelesene Dokumente entfernt: ${res.removedCount}`);
    }
    async function saveSettings() {
        const persisted = await window.ragApi.saveSettings(settings);
        setSettings(persisted);
        setIsConnectionReady(false);
        setSelectedDocumentIds([]);
        await reloadDocuments();
        setHealthMessage(t("settings.saved"));
    }
    async function runConnectionTest() {
        if (!window.ragApi) {
            setHealthMessage(t("settings.loadError"));
            return;
        }
        setConnectionTestRunning(true);
        try {
            const result = await window.ragApi.testDatabaseConnection(settings);
            setIsConnectionReady(result.status === "ok");
            if (result.status === "ok") {
                setSelectedDocumentIds([]);
                await reloadDocuments();
            }
            setHealthMessage(result.message);
            setConnectionTestLastResponse(JSON.stringify(result, null, 2));
        }
        catch (err) {
            console.error("testDatabaseConnection", err);
            setIsConnectionReady(false);
            const detail = err instanceof Error ? err.message : String(err);
            setHealthMessage(t("settings.connectionTestError"));
            setConnectionTestLastResponse(detail);
        }
        finally {
            setConnectionTestRunning(false);
        }
    }
    async function exportCsv() {
        const csvContent = await window.ragApi.exportDocumentsCsv();
        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const anchorElement = document.createElement("a");
        anchorElement.href = url;
        anchorElement.download = "rag-ingest-documents.csv";
        anchorElement.click();
        URL.revokeObjectURL(url);
    }
    return (_jsxs("div", { className: "app-shell", children: [_jsxs("header", { className: "top-bar", children: [_jsxs("div", { className: "top-bar-left", children: [_jsx("h1", { children: t("app.title") }), _jsxs("div", { className: "tab-row", children: [_jsx("button", { type: "button", className: `tab-button ${activeTab === "documents" ? "active" : ""}`, onClick: () => setActiveTab("documents"), children: t("tabs.documents") }), _jsx("button", { type: "button", className: `tab-button ${activeTab === "models" ? "active" : ""}`, onClick: () => setActiveTab("models"), children: t("tabs.models") }), _jsx("button", { type: "button", className: `tab-button ${activeTab === "settings" ? "active" : ""}`, onClick: () => setActiveTab("settings"), children: t("tabs.settings") })] })] }), _jsxs("div", { className: "button-row", children: [activeTab === "documents" && (_jsxs(_Fragment, { children: [_jsx("button", { type: "button", onClick: () => void uploadWithPicker(), children: t("header.addDocuments") }), _jsx("button", { onClick: () => void reindexSelectedDocuments(), disabled: selectedDocumentIds.length === 0, children: t("header.reindexSelected") }), _jsx("button", { type: "button", onClick: () => void reindexAllDocuments(), disabled: !isConnectionReady || documents.length === 0 || reindexAllRunning, children: reindexAllRunning ? t("header.reindexAllRunning") : t("header.reindexAll") }), _jsx("button", { onClick: () => void removeSelectedDocuments(), disabled: selectedDocumentIds.length === 0, children: t("header.removeSelected") }), _jsx("button", { onClick: () => void removeNotIngestedDocuments(), children: "Alle nicht eingelesenen entfernen" }), _jsx("button", { onClick: () => void exportCsv(), children: t("header.exportCsv") })] })), _jsxs("div", { className: "lang-switcher", children: [_jsxs("span", { children: [t("settings.language"), ":"] }), _jsx("button", { className: `lang-toggle ${locale === "de" ? "active" : ""}`, onClick: () => setLocale("de"), type: "button", children: "DE" }), _jsx("button", { className: `lang-toggle ${locale === "en" ? "active" : ""}`, onClick: () => setLocale("en"), type: "button", children: "EN" })] })] })] }), activeTab === "documents" && (_jsxs(_Fragment, { children: [_jsx("section", { className: `drop-zone ${isDropActive ? "drop-zone-active" : ""}`, onDragOver: (event) => {
                            if (!isConnectionReady)
                                return;
                            event.preventDefault();
                            setIsDropActive(true);
                        }, onDragLeave: () => setIsDropActive(false), onDrop: (event) => {
                            if (!isConnectionReady)
                                return;
                            event.preventDefault();
                            setIsDropActive(false);
                            const droppedFilePaths = Array.from(event.dataTransfer.files)
                                .map((file) => file.path)
                                .filter((value) => Boolean(value));
                            void uploadFromDrop(droppedFilePaths);
                        }, children: isConnectionReady ? t("drop.ready") : t("drop.locked") }), _jsxs("section", { className: "panel panel-folder-ingest", "aria-label": t("upload.folderSectionTitle"), children: [_jsx("h2", { className: "panel-folder-ingest__title", children: t("upload.folderSectionTitle") }), _jsxs("div", { className: "folder-toolbar-visible", children: [_jsx("button", { type: "button", onClick: () => void pickFolderOnly(), children: t("header.addFolder") }), _jsx("button", { type: "button", className: `btn-folder-start${!selectedFolderPath || !isConnectionReady ? " btn-folder-start--muted" : ""}`, disabled: folderIngestRunning, title: selectedFolderPath ? selectedFolderPath : t("header.folderIngestNeedPick"), onClick: () => onOrdnerEinlesenClick(), children: folderIngestRunning ? t("header.folderIngestRunning") : t("header.startFolderIngest") }), selectedFolderPath ? (_jsxs(_Fragment, { children: [_jsx("span", { className: "folder-pick-path folder-pick-path--block", title: selectedFolderPath, children: selectedFolderPath }), _jsx("button", { type: "button", className: "btn-folder-clear", disabled: folderIngestRunning, onClick: () => {
                                                    setSelectedFolderPath(null);
                                                    setHealthMessage("");
                                                    appendFolderLog("Auswahl aufgehoben");
                                                }, children: t("header.clearFolderPick") })] })) : null] }), _jsx("p", { className: "upload-hint", children: t("upload.folderHint") }), healthMessage ? (_jsx("p", { className: "upload-hint upload-status folder-ingest-status", role: "status", children: healthMessage })) : null, _jsxs("div", { className: "folder-action-log-header", children: [_jsx("span", { className: "upload-hint", children: t("upload.actionLogTitle") }), _jsx("button", { type: "button", className: "btn-folder-clear", onClick: () => setFolderActionLog(""), children: t("upload.actionLogClear") })] }), folderActionLog ? (_jsx("pre", { className: "folder-action-log", "aria-live": "polite", children: folderActionLog })) : (_jsx("p", { className: "upload-hint folder-action-log-placeholder", children: t("upload.actionLogEmpty") }))] }), _jsxs("section", { className: "panel", children: [_jsx("h2", { children: t("upload.title") }), _jsxs("div", { className: "input-grid", children: [_jsxs("label", { children: [t("upload.tags"), _jsx("input", { value: uploadFormState.tagsInput, onChange: (event) => setUploadFormState((old) => ({ ...old, tagsInput: event.target.value })) })] }), _jsxs("label", { children: [t("upload.source"), _jsx("input", { value: uploadFormState.source, onChange: (event) => setUploadFormState((old) => ({ ...old, source: event.target.value })) })] })] })] }), _jsxs("section", { className: "panel", children: [_jsx("h2", { children: t("doclist.title") }), _jsxs("div", { className: "input-grid filter-grid", children: [_jsxs("label", { children: [t("doclist.search"), _jsx("input", { value: searchText, onChange: (event) => setSearchText(event.target.value) })] }), _jsxs("label", { children: [t("doclist.status"), _jsxs("select", { value: statusFilter, onChange: (event) => setStatusFilter(event.target.value), children: [_jsx("option", { value: "all", children: t("doclist.all") }), _jsx("option", { value: "queued", children: "queued" }), _jsx("option", { value: "processing", children: "processing" }), _jsx("option", { value: "done", children: "done" }), _jsx("option", { value: "error", children: "error" })] })] }), _jsxs("label", { children: [t("doclist.type"), _jsxs("select", { value: typeFilter, onChange: (event) => setTypeFilter(event.target.value), children: [_jsx("option", { value: "all", children: t("doclist.all") }), Array.from(new Set(documents.map((document) => document.fileType))).map((fileType) => (_jsx("option", { value: fileType, children: fileType }, fileType)))] })] }), _jsxs("label", { children: [t("doclist.tag"), _jsxs("select", { value: tagFilter, onChange: (event) => setTagFilter(event.target.value), children: [_jsx("option", { value: "all", children: t("doclist.all") }), availableTags.map((tag) => (_jsx("option", { value: tag, children: tag }, tag)))] })] })] }), _jsx("div", { className: "table-wrapper", children: _jsxs("table", { children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", {}), _jsx("th", { children: t("doclist.file") }), _jsx("th", { children: "docId" }), _jsx("th", { children: t("doclist.type") }), _jsx("th", { children: t("doclist.status") }), _jsx("th", { children: t("doclist.chunks") }), _jsx("th", { children: t("doclist.size") }), _jsx("th", { children: t("doclist.tags") }), _jsx("th", { children: t("doclist.source") }), _jsx("th", { children: t("doclist.lastProcessed") }), _jsx("th", { children: t("doclist.actions") })] }) }), _jsx("tbody", { children: filteredDocuments.map((document) => {
                                                const isSelected = selectedDocumentIds.includes(document.docId);
                                                return (_jsxs("tr", { children: [_jsx("td", { children: _jsx("input", { type: "checkbox", checked: isSelected, onChange: (event) => {
                                                                    setSelectedDocumentIds((oldDocumentIds) => event.target.checked
                                                                        ? [...oldDocumentIds, document.docId]
                                                                        : oldDocumentIds.filter((entry) => entry !== document.docId));
                                                                } }) }), _jsx("td", { children: document.fileName }), _jsxs("td", { className: "mono-cell", children: [document.docId.slice(0, 12), "..."] }), _jsx("td", { children: document.fileType }), _jsx("td", { children: document.status }), _jsx("td", { children: document.chunkCount }), _jsxs("td", { children: [Math.round(document.sizeBytes / 1024), " KB"] }), _jsx("td", { children: document.tags.join(", ") }), _jsx("td", { children: document.source }), _jsx("td", { children: document.lastIndexedAt ? new Date(document.lastIndexedAt).toLocaleString() : "-" }), _jsxs("td", { className: "action-column", children: [_jsx("button", { onClick: () => void openCorpusEditor(document.docId), children: t("doclist.viewCorpus") }), _jsx("button", { onClick: () => void window.ragApi.reindexDocument(document.docId), children: t("doclist.reindex") }), _jsx("button", { onClick: () => void removeSingleDocument(document.docId), children: t("doclist.remove") })] })] }, document.docId));
                                            }) })] }) })] }), _jsxs("section", { className: "panel", children: [_jsx("h2", { children: t("jobs.title") }), _jsx("div", { className: "events-list", children: progressEvents.map((event) => (_jsxs("div", { className: "event-card", children: [_jsx("strong", { children: event.type }), " | ", event.status, " | ", Math.round(event.progress * 100), "%", _jsxs("div", { children: [event.docId.slice(0, 12), "... - ", event.message] })] }, `${event.jobId}-${event.progress}-${event.status}`))) })] }), corpusDocumentId ? (_jsxs("section", { className: "panel", children: [_jsxs("h2", { children: [t("corpus.title"), " - ", corpusDocumentId] }), _jsx("textarea", { value: corpusContent, onChange: (event) => setCorpusContent(event.target.value), rows: 18 }), _jsxs("div", { className: "button-row", children: [_jsx("button", { onClick: () => void saveCorpusAndReindex(), children: t("corpus.saveAndReindex") }), _jsx("button", { onClick: () => {
                                            setCorpusDocumentId(null);
                                            setCorpusContent("");
                                        }, children: t("corpus.close") })] })] })) : null] })), activeTab === "models" && (_jsxs("section", { className: "panel models-panel", children: [_jsx("h2", { children: t("models.title") }), _jsx("p", { className: "upload-hint models-panel__intro", children: t("models.intro") }), _jsx("ul", { className: "model-provider-list", "aria-label": t("models.title"), children: _jsxs("li", { className: "model-provider-card model-provider-card--system", children: [_jsxs("div", { className: "model-provider-card__header", children: [_jsx("span", { className: "model-provider-card__name", children: t("models.ollama.name") }), _jsx("span", { className: "model-provider-card__badge", children: t("models.badgeBuiltin") })] }), _jsx("p", { className: "model-provider-card__description", children: t("models.ollama.description") }), ollamaModelsBaseUrl ? (_jsxs("p", { className: "model-provider-card__endpoint", children: [_jsx("span", { className: "model-provider-card__endpoint-label", children: t("models.ollamaEndpoint") }), _jsx("code", { className: "model-provider-card__endpoint-value", children: ollamaModelsBaseUrl })] })) : null, _jsx("div", { className: "ollama-models-toolbar", children: _jsx("button", { type: "button", onClick: () => void loadOllamaModels(), disabled: ollamaModelsLoading, children: ollamaModelsLoading ? t("models.loading") : t("models.refresh") }) }), ollamaModelsError ? (_jsx("p", { className: "ollama-models-error", role: "alert", children: ollamaModelsError })) : null, !ollamaModelsLoading && !ollamaModelsError && ollamaModels.length === 0 ? (_jsx("p", { className: "upload-hint ollama-models-empty", children: t("models.empty") })) : null, ollamaModels.length > 0 ? (_jsx("div", { className: "table-wrapper ollama-models-table-wrap", children: _jsxs("table", { className: "ollama-models-table", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: t("models.colName") }), _jsx("th", { children: t("models.colSize") }), _jsx("th", { children: t("models.colModified") })] }) }), _jsx("tbody", { children: ollamaModels.map((row) => (_jsxs("tr", { children: [_jsx("td", { className: "mono-cell", children: row.name }), _jsx("td", { children: formatBytes(row.size) }), _jsx("td", { children: row.modifiedAt
                                                                ? (() => {
                                                                    const d = Date.parse(row.modifiedAt);
                                                                    return Number.isNaN(d) ? row.modifiedAt : new Date(d).toLocaleString();
                                                                })()
                                                                : "—" })] }, row.name))) })] }) })) : null] }) })] })), activeTab === "settings" && (_jsxs("section", { className: "panel", children: [_jsx("h2", { children: t("settings.title") }), _jsxs("div", { className: "input-grid", children: [_jsxs("div", { className: "button-row", style: { gridColumn: "1 / -1" }, children: [_jsxs("label", { style: { display: "flex", flexDirection: "column", gap: 4, flex: 1 }, children: [t("settings.activePostgresEnv"), _jsx("select", { value: settings.activePostgresEnvironmentId, onChange: (event) => {
                                                    const nextId = event.target.value;
                                                    setSettings((old) => (old ? { ...old, activePostgresEnvironmentId: nextId } : old));
                                                    setIsConnectionReady(false);
                                                }, children: settings.postgresEnvironments.map((env) => (_jsxs("option", { value: env.id, children: [env.name, " (", env.id, ")"] }, env.id))) })] }), _jsx("button", { type: "button", onClick: () => {
                                            setSettings((old) => (old ? addPostgresEnvironment(old) : old));
                                            setIsConnectionReady(false);
                                        }, children: t("settings.addPostgresEnv") }), _jsx("button", { type: "button", disabled: settings.postgresEnvironments.length < 2, onClick: () => {
                                            setSettings((old) => old ? removePostgresEnvironment(old, old.activePostgresEnvironmentId) : old);
                                            setIsConnectionReady(false);
                                        }, children: t("settings.removePostgresEnv") })] }), _jsxs("label", { children: [t("settings.envName"), _jsx("input", { value: getActivePostgresEnv(settings)?.name ?? "", onChange: (event) => setSettings((old) => (old ? updateActivePostgresEnv(old, { name: event.target.value }) : old)) })] }), _jsxs("label", { children: [t("settings.vectorBackend"), _jsxs("select", { value: activeVectorBackend, onChange: (event) => setSettings((old) => old
                                            ? updateActivePostgresEnv(old, {
                                                vectorBackend: event.target.value
                                            })
                                            : old), children: [_jsx("option", { value: "postgres", children: t("settings.vectorBackend.postgres") }), _jsx("option", { value: "sqlite_embedded", children: t("settings.vectorBackend.sqlite") }), _jsx("option", { value: "qdrant_embedded", children: t("settings.vectorBackend.qdrant") })] })] }), activeVectorBackend === "postgres" ? (_jsxs(_Fragment, { children: [_jsxs("label", { children: [t("settings.dbHost"), _jsx("input", { value: getActivePostgresEnv(settings)?.dbHost ?? "", onChange: (event) => setSettings((old) => (old ? updateActivePostgresEnv(old, { dbHost: event.target.value }) : old)) })] }), _jsxs("label", { children: [t("settings.dbPort"), _jsx("input", { type: "number", value: getActivePostgresEnv(settings)?.dbPort ?? 5432, onChange: (event) => setSettings((old) => old ? updateActivePostgresEnv(old, { dbPort: Number(event.target.value) || 5432 }) : old) })] }), _jsxs("label", { children: [t("settings.dbName"), _jsx("input", { value: getActivePostgresEnv(settings)?.dbName ?? "", onChange: (event) => setSettings((old) => (old ? updateActivePostgresEnv(old, { dbName: event.target.value }) : old)) })] }), _jsxs("label", { children: [t("settings.dbSchema"), _jsx("input", { value: getActivePostgresEnv(settings)?.dbSchema ?? "public", onChange: (event) => setSettings((old) => (old ? updateActivePostgresEnv(old, { dbSchema: event.target.value }) : old)) })] }), _jsxs("label", { children: [t("settings.dbUser"), _jsx("input", { value: getActivePostgresEnv(settings)?.dbUser ?? "", onChange: (event) => setSettings((old) => (old ? updateActivePostgresEnv(old, { dbUser: event.target.value }) : old)) })] }), _jsxs("label", { children: [t("settings.dbPassword"), _jsx("input", { type: "password", value: getActivePostgresEnv(settings)?.dbPassword ?? "", onChange: (event) => setSettings((old) => old ? updateActivePostgresEnv(old, { dbPassword: event.target.value }) : old) })] })] })) : null, activeVectorBackend === "sqlite_embedded" ? (_jsxs("label", { children: [t("settings.sqliteFilePath"), _jsx("input", { value: getActivePostgresEnv(settings)?.sqliteFilePath ?? "", placeholder: t("settings.sqliteFilePathPlaceholder"), onChange: (event) => setSettings((old) => old ? updateActivePostgresEnv(old, { sqliteFilePath: event.target.value }) : old) })] })) : null, activeVectorBackend === "qdrant_embedded" ? (_jsxs("label", { children: [t("settings.qdrantLocalPath"), _jsx("input", { value: getActivePostgresEnv(settings)?.qdrantLocalPath ?? "", placeholder: t("settings.qdrantLocalPathPlaceholder"), onChange: (event) => setSettings((old) => old ? updateActivePostgresEnv(old, { qdrantLocalPath: event.target.value }) : old) })] })) : null, _jsxs("label", { children: [t("settings.vectorTable"), _jsx("input", { value: getActivePostgresEnv(settings)?.dbTableName ?? "", onChange: (event) => setSettings((old) => old ? updateActivePostgresEnv(old, { dbTableName: event.target.value }) : old) })] }), _jsxs("label", { children: [t("settings.chunkSize"), _jsx("input", { type: "number", value: settings.chunkSize, onChange: (event) => setSettings((old) => (old ? { ...old, chunkSize: Number(event.target.value) } : old)) })] }), _jsxs("label", { children: [t("settings.chunkOverlap"), _jsx("input", { type: "number", value: settings.chunkOverlap, onChange: (event) => setSettings((old) => (old ? { ...old, chunkOverlap: Number(event.target.value) } : old)) })] }), _jsxs("label", { children: [t("settings.embeddingModel"), _jsx("input", { value: settings.embeddingModel, onChange: (event) => setSettings((old) => (old ? { ...old, embeddingModel: event.target.value } : old)) })] }), _jsxs("label", { className: "checkbox-label", children: [_jsx("input", { type: "checkbox", checked: settings.storeMarkdown, onChange: (event) => setSettings((old) => (old ? { ...old, storeMarkdown: event.target.checked } : old)) }), t("settings.storeMarkdown")] }), _jsx("p", { className: "upload-hint", children: t("settings.connectionTestUsesForm") }), _jsx("p", { className: "upload-hint", children: t("settings.passwordKeepHint") }), _jsxs("div", { className: "button-row connection-test-actions", children: [_jsx("button", { type: "button", onClick: () => void saveSettings(), disabled: connectionTestRunning, children: t("settings.save") }), _jsx("button", { type: "button", className: `btn-connection-test${connectionTestRunning ? " btn-connection-test--running" : ""}`, onClick: () => void runConnectionTest(), disabled: connectionTestRunning, "aria-busy": connectionTestRunning, children: connectionTestRunning ? (_jsxs(_Fragment, { children: [_jsx("span", { className: "btn-connection-test__spinner", "aria-hidden": true }), _jsx("span", { children: t("settings.connectionTestRunning") })] })) : (t("settings.connectionTest")) })] }), healthMessage || connectionTestRunning ? (_jsx("p", { className: `connection-feedback${connectionTestRunning
                                    ? " connection-feedback--busy"
                                    : isConnectionReady
                                        ? " connection-feedback--ok"
                                        : " connection-feedback--err"}`, role: "status", children: connectionTestRunning ? t("settings.connectionTestRunningDetail") : healthMessage })) : null, connectionTestLastResponse.trim().length > 0 ? (_jsxs("div", { className: "connection-test-response-wrap", children: [_jsx("div", { className: "connection-test-response-label", children: t("settings.connectionTestResponse") }), _jsx("pre", { className: "connection-test-response", children: connectionTestLastResponse })] })) : null] })] }))] }));
}
