import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  DEFAULT_EMBEDDING_MODEL_ID,
  EMBEDDING_MODEL_OPTIONS,
  defaultAppSettings,
  type AppSettings,
  type DocumentRecord,
  type PostgresEnvironment,
  type ProgressEventPayload,
  type UploadOptions,
  type VectorBackend
} from "@rag/shared";
import { useI18n } from "./i18n";
import type { ChatSettings, OllamaModelRow } from "./types/global";
import ApiKeysPanel from "./ApiKeysPanel";
import BulkTestPanel from "./BulkTestPanel";
import { useConnection } from "./ConnectionGate";

interface UploadFormState {
  tagsInput: string;
  source: string;
  embeddingModel: string;
}

function parseTags(tagsInput: string): string[] {
  return tagsInput
    .split(",")
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
}

function buildUploadOptions(form: UploadFormState): UploadOptions {
  return {
    tags: parseTags(form.tagsInput),
    source: form.source.trim() || "lokal",
    embeddingModel: form.embeddingModel.trim() || undefined
  };
}

function formatBytes(n: number | null | undefined): string {
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

const DEFAULT_RERANK = {
  rerankSimilarityWeight: 0.9,
  rerankLexicalWeight: 0.05,
  rerankNumericWeight: 0.05
} as const;

function normalizeChatSettings(settings: ChatSettings): ChatSettings {
  return {
    ...settings,
    rerankSimilarityWeight: Math.max(
      0,
      Number.isFinite(settings.rerankSimilarityWeight)
        ? settings.rerankSimilarityWeight
        : DEFAULT_RERANK.rerankSimilarityWeight
    ),
    rerankLexicalWeight: Math.max(
      0,
      Number.isFinite(settings.rerankLexicalWeight)
        ? settings.rerankLexicalWeight
        : DEFAULT_RERANK.rerankLexicalWeight
    ),
    rerankNumericWeight: Math.max(
      0,
      Number.isFinite(settings.rerankNumericWeight)
        ? settings.rerankNumericWeight
        : DEFAULT_RERANK.rerankNumericWeight
    )
  };
}

function rerankWeightPercents(settings: ChatSettings): {
  similarity: number;
  lexical: number;
  numeric: number;
} {
  const sim = Math.max(0, settings.rerankSimilarityWeight);
  const lex = Math.max(0, settings.rerankLexicalWeight);
  const num = Math.max(0, settings.rerankNumericWeight);
  const total = sim + lex + num;
  if (total <= 0) {
    return { similarity: 100, lexical: 0, numeric: 0 };
  }
  return {
    similarity: Math.round((sim / total) * 1000) / 10,
    lexical: Math.round((lex / total) * 1000) / 10,
    numeric: Math.round((num / total) * 1000) / 10
  };
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

function normalizeEnv(env: PostgresEnvironment, fallback?: AppSettings): PostgresEnvironment {
  return {
    ...env,
    familyId: env.familyId || env.id,
    familyName: env.familyName || env.name || env.id,
    embeddingModel: env.embeddingModel || fallback?.embeddingModel || DEFAULT_EMBEDDING_MODEL_ID,
    chunkSize: env.chunkSize || fallback?.chunkSize || 900,
    chunkOverlap: env.chunkOverlap ?? fallback?.chunkOverlap ?? 15,
    isMatrixVariant: Boolean(env.isMatrixVariant)
  };
}

function updateActivePostgresEnv(settings: AppSettings, patch: Partial<PostgresEnvironment>): AppSettings {
  const activeId = settings.activePostgresEnvironmentId;
  const activeBefore = settings.postgresEnvironments.find((env) => env.id === activeId);
  let nextEnvs = settings.postgresEnvironments.map((env) =>
    env.id === activeId ? { ...normalizeEnv(env, settings), ...patch } : env
  );

  // Familienname gilt für alle Instanzen derselben familyId
  if (patch.familyName !== undefined && activeBefore) {
    const fid = String(patch.familyId || activeBefore.familyId || activeBefore.id);
    const fname = patch.familyName;
    nextEnvs = nextEnvs.map((env) => {
      const n = normalizeEnv(env, settings);
      if ((n.familyId || n.id) !== fid) return env;
      const merged = env.id === activeId ? { ...n, ...patch } : n;
      return {
        ...merged,
        familyId: fid,
        familyName: fname,
        name:
          env.id === activeId && typeof patch.name === "string"
            ? patch.name
            : formatInstanceName(
                fname,
                merged.embeddingModel,
                merged.chunkSize,
                merged.chunkOverlap
              )
      };
    });
  }

  const active = nextEnvs.find((e) => e.id === activeId);
  const mirrored =
    active != null
      ? {
          embeddingModel: active.embeddingModel,
          chunkSize: active.chunkSize,
          chunkOverlap: active.chunkOverlap
        }
      : {};
  return {
    ...settings,
    ...mirrored,
    postgresEnvironments: nextEnvs
  };
}

function embeddingShortLabel(modelId: string): string {
  const opt = EMBEDDING_MODEL_OPTIONS.find((m) => m.id === modelId);
  if (opt) return opt.label.replace(/\s*\(.*?\)\s*/g, "").trim() || opt.label;
  const base = modelId.split("/").pop() || modelId;
  return base.length > 28 ? `${base.slice(0, 28)}…` : base;
}

function formatInstanceName(familyName: string, embeddingModel: string, chunkSize: number, overlap: number): string {
  return `${familyName} · ${embeddingShortLabel(embeddingModel)} · c${chunkSize}/o${overlap}%`;
}

function tableNameForInstance(instanceId: string): string {
  const safe = instanceId.replace(/[^a-zA-Z0-9_]/g, "_").slice(0, 24);
  return `rag_${safe || "env"}`;
}

function addPostgresEnvironment(settings: AppSettings): AppSettings {
  const newId = crypto.randomUUID();
  const template = getActivePostgresEnv(settings) ?? settings.postgresEnvironments[0];
  if (!template) {
    return settings;
  }
  const base = normalizeEnv(template, settings);
  const familyName = base.familyName || base.name || "Umgebung";
  const clone: PostgresEnvironment = {
    ...base,
    id: newId,
    familyId: base.familyId || base.id,
    familyName,
    name: formatInstanceName(familyName, base.embeddingModel, base.chunkSize, base.chunkOverlap),
    dbTableName: tableNameForInstance(newId),
    sqliteFilePath: "",
    qdrantLocalPath: "",
    isMatrixVariant: false
  };
  return {
    ...settings,
    embeddingModel: clone.embeddingModel,
    chunkSize: clone.chunkSize,
    chunkOverlap: clone.chunkOverlap,
    postgresEnvironments: [...settings.postgresEnvironments, clone],
    activePostgresEnvironmentId: newId
  };
}

function addMatrixFamily(
  settings: AppSettings,
  opts: {
    familyName: string;
    embeddings: string[];
    chunkSizes: number[];
    overlaps: number[];
  }
): AppSettings {
  const template = getActivePostgresEnv(settings) ?? settings.postgresEnvironments[0];
  if (!template) return settings;
  const base = normalizeEnv(template, settings);
  const familyId = crypto.randomUUID();
  const familyName = opts.familyName.trim() || base.familyName || base.name || "Matrix";
  const instances: PostgresEnvironment[] = [];
  for (const emb of opts.embeddings) {
    for (const chunk of opts.chunkSizes) {
      for (const overlap of opts.overlaps) {
        const id = crypto.randomUUID();
        instances.push({
          ...base,
          id,
          familyId,
          familyName,
          name: formatInstanceName(familyName, emb, chunk, overlap),
          embeddingModel: emb,
          chunkSize: chunk,
          chunkOverlap: overlap,
          dbTableName: tableNameForInstance(id),
          sqliteFilePath: "",
          qdrantLocalPath: "",
          isMatrixVariant: true
        });
      }
    }
  }
  if (instances.length === 0) return settings;
  const first = instances[0]!;
  return {
    ...settings,
    embeddingModel: first.embeddingModel,
    chunkSize: first.chunkSize,
    chunkOverlap: first.chunkOverlap,
    postgresEnvironments: [...settings.postgresEnvironments, ...instances],
    activePostgresEnvironmentId: first.id
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
  const active = remaining.find((e) => e.id === nextActive) ?? firstRemaining;
  return {
    ...settings,
    embeddingModel: active.embeddingModel || settings.embeddingModel,
    chunkSize: active.chunkSize || settings.chunkSize,
    chunkOverlap: active.chunkOverlap ?? settings.chunkOverlap,
    postgresEnvironments: remaining,
    activePostgresEnvironmentId: nextActive
  };
}

export default function App() {
  const { t, locale, setLocale } = useI18n();
  const { reopenConnectionSetup, isAdmin } = useConnection();
  const tRef = useRef(t);
  tRef.current = t;
  const [activeTab, setActiveTab] = useState<"documents" | "models" | "settings" | "bulk">("documents");
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [searchText, setSearchText] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [tagFilter, setTagFilter] = useState<string>("all");
  const [uploadFormState, setUploadFormState] = useState<UploadFormState>({
    tagsInput: "",
    source: "lokal",
    embeddingModel: DEFAULT_EMBEDDING_MODEL_ID
  });
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
  const [reindexAllRunning, setReindexAllRunning] = useState(false);
  const [familyReindexRunning, setFamilyReindexRunning] = useState(false);
  const [familyReindexMessage, setFamilyReindexMessage] = useState("");
  const familyReindexPollRef = useRef<number | null>(null);
  const [ollamaModels, setOllamaModels] = useState<OllamaModelRow[]>([]);
  const [ollamaModelsBaseUrl, setOllamaModelsBaseUrl] = useState("");
  const [ollamaModelsLoading, setOllamaModelsLoading] = useState(false);
  const [ollamaModelsError, setOllamaModelsError] = useState("");
  const [chatSettings, setChatSettings] = useState<ChatSettings | null>(null);
  const [activeModelSaving, setActiveModelSaving] = useState(false);
  const [activeModelMessage, setActiveModelMessage] = useState("");
  const [rankingSaving, setRankingSaving] = useState(false);
  const [rankingMessage, setRankingMessage] = useState("");
  const [matrixMode, setMatrixMode] = useState(false);
  const [matrixFamilyName, setMatrixFamilyName] = useState("");
  const [matrixEmbeddings, setMatrixEmbeddings] = useState<string[]>([DEFAULT_EMBEDDING_MODEL_ID]);
  const [matrixChunkSizes, setMatrixChunkSizes] = useState<string>("800,900,1000,1100,1200");
  const [matrixOverlaps, setMatrixOverlaps] = useState<string>("10,15,20");

  const rankingPercents = useMemo(
    () => (chatSettings ? rerankWeightPercents(chatSettings) : null),
    [chatSettings]
  );

  const loadModelsTab = useCallback(async () => {
    if (!window.ragApi?.listOllamaModels) {
      setOllamaModelsError(t("models.apiUnavailable"));
      return;
    }
    setOllamaModelsLoading(true);
    setOllamaModelsError("");
    setActiveModelMessage("");
    try {
      const [modelsRes, settings] = await Promise.all([
        window.ragApi.listOllamaModels(),
        window.ragApi.getChatSettings()
      ]);
      setOllamaModels(modelsRes.models);
      setOllamaModelsBaseUrl(modelsRes.ollamaBaseUrl);
      setChatSettings(normalizeChatSettings(settings));
      setRankingMessage("");
    } catch (err: unknown) {
      setOllamaModelsError(err instanceof Error ? err.message : String(err));
      setOllamaModels([]);
      setOllamaModelsBaseUrl("");
    } finally {
      setOllamaModelsLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (activeTab !== "models") {
      return undefined;
    }
    void loadModelsTab();
    return undefined;
  }, [activeTab, loadModelsTab]);

  async function selectActiveModel(modelName: string): Promise<void> {
    if (!chatSettings || !modelName || chatSettings.llmModel === modelName || activeModelSaving) {
      return;
    }
    setActiveModelSaving(true);
    setActiveModelMessage("");
    try {
      const saved = await window.ragApi.saveChatSettings({
        ...chatSettings,
        llmModel: modelName
      });
      setChatSettings(normalizeChatSettings(saved));
      setActiveModelMessage(t("models.activeSaved", modelName));
    } catch (err: unknown) {
      setActiveModelMessage(
        `${t("models.activeSaveError")}: ${err instanceof Error ? err.message : String(err)}`
      );
    } finally {
      setActiveModelSaving(false);
    }
  }

  function patchRankingWeight(
    key: "rerankSimilarityWeight" | "rerankLexicalWeight" | "rerankNumericWeight",
    value: number
  ): void {
    setChatSettings((prev) => (prev ? { ...prev, [key]: Math.max(0, value) } : prev));
    setRankingMessage("");
  }

  async function saveRankingWeights(): Promise<void> {
    if (!chatSettings || rankingSaving) {
      return;
    }
    setRankingSaving(true);
    setRankingMessage("");
    try {
      const saved = await window.ragApi.saveChatSettings(normalizeChatSettings(chatSettings));
      setChatSettings(normalizeChatSettings(saved));
      setRankingMessage(t("models.ranking.saved"));
    } catch (err: unknown) {
      setRankingMessage(
        `${t("models.ranking.saveError")}: ${err instanceof Error ? err.message : String(err)}`
      );
    } finally {
      setRankingSaving(false);
    }
  }

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

    void api.getChatSettings()
      .then((settings) => {
        if (alive) {
          setChatSettings(normalizeChatSettings(settings));
        }
      })
      .catch((err: unknown) => {
        console.error("getChatSettings", err);
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
      setUploadFormState((old) => ({
        ...old,
        embeddingModel: loadedSettings.embeddingModel || old.embeddingModel
      }));

      const activeEnv = getActivePostgresEnv(loadedSettings);
      const vb = activeEnv?.vectorBackend ?? "postgres";
      const hasDbConfig =
        activeEnv !== undefined &&
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

  const activePgEnvResolved = getActivePostgresEnv(settings);
  const activeVectorBackend: VectorBackend = activePgEnvResolved?.vectorBackend ?? "postgres";
  const activeFamilyId = activePgEnvResolved?.familyId || activePgEnvResolved?.id || "";
  const activeFamilyInstanceCount = useMemo(
    () =>
      settings.postgresEnvironments.filter(
        (e) => (e.familyId || e.id) === activeFamilyId
      ).length,
    [settings.postgresEnvironments, activeFamilyId]
  );
  const totalEnvironmentCount = settings.postgresEnvironments.length;

  const matrixPreviewCount = useMemo(() => {
    const chunks = matrixChunkSizes
      .split(/[,;\s]+/)
      .map((s) => Number(s.trim()))
      .filter((n) => Number.isFinite(n) && n > 0);
    const overlaps = matrixOverlaps
      .split(/[,;\s]+/)
      .map((s) => Number(s.trim()))
      .filter((n) => Number.isFinite(n) && n >= 0 && n <= 90);
    return matrixEmbeddings.length * chunks.length * overlaps.length;
  }, [matrixEmbeddings, matrixChunkSizes, matrixOverlaps]);

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
      const up = await window.ragApi.pickAndUploadDocuments(buildUploadOptions(uploadFormState));
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
      const result = await window.ragApi.uploadFolderFromPath(selectedFolderPath, buildUploadOptions(uploadFormState));
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
      const up = await window.ragApi.uploadFiles(filePaths, buildUploadOptions(uploadFormState));
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

  async function reindexAllDocuments(): Promise<void> {
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
    } catch (err: unknown) {
      const detail = formatErrorDetail(err);
      console.error("[rag] reindexAllDocuments", err);
      setHealthMessage(detail);
    } finally {
      setReindexAllRunning(false);
    }
  }

  function stopFamilyReindexPolling(): void {
    if (familyReindexPollRef.current != null) {
      window.clearInterval(familyReindexPollRef.current);
      familyReindexPollRef.current = null;
    }
  }

  function startFamilyReindexPolling(): void {
    stopFamilyReindexPolling();
    familyReindexPollRef.current = window.setInterval(() => {
      void (async () => {
        try {
          const st = await window.ragApi.getFamilyReindexStatus?.();
          if (!st) return;
          setFamilyReindexMessage(st.message || "");
          if (st.message) setHealthMessage(st.message);
          if (st.status === "done" || st.status === "error" || st.status === "cancelled" || st.status === "idle") {
            stopFamilyReindexPolling();
            setFamilyReindexRunning(false);
            await reloadDocuments();
            if (st.status === "done") {
              setHealthMessage(st.message || t("header.familyReindexStarted"));
            } else if (st.status === "error") {
              setHealthMessage(st.error || st.message || "Familien-Index fehlgeschlagen");
            } else if (st.status === "cancelled") {
              setHealthMessage(st.message || "Abgebrochen");
            }
            // Settings neu laden (aktive Umgebung kann gewechselt worden sein)
            try {
              const next = await window.ragApi.getSettings();
              setSettings(next);
            } catch {
              /* ignore */
            }
          }
        } catch (err) {
          stopFamilyReindexPolling();
          setFamilyReindexRunning(false);
          setHealthMessage(formatErrorDetail(err));
        }
      })();
    }, 1500);
  }

  async function reindexFamily(): Promise<void> {
    if (!window.ragApi?.startFamilyReindex) {
      setHealthMessage(t("upload.noRagApi"));
      return;
    }
    if (!isConnectionReady) {
      setHealthMessage(t("settings.testFirst"));
      return;
    }
    const active = getActivePostgresEnv(settings);
    const familyId = active?.familyId || active?.id || "";
    const instanceCount = settings.postgresEnvironments.filter(
      (e) => (e.familyId || e.id) === familyId
    ).length;
    if (instanceCount < 1) {
      setHealthMessage("Keine Familien-Instanzen gefunden.");
      return;
    }
    if (
      !window.confirm(
        `${t("header.familyReindexConfirm", String(documents.length))} (${instanceCount} Instanzen)`
      )
    ) {
      return;
    }
    setFamilyReindexRunning(true);
    setFamilyReindexMessage("");
    try {
      const started = await window.ragApi.startFamilyReindex({
        familyId: familyId || undefined,
        sourceEnvironmentId: settings.activePostgresEnvironmentId
      });
      setFamilyReindexMessage(started.message || "");
      setHealthMessage(t("header.familyReindexStarted"));
      startFamilyReindexPolling();
    } catch (err: unknown) {
      setFamilyReindexRunning(false);
      setHealthMessage(formatErrorDetail(err));
    }
  }

  async function cancelFamilyReindex(): Promise<void> {
    try {
      await window.ragApi.cancelFamilyReindex?.();
      setHealthMessage("Abbruch angefordert …");
    } catch (err) {
      setHealthMessage(formatErrorDetail(err));
    }
  }

  useEffect(() => {
    return () => {
      if (familyReindexPollRef.current != null) {
        window.clearInterval(familyReindexPollRef.current);
        familyReindexPollRef.current = null;
      }
    };
  }, []);

  async function removeSelectedDocuments(): Promise<void> {
    if (selectedDocumentIds.length === 0) return;
    await window.ragApi.removeDocuments(selectedDocumentIds);
    setSelectedDocumentIds([]);
    await reloadDocuments();
  }

  async function removeNotIngestedDocuments(): Promise<void> {
    const res = await window.ragApi.removeNotIngestedDocuments();
    setSelectedDocumentIds([]);
    await reloadDocuments();
    appendFolderLog(`cleanup: ${res.removedCount} nicht eingelesene Dokumente entfernt`);
    setHealthMessage(`Nicht eingelesene Dokumente entfernt: ${res.removedCount}`);
  }

  async function saveSettings(override?: AppSettings): Promise<AppSettings | null> {
    const source = override ?? settings;
    const toSave: AppSettings = {
      ...source,
      postgresEnvironments: source.postgresEnvironments.map((env) => normalizeEnv(env, source))
    };
    try {
      const persisted = await window.ragApi.saveSettings(toSave);
      setSettings(persisted);
      setUploadFormState((old) => ({
        ...old,
        embeddingModel: persisted.embeddingModel || old.embeddingModel
      }));
      setIsConnectionReady(false);
      setSelectedDocumentIds([]);
      await reloadDocuments();
      setHealthMessage(t("settings.saved"));
      return persisted;
    } catch (err: unknown) {
      const detail = formatErrorDetail(err);
      console.error("[rag] saveSettings", err);
      setHealthMessage(`${t("settings.saveError")}: ${detail}`);
      return null;
    }
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
      if (result.status === "ok") {
        setSelectedDocumentIds([]);
        await reloadDocuments();
      }
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
          <button
            type="button"
            className="active-model-chip"
            title={t("models.activeChipHint")}
            onClick={() => setActiveTab("models")}
          >
            <span className="active-model-chip__label">{t("models.activeChipLabel")}</span>
            <code className="active-model-chip__value">
              {chatSettings?.llmModel?.trim() || t("models.activeChipUnknown")}
            </code>
          </button>
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
              className={`tab-button ${activeTab === "models" ? "active" : ""}`}
              onClick={() => setActiveTab("models")}
            >
              {t("tabs.models")}
            </button>
            <button
              type="button"
              className={`tab-button ${activeTab === "bulk" ? "active" : ""}`}
              onClick={() => setActiveTab("bulk")}
            >
              {t("tabs.bulk")}
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
              <button
                type="button"
                onClick={() => void reindexAllDocuments()}
                disabled={!isConnectionReady || documents.length === 0 || reindexAllRunning || familyReindexRunning}
              >
                {reindexAllRunning ? t("header.reindexAllRunning") : t("header.reindexAll")}
              </button>
              <button
                type="button"
                onClick={() => void reindexFamily()}
                disabled={!isConnectionReady || familyReindexRunning}
                title={familyReindexMessage || undefined}
              >
                {familyReindexRunning ? t("header.familyReindexRunning") : t("header.familyReindex")}
                {!familyReindexRunning && activeFamilyInstanceCount > 1
                  ? ` (${activeFamilyInstanceCount})`
                  : ""}
              </button>
              {familyReindexRunning ? (
                <>
                  <button type="button" onClick={() => void cancelFamilyReindex()}>
                    {t("header.familyReindexCancel")}
                  </button>
                  {familyReindexMessage ? (
                    <span className="upload-hint" style={{ alignSelf: "center" }}>
                      {familyReindexMessage}
                    </span>
                  ) : null}
                </>
              ) : null}
              <button onClick={() => void removeSelectedDocuments()} disabled={selectedDocumentIds.length === 0}>
                {t("header.removeSelected")}
              </button>
              <button onClick={() => void removeNotIngestedDocuments()}>
                Alle nicht eingelesenen entfernen
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
              const files = Array.from(event.dataTransfer.files);
              if (files.length === 0) {
                return;
              }
              if (typeof window.ragApi.uploadBrowserFiles === "function") {
                void (async () => {
                  try {
                    appendFolderLog(`drop: ${files.length} Datei(en) (Browser)`);
                    const up = await window.ragApi.uploadBrowserFiles!(files, buildUploadOptions(uploadFormState));
                    appendFolderLog(
                      `drop: eingeplant=${up.queuedDocIds.length} uebersprungen=${up.skippedDocIds.length}`
                    );
                    await reloadDocuments();
                  } catch (err) {
                    const detail = formatErrorDetail(err);
                    appendFolderLog(`drop FEHLER: ${detail}`);
                    setHealthMessage(`${t("upload.dropError")} ${detail}`);
                  }
                })();
                return;
              }
              const droppedFilePaths = files
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
              <label>
                {t("upload.embeddingModel")}
                <select
                  value={uploadFormState.embeddingModel}
                  onChange={(event) =>
                    setUploadFormState((old) => ({ ...old, embeddingModel: event.target.value }))
                  }
                >
                  {EMBEDDING_MODEL_OPTIONS.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.label}
                      {model.recommended ? " ★" : ""} ({model.dimensions}d · {model.languages})
                    </option>
                  ))}
                  {!EMBEDDING_MODEL_OPTIONS.some((m) => m.id === uploadFormState.embeddingModel) &&
                  uploadFormState.embeddingModel ? (
                    <option value={uploadFormState.embeddingModel}>{uploadFormState.embeddingModel}</option>
                  ) : null}
                </select>
              </label>
            </div>
            <p className="upload-hint">
              {EMBEDDING_MODEL_OPTIONS.find((m) => m.id === uploadFormState.embeddingModel)?.description ??
                t("upload.embeddingModelHint")}
            </p>
            <p className="upload-hint">{t("upload.embeddingModelHint")}</p>
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

      {activeTab === "bulk" && <BulkTestPanel connectionReady={isConnectionReady} />}

      {activeTab === "models" && (
        <section className="panel models-panel">
          <h2>{t("models.title")}</h2>
          <p className="upload-hint models-panel__intro">{t("models.intro")}</p>
          <ul className="model-provider-list" aria-label={t("models.title")}>
            <li className="model-provider-card model-provider-card--system">
              <div className="model-provider-card__header">
                <span className="model-provider-card__name">{t("models.ollama.name")}</span>
                <span className="model-provider-card__badge">{t("models.badgeBuiltin")}</span>
              </div>
              <p className="model-provider-card__description">{t("models.ollama.description")}</p>
              {ollamaModelsBaseUrl ? (
                <p className="model-provider-card__endpoint">
                  <span className="model-provider-card__endpoint-label">{t("models.ollamaEndpoint")}</span>
                  <code className="model-provider-card__endpoint-value">{ollamaModelsBaseUrl}</code>
                </p>
              ) : null}

              <div className="models-active-picker">
                <label className="models-active-picker__label" htmlFor="active-llm-model">
                  {t("models.activeLabel")}
                </label>
                <div className="models-active-picker__row">
                  <select
                    id="active-llm-model"
                    value={chatSettings?.llmModel ?? ""}
                    disabled={!chatSettings || activeModelSaving || ollamaModels.length === 0}
                    onChange={(e) => void selectActiveModel(e.target.value)}
                  >
                    {chatSettings?.llmModel &&
                    !ollamaModels.some((m) => m.name === chatSettings.llmModel) ? (
                      <option value={chatSettings.llmModel}>
                        {chatSettings.llmModel} ({t("models.notInstalled")})
                      </option>
                    ) : null}
                    {ollamaModels.map((row) => (
                      <option key={row.name} value={row.name}>
                        {row.name}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => void loadModelsTab()}
                    disabled={ollamaModelsLoading || activeModelSaving}
                  >
                    {ollamaModelsLoading ? t("models.loading") : t("models.refresh")}
                  </button>
                </div>
                {chatSettings?.llmModel ? (
                  <p className="models-active-current">
                    {t("models.activeCurrent")}: <code>{chatSettings.llmModel}</code>
                  </p>
                ) : null}
                {activeModelMessage ? (
                  <p
                    className={`models-active-feedback${
                      activeModelMessage.startsWith(t("models.activeSaveError"))
                        ? " models-active-feedback--err"
                        : " models-active-feedback--ok"
                    }`}
                    role="status"
                  >
                    {activeModelMessage}
                  </p>
                ) : null}
              </div>

              {ollamaModelsError ? (
                <p className="ollama-models-error" role="alert">
                  {ollamaModelsError}
                </p>
              ) : null}
              {!ollamaModelsLoading && !ollamaModelsError && ollamaModels.length === 0 ? (
                <p className="upload-hint ollama-models-empty">{t("models.empty")}</p>
              ) : null}
              {ollamaModels.length > 0 ? (
                <div className="table-wrapper ollama-models-table-wrap">
                  <table className="ollama-models-table">
                    <thead>
                      <tr>
                        <th>{t("models.colName")}</th>
                        <th>{t("models.colSize")}</th>
                        <th>{t("models.colModified")}</th>
                        <th>{t("models.colAction")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ollamaModels.map((row) => {
                        const isActive = chatSettings?.llmModel === row.name;
                        return (
                          <tr
                            key={row.name}
                            className={isActive ? "ollama-models-row--active" : undefined}
                          >
                            <td className="mono-cell">{row.name}</td>
                            <td>{formatBytes(row.size)}</td>
                            <td>
                              {row.modifiedAt
                                ? (() => {
                                    const d = Date.parse(row.modifiedAt);
                                    return Number.isNaN(d)
                                      ? row.modifiedAt
                                      : new Date(d).toLocaleString();
                                  })()
                                : "—"}
                            </td>
                            <td>
                              {isActive ? (
                                <span className="models-active-badge">{t("models.activeBadge")}</span>
                              ) : (
                                <button
                                  type="button"
                                  disabled={activeModelSaving || !chatSettings}
                                  onClick={() => void selectActiveModel(row.name)}
                                >
                                  {t("models.select")}
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </li>

            <li className="model-provider-card">
              <div className="model-provider-card__header">
                <span className="model-provider-card__name">{t("models.ranking.title")}</span>
              </div>
              <p className="model-provider-card__description">{t("models.ranking.intro")}</p>
              {chatSettings && rankingPercents ? (
                <div className="ranking-weights">
                  <label className="ranking-weight-row">
                    <span className="ranking-weight-row__label">
                      {t("models.ranking.similarity")}
                      <span className="ranking-weight-row__pct">{rankingPercents.similarity}%</span>
                    </span>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      step={1}
                      value={Math.round(chatSettings.rerankSimilarityWeight * 100)}
                      disabled={rankingSaving}
                      onChange={(e) =>
                        patchRankingWeight("rerankSimilarityWeight", Number(e.target.value) / 100)
                      }
                    />
                  </label>
                  <label className="ranking-weight-row">
                    <span className="ranking-weight-row__label">
                      {t("models.ranking.lexical")}
                      <span className="ranking-weight-row__pct">{rankingPercents.lexical}%</span>
                    </span>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      step={1}
                      value={Math.round(chatSettings.rerankLexicalWeight * 100)}
                      disabled={rankingSaving}
                      onChange={(e) =>
                        patchRankingWeight("rerankLexicalWeight", Number(e.target.value) / 100)
                      }
                    />
                  </label>
                  <label className="ranking-weight-row">
                    <span className="ranking-weight-row__label">
                      {t("models.ranking.numeric")}
                      <span className="ranking-weight-row__pct">{rankingPercents.numeric}%</span>
                    </span>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      step={1}
                      value={Math.round(chatSettings.rerankNumericWeight * 100)}
                      disabled={rankingSaving}
                      onChange={(e) =>
                        patchRankingWeight("rerankNumericWeight", Number(e.target.value) / 100)
                      }
                    />
                  </label>
                  <p className="ranking-weights__hint">{t("models.ranking.hint")}</p>
                  <div className="models-active-picker__row">
                    <button
                      type="button"
                      onClick={() => void saveRankingWeights()}
                      disabled={rankingSaving}
                    >
                      {rankingSaving ? t("models.ranking.saving") : t("models.ranking.save")}
                    </button>
                    <button
                      type="button"
                      className="btn-ghost-inline"
                      disabled={rankingSaving}
                      onClick={() => {
                        setChatSettings((prev) =>
                          prev
                            ? {
                                ...prev,
                                ...DEFAULT_RERANK
                              }
                            : prev
                        );
                        setRankingMessage("");
                      }}
                    >
                      {t("models.ranking.reset")}
                    </button>
                  </div>
                  {rankingMessage ? (
                    <p
                      className={`models-active-feedback${
                        rankingMessage.startsWith(t("models.ranking.saveError"))
                          ? " models-active-feedback--err"
                          : " models-active-feedback--ok"
                      }`}
                      role="status"
                    >
                      {rankingMessage}
                    </p>
                  ) : null}
                </div>
              ) : (
                <p className="upload-hint">{t("models.ranking.loading")}</p>
              )}
            </li>
          </ul>
        </section>
      )}

      {activeTab === "settings" && (
        <section className="panel">
          <h2>{t("settings.title")}</h2>
            <div className="input-grid">
              <div className="button-row" style={{ gridColumn: "1 / -1" }}>
                <button type="button" onClick={reopenConnectionSetup}>
                  API-Verbindung ändern
                </button>
              </div>
              {isAdmin ? <ApiKeysPanel /> : null}
              <div className="button-row" style={{ gridColumn: "1 / -1" }}>
                <label style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
                  {t("settings.activePostgresEnv")}
                  <select
                    value={settings.activePostgresEnvironmentId}
                    onChange={(event) => {
                      const nextId = event.target.value;
                      setSettings((old) => {
                        if (!old) return old;
                        const env = old.postgresEnvironments.find((e) => e.id === nextId);
                        if (!env) return { ...old, activePostgresEnvironmentId: nextId };
                        const n = normalizeEnv(env, old);
                        return {
                          ...old,
                          activePostgresEnvironmentId: nextId,
                          embeddingModel: n.embeddingModel,
                          chunkSize: n.chunkSize,
                          chunkOverlap: n.chunkOverlap
                        };
                      });
                      setIsConnectionReady(false);
                    }}
                  >
                    {settings.postgresEnvironments.map((env) => (
                      <option key={env.id} value={env.id}>
                        {env.name} ({env.familyName || env.familyId || env.id})
                      </option>
                    ))}
                  </select>
                  <p className="upload-hint" style={{ margin: "4px 0 0" }}>
                    {t("settings.familyInstanceCount")
                      .replace("{family}", activePgEnvResolved?.familyName || activeFamilyId || "—")
                      .replace("{n}", String(activeFamilyInstanceCount))
                      .replace("{total}", String(totalEnvironmentCount))}
                  </p>
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
                {t("settings.familyName")}
                <input
                  value={getActivePostgresEnv(settings)?.familyName ?? ""}
                  onChange={(event) =>
                    setSettings((old) =>
                      old
                        ? updateActivePostgresEnv(old, {
                            familyName: event.target.value,
                            name: formatInstanceName(
                              event.target.value || "Umgebung",
                              getActivePostgresEnv(old)?.embeddingModel || old.embeddingModel,
                              getActivePostgresEnv(old)?.chunkSize || old.chunkSize,
                              getActivePostgresEnv(old)?.chunkOverlap ?? old.chunkOverlap
                            )
                          })
                        : old
                    )
                  }
                />
              </label>
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
                {t("settings.vectorBackend")}
                <select
                  value={activeVectorBackend}
                  onChange={(event) =>
                    setSettings((old) =>
                      old
                        ? updateActivePostgresEnv(old, {
                            vectorBackend: event.target.value as VectorBackend
                          })
                        : old
                    )
                  }
                >
                  <option value="postgres">{t("settings.vectorBackend.postgres")}</option>
                  <option value="sqlite_embedded">{t("settings.vectorBackend.sqlite")}</option>
                  <option value="qdrant_embedded">{t("settings.vectorBackend.qdrant")}</option>
                </select>
              </label>
              {activeVectorBackend === "postgres" ? (
                <>
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
                        setSettings((old) =>
                          old ? updateActivePostgresEnv(old, { dbPassword: event.target.value }) : old
                        )
                      }
                    />
                  </label>
                </>
              ) : null}
              {activeVectorBackend === "sqlite_embedded" ? (
                <label>
                  {t("settings.sqliteFilePath")}
                  <input
                    value={getActivePostgresEnv(settings)?.sqliteFilePath ?? ""}
                    placeholder={t("settings.sqliteFilePathPlaceholder")}
                    onChange={(event) =>
                      setSettings((old) =>
                        old ? updateActivePostgresEnv(old, { sqliteFilePath: event.target.value }) : old
                      )
                    }
                  />
                </label>
              ) : null}
              {activeVectorBackend === "qdrant_embedded" ? (
                <label>
                  {t("settings.qdrantLocalPath")}
                  <input
                    value={getActivePostgresEnv(settings)?.qdrantLocalPath ?? ""}
                    placeholder={t("settings.qdrantLocalPathPlaceholder")}
                    onChange={(event) =>
                      setSettings((old) =>
                        old ? updateActivePostgresEnv(old, { qdrantLocalPath: event.target.value }) : old
                      )
                    }
                  />
                </label>
              ) : null}
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
              <label className="checkbox-label" style={{ gridColumn: "1 / -1" }}>
                <input
                  type="checkbox"
                  checked={matrixMode}
                  onChange={(event) => setMatrixMode(event.target.checked)}
                />
                {t("settings.matrixMode")}
              </label>
              {matrixMode ? (
                <div className="matrix-create" style={{ gridColumn: "1 / -1", display: "grid", gap: 10 }}>
                  <p className="upload-hint">{t("settings.matrixHint")}</p>
                  <label>
                    {t("settings.matrixFamilyName")}
                    <input
                      value={matrixFamilyName}
                      placeholder={getActivePostgresEnv(settings)?.familyName || getActivePostgresEnv(settings)?.name || ""}
                      onChange={(event) => setMatrixFamilyName(event.target.value)}
                    />
                  </label>
                  <fieldset style={{ border: "1px solid var(--border, #ccc)", padding: 8, margin: 0 }}>
                    <legend>{t("settings.matrixEmbeddings")}</legend>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                      {EMBEDDING_MODEL_OPTIONS.map((model) => {
                        const checked = matrixEmbeddings.includes(model.id);
                        return (
                          <label key={model.id} className="checkbox-label" style={{ marginRight: 8 }}>
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() =>
                                setMatrixEmbeddings((old) =>
                                  checked ? old.filter((id) => id !== model.id) : [...old, model.id]
                                )
                              }
                            />
                            {model.label}
                          </label>
                        );
                      })}
                    </div>
                  </fieldset>
                  <label>
                    {t("settings.matrixChunkSizes")}
                    <input
                      value={matrixChunkSizes}
                      onChange={(event) => setMatrixChunkSizes(event.target.value)}
                      placeholder="800,900,1000"
                    />
                  </label>
                  <label>
                    {t("settings.matrixOverlaps")}
                    <input
                      value={matrixOverlaps}
                      onChange={(event) => setMatrixOverlaps(event.target.value)}
                      placeholder="10,15,20"
                    />
                  </label>
                  <p className="upload-hint">
                    {t("settings.matrixPreview").replace("{n}", String(matrixPreviewCount))}
                  </p>
                  <button
                    type="button"
                    disabled={matrixPreviewCount < 1 || matrixEmbeddings.length < 1 || connectionTestRunning}
                    onClick={() => {
                      void (async () => {
                        const chunks = matrixChunkSizes
                          .split(/[,;\s]+/)
                          .map((s) => Number(s.trim()))
                          .filter((n) => Number.isFinite(n) && n > 0);
                        const overlaps = matrixOverlaps
                          .split(/[,;\s]+/)
                          .map((s) => Number(s.trim()))
                          .filter((n) => Number.isFinite(n) && n >= 0 && n <= 90);
                        const next = addMatrixFamily(settings, {
                          familyName:
                            matrixFamilyName.trim() ||
                            getActivePostgresEnv(settings)?.familyName ||
                            getActivePostgresEnv(settings)?.name ||
                            "Matrix",
                          embeddings: matrixEmbeddings,
                          chunkSizes: chunks,
                          overlaps
                        });
                        const created = next.postgresEnvironments.length - settings.postgresEnvironments.length;
                        setSettings(next);
                        setIsConnectionReady(false);
                        setMatrixMode(false);
                        const persisted = await saveSettings(next);
                        if (persisted) {
                          setHealthMessage(
                            t("settings.matrixSaved").replace("{n}", String(Math.max(0, created)))
                          );
                        }
                      })();
                    }}
                  >
                    {t("settings.matrixCreate")}
                  </button>
                </div>
              ) : null}
              <label>
                {t("settings.chunkSize")}
                <input
                  type="number"
                  value={getActivePostgresEnv(settings)?.chunkSize ?? settings.chunkSize}
                  onChange={(event) => {
                    const chunkSize = Number(event.target.value);
                    setSettings((old) => {
                      if (!old) return old;
                      const env = getActivePostgresEnv(old);
                      const familyName = env?.familyName || env?.name || "Umgebung";
                      const emb = env?.embeddingModel || old.embeddingModel;
                      const overlap = env?.chunkOverlap ?? old.chunkOverlap;
                      return updateActivePostgresEnv(old, {
                        chunkSize,
                        name: formatInstanceName(familyName, emb, chunkSize, overlap)
                      });
                    });
                  }}
                />
              </label>
              <label>
                {t("settings.chunkOverlap")}
                <input
                  type="number"
                  min={0}
                  max={90}
                  value={getActivePostgresEnv(settings)?.chunkOverlap ?? settings.chunkOverlap}
                  onChange={(event) => {
                    const chunkOverlap = Math.max(0, Math.min(90, Number(event.target.value) || 0));
                    setSettings((old) => {
                      if (!old) return old;
                      const env = getActivePostgresEnv(old);
                      const familyName = env?.familyName || env?.name || "Umgebung";
                      const emb = env?.embeddingModel || old.embeddingModel;
                      const chunk = env?.chunkSize || old.chunkSize;
                      return updateActivePostgresEnv(old, {
                        chunkOverlap,
                        name: formatInstanceName(familyName, emb, chunk, chunkOverlap)
                      });
                    });
                  }}
                />
              </label>
              <p className="upload-hint">{t("settings.chunkOverlapHint")}</p>
              <label>
                {t("settings.embeddingModel")}
                <select
                  value={getActivePostgresEnv(settings)?.embeddingModel ?? settings.embeddingModel}
                  onChange={(event) => {
                    const embeddingModel = event.target.value;
                    setSettings((old) => {
                      if (!old) return old;
                      const env = getActivePostgresEnv(old);
                      const familyName = env?.familyName || env?.name || "Umgebung";
                      const chunk = env?.chunkSize || old.chunkSize;
                      const overlap = env?.chunkOverlap ?? old.chunkOverlap;
                      return updateActivePostgresEnv(old, {
                        embeddingModel,
                        name: formatInstanceName(familyName, embeddingModel, chunk, overlap)
                      });
                    });
                  }}
                >
                  {EMBEDDING_MODEL_OPTIONS.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.label}
                      {model.recommended ? " ★" : ""} ({model.dimensions}d · {model.languages})
                    </option>
                  ))}
                  {!EMBEDDING_MODEL_OPTIONS.some(
                    (m) => m.id === (getActivePostgresEnv(settings)?.embeddingModel ?? settings.embeddingModel)
                  ) && (getActivePostgresEnv(settings)?.embeddingModel ?? settings.embeddingModel) ? (
                    <option value={getActivePostgresEnv(settings)?.embeddingModel ?? settings.embeddingModel}>
                      {getActivePostgresEnv(settings)?.embeddingModel ?? settings.embeddingModel}
                    </option>
                  ) : null}
                </select>
              </label>
              <p className="upload-hint">
                {EMBEDDING_MODEL_OPTIONS.find(
                  (m) => m.id === (getActivePostgresEnv(settings)?.embeddingModel ?? settings.embeddingModel)
                )?.description ?? t("settings.embeddingModelHint")}
              </p>
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
