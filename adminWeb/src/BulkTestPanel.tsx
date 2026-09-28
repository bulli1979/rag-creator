import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent, ReactElement } from "react";
import { useI18n } from "./i18n";
import type { TranslationKey } from "./i18n";

export type BatchContextChunk = {
  documentId?: string;
  fileName?: string;
  chunkIndex?: number | null;
  similarity?: number | null;
  text?: string;
};

type BatchItemResult = {
  row_no: number;
  question_id: string;
  question_type: string;
  question: string;
  ground_truth: string;
  answer: string;
  error: string;
  latency_ms: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  tokens_per_second: number | null;
  chunk_count: number;
  chunks_summary: string;
  context_chunks?: BatchContextChunk[];
  judge_answer_relevance: number | null;
  judge_context_relevance: number | null;
  judge_groundedness: number | null;
  judge_answer_correctness: number | null;
  judge_notes: string;
  judge_error: string;
};

export type BatchRunSummary = {
  questionCount: number;
  successCount: number;
  errorCount: number;
  successRate: number;
  latencyMs: { mean: number | null; min: number | null; max: number | null; count: number };
  byType: Record<string, number>;
  judge: Record<string, { mean: number | null; count: number }> | null;
  avgChunkCount: number | null;
  avgTokensPerSecond: number | null;
};

export type BatchChatSettings = {
  temperature: number;
  maxTokens: number;
  topK: number;
  rerankSimilarityWeight: number;
  rerankLexicalWeight: number;
  rerankNumericWeight: number;
  /** null/undefined = Auto (topK×4, max 30) */
  retrievalCandidateK?: number | null;
  systemPrompt: string;
  llmApiKey?: string;
  llmBaseUrl?: string;
  llmModel?: string;
};

export type BatchEvalJudge = {
  llmBaseUrl: string;
  llmApiKey: string;
  llmModel: string;
  temperature: number;
  maxTokens: number;
  maxContextChars: number;
  maxRetries: number;
  retrySleepSec: number;
  claimLevel?: boolean;
};

export type BatchTestSettings = {
  settingsId: string;
  name: string;
  chatSettings: BatchChatSettings;
  evalJudge: BatchEvalJudge;
  createdAt: number;
  updatedAt: number;
};

export type BatchRun = {
  runId: string;
  status: "queued" | "running" | "done" | "error" | "cancelled";
  createdAt: string;
  finishedAt?: string | null;
  fileName: string;
  evaluateAnswers: boolean;
  language?: string | null;
  total: number;
  current: number;
  progress: number;
  message: string;
  error: string;
  llmModel: string;
  environmentId: string;
  environmentName: string;
  settingsId?: string | null;
  settingsName?: string;
  familyRunId?: string | null;
  familyInstanceIndex?: number | null;
  familyInstanceTotal?: number | null;
  settingsSnapshot?: {
    chatSettings?: BatchChatSettings;
    evalJudge?: BatchEvalJudge;
    appSettings?: {
      chunkSize?: number;
      chunkOverlap?: number;
      embeddingModel?: string;
      storeMarkdown?: boolean;
      activePostgresEnvironmentId?: string;
    };
    environment?: {
      id?: string;
      name?: string;
      familyId?: string;
      familyName?: string;
      vectorBackend?: string;
      dbHost?: string;
      dbPort?: number;
      dbName?: string;
      dbUser?: string;
      dbPasswordSet?: boolean;
      dbSchema?: string;
      dbTableName?: string;
      sqliteFilePath?: string;
      qdrantLocalPath?: string;
      embeddingModel?: string;
      chunkSize?: number;
      chunkOverlap?: number;
      isMatrixVariant?: boolean;
    };
    familyRunId?: string;
    familyInstanceIndex?: number;
    familyInstanceTotal?: number;
    runOptions?: { evaluateAnswers?: boolean; language?: string | null };
  };
  summary?: BatchRunSummary & {
    familyRunId?: string;
    familyInstanceIndex?: number;
    familyInstanceTotal?: number;
  };
  results?: BatchItemResult[];
};

type ResultSortKey =
  | "row_no"
  | "question_id"
  | "question_type"
  | "latency_ms"
  | "chunk_count"
  | "judge_answer_relevance"
  | "judge_answer_correctness"
  | "error";

type ColHelpKey =
  | "row_no"
  | "question_id"
  | "question_type"
  | "latency_ms"
  | "chunk_count"
  | "judge_answer_relevance"
  | "judge_answer_correctness"
  | "error"
  | "question"
  | "answer";

function colHelpKey(helpKey: ColHelpKey, part: "title" | "tip" | "body"): TranslationKey {
  return `bulk.colHelp.${helpKey}.${part}` as TranslationKey;
}

type SettingHelpKey =
  | "llmModel"
  | "llmBaseUrl"
  | "llmApiKey"
  | "temperature"
  | "maxTokens"
  | "systemPrompt"
  | "topK"
  | "retrievalCandidateK"
  | "rerankSimilarity"
  | "rerankLexical"
  | "rerankNumeric"
  | "judgeModel"
  | "judgeBaseUrl"
  | "judgeApiKey"
  | "judgeTemperature"
  | "judgeMaxTokens"
  | "judgeMaxContext"
  | "judgeMaxRetries"
  | "judgeRetrySleep"
  | "claimLevel"
  | "profile"
  | "profileName"
  | "file"
  | "language"
  | "evaluate"
  | "environment";

function settingHelpKey(helpKey: SettingHelpKey, part: "title" | "tip" | "body"): TranslationKey {
  return `bulk.settingsHelp.${helpKey}.${part}` as TranslationKey;
}

function ColumnHelp({
  helpKey,
  t,
  onOpen
}: {
  helpKey: ColHelpKey;
  t: (key: TranslationKey) => string;
  onOpen: (helpKey: ColHelpKey) => void;
}): ReactElement {
  const title = t(colHelpKey(helpKey, "title"));
  const tip = t(colHelpKey(helpKey, "tip"));

  function openDialog(e: ReactMouseEvent): void {
    e.preventDefault();
    e.stopPropagation();
    onOpen(helpKey);
  }

  return (
    <button
      type="button"
      className="bulk-col-help"
      title={tip}
      aria-label={title}
      onClick={openDialog}
    >
      i
    </button>
  );
}

function SettingHelp({
  helpKey,
  t,
  onOpen
}: {
  helpKey: SettingHelpKey;
  t: (key: TranslationKey) => string;
  onOpen: (helpKey: SettingHelpKey) => void;
}): ReactElement {
  const title = t(settingHelpKey(helpKey, "title"));
  const tip = t(settingHelpKey(helpKey, "tip"));

  function openDialog(e: ReactMouseEvent): void {
    e.preventDefault();
    e.stopPropagation();
    onOpen(helpKey);
  }

  return (
    <button
      type="button"
      className="bulk-col-help"
      title={tip}
      aria-label={title}
      onClick={openDialog}
    >
      i
    </button>
  );
}

function SettingLabel({
  helpKey,
  label,
  t,
  onOpen
}: {
  helpKey: SettingHelpKey;
  label: string;
  t: (key: TranslationKey) => string;
  onOpen: (helpKey: SettingHelpKey) => void;
}): ReactElement {
  return (
    <span className="bulk-setting-label">
      <span>{label}</span>
      <SettingHelp helpKey={helpKey} t={t} onOpen={onOpen} />
    </span>
  );
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${(v * 100).toFixed(1)} %`;
}

function fmtJudgeScore(
  v: number | null | undefined,
  opts: { evaluateEnabled: boolean }
): string {
  if (v != null && Number.isFinite(v)) return v.toFixed(3);
  if (!opts.evaluateEnabled) return "aus";
  return "—";
}

function avgJudge(summary: BatchRunSummary | null | undefined, key: string): number | null {
  const mean = summary?.judge?.[key]?.mean;
  return mean != null && Number.isFinite(mean) ? mean : null;
}

function snapTopK(run: BatchRun): string {
  const v = run.settingsSnapshot?.chatSettings?.topK;
  return v != null && Number.isFinite(v) ? String(v) : "—";
}

function snapChunkSize(run: BatchRun): string {
  const v = run.settingsSnapshot?.appSettings?.chunkSize;
  return v != null && Number.isFinite(v) ? String(v) : "—";
}

function snapEnvName(run: BatchRun): string {
  return run.settingsSnapshot?.environment?.name || run.environmentName || "—";
}

function snapEmbedding(run: BatchRun): string {
  return run.settingsSnapshot?.appSettings?.embeddingModel || "—";
}

function formatSettingsSnapshotLines(run: BatchRun): string[] {
  const snap = run.settingsSnapshot;
  const chat = snap?.chatSettings;
  const app = snap?.appSettings;
  const env = snap?.environment;
  const judge = snap?.evalJudge;
  const opts = snap?.runOptions;
  const dbTarget =
    env?.vectorBackend === "postgres"
      ? `${env?.dbHost ?? "—"}:${env?.dbPort ?? "—"}/${env?.dbName ?? "—"}`
      : env?.vectorBackend === "sqlite_embedded"
        ? env?.sqliteFilePath || "(auto)"
        : env?.vectorBackend === "qdrant_embedded"
          ? env?.qdrantLocalPath || "(auto)"
          : "—";
  return [
    `Profil: ${run.settingsName || "—"}`,
    `Umgebung: ${env?.name || run.environmentName || "—"} (${env?.id || run.environmentId || "—"})`,
    `Vector-Backend: ${env?.vectorBackend || "—"}`,
    `DB/Pfad: ${dbTarget}`,
    `Schema/Tabelle: ${env?.dbSchema ?? "—"} / ${env?.dbTableName ?? "—"}`,
    `DB-User: ${env?.dbUser || "—"} (Passwort gesetzt: ${env?.dbPasswordSet ? "ja" : "nein"})`,
    `Embedding: ${app?.embeddingModel || "—"}`,
    `Chunk-Size/Overlap: ${app?.chunkSize ?? "—"} / ${app?.chunkOverlap ?? "—"}%`,
    `Store-Markdown: ${app?.storeMarkdown == null ? "—" : app.storeMarkdown ? "ja" : "nein"}`,
    `Chat-Modell: ${chat?.llmModel || run.llmModel || "—"} @ ${chat?.llmBaseUrl || "—"}`,
    `Temperature/MaxTokens: ${chat?.temperature ?? "—"} / ${chat?.maxTokens ?? "—"}`,
    `Top-K / Candidate-K: ${chat?.topK ?? "—"} / ${chat?.retrievalCandidateK ?? "Auto"}`,
    `Rerank S/L/N: ${chat?.rerankSimilarityWeight ?? "—"} / ${chat?.rerankLexicalWeight ?? "—"} / ${chat?.rerankNumericWeight ?? "—"}`,
    `Judge: ${judge?.llmModel || "—"} @ ${judge?.llmBaseUrl || "—"} (T=${judge?.temperature ?? "—"})`,
    `Claim-Level AC/GR: ${judge?.claimLevel === false ? "nein" : "ja"}`,
    `Evaluate/Language: ${(opts?.evaluateAnswers ?? run.evaluateAnswers) ? "ja" : "nein"} / ${opts?.language || run.language || "—"}`
  ];
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function oneLine(text: string | null | undefined, empty = "—"): string {
  const cleaned = (text || "").replace(/\s+/g, " ").trim();
  return cleaned || empty;
}

function multiLineHtml(text: string | null | undefined, empty = "—"): string {
  const cleaned = (text || "").replace(/\r\n/g, "\n").trim();
  if (!cleaned) return empty;
  return escapeHtml(cleaned).replace(/\n/g, "<br/>");
}

function formatRowError(row: BatchItemResult): string {
  const parts = [row.error, row.judge_error].map((s) => (s || "").trim()).filter(Boolean);
  return parts.length ? parts.join(" · ") : "—";
}

function parseCorpusJsonl(raw: string): Array<{ chunkIndex: number; text: string }> {
  const rows: Array<{ chunkIndex: number; text: string }> = [];
  for (const line of raw.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      const parsed = JSON.parse(trimmed) as { chunkIndex?: number; text?: string };
      rows.push({
        chunkIndex: Number.isFinite(Number(parsed.chunkIndex)) ? Number(parsed.chunkIndex) : rows.length,
        text: String(parsed.text || "")
      });
    } catch {
      // ignore malformed lines
    }
  }
  return rows;
}

function fmtNum(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return v.toFixed(digits);
}

function fmtMs(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  if (v >= 1000) return `${(v / 1000).toFixed(2)} s`;
  return `${Math.round(v)} ms`;
}

const DEFAULT_CHAT: BatchChatSettings = {
  llmApiKey: "ollama",
  llmBaseUrl: "http://localhost:11434/v1",
  llmModel: "",
  temperature: 0.3,
  maxTokens: 2048,
  topK: 5,
  rerankSimilarityWeight: 0.9,
  rerankLexicalWeight: 0.05,
  rerankNumericWeight: 0.05,
  retrievalCandidateK: null,
  systemPrompt:
    "You are a helpful assistant that answers questions based on provided documents. Always cite the source file name when possible. Be precise and thorough."
};

const DEFAULT_JUDGE: BatchEvalJudge = {
  llmBaseUrl: "http://localhost:11434/v1",
  llmApiKey: "ollama",
  llmModel: "qwen2.5:latest",
  temperature: 0,
  maxTokens: 1024,
  maxContextChars: 12000,
  maxRetries: 2,
  retrySleepSec: 1.5,
  claimLevel: true
};

function BarChart({
  title,
  items
}: {
  title: string;
  items: { label: string; value: number; max?: number }[];
}) {
  const max = Math.max(0.0001, ...items.map((i) => i.max ?? i.value), 0.0001);
  return (
    <div className="bulk-chart">
      <h4>{title}</h4>
      <div className="bulk-chart__bars">
        {items.map((item) => (
          <div key={item.label} className="bulk-chart__row">
            <span className="bulk-chart__label">{item.label}</span>
            <div className="bulk-chart__track">
              <div
                className="bulk-chart__fill"
                style={{ width: `${Math.max(2, (item.value / max) * 100)}%` }}
              />
            </div>
            <span className="bulk-chart__value">{fmtNum(item.value, 3)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function BulkTestPanel({ connectionReady }: { connectionReady: boolean }) {
  const { t } = useI18n();
  const [file, setFile] = useState<File | null>(null);
  const [evaluateAnswers, setEvaluateAnswers] = useState(true);
  const [language, setLanguage] = useState<"" | "de" | "en">("");
  const [chatSettings, setChatSettings] = useState<BatchChatSettings>(DEFAULT_CHAT);
  const [evalJudge, setEvalJudge] = useState<BatchEvalJudge>(DEFAULT_JUDGE);
  const [environments, setEnvironments] = useState<
    Array<{
      id: string;
      name: string;
      vectorBackend?: string;
      familyId?: string;
      familyName?: string;
      embeddingModel?: string;
      chunkSize?: number;
      chunkOverlap?: number;
    }>
  >([]);
  const [families, setFamilies] = useState<
    Array<{ familyId: string; familyName: string; instanceCount: number; instanceIds: string[] }>
  >([]);
  const [selectedFamilyId, setSelectedFamilyId] = useState("");
  const [runAllFamilyInstances, setRunAllFamilyInstances] = useState(true);
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState("");
  const familyPollIdRef = useRef<string | null>(null);
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [settingsList, setSettingsList] = useState<BatchTestSettings[]>([]);
  const [selectedSettingsId, setSelectedSettingsId] = useState("");
  const [settingsName, setSettingsName] = useState("Mein Test-Profil");
  const [history, setHistory] = useState<BatchRun[]>([]);
  const [historySortBy, setHistorySortBy] = useState("createdAt");
  const [historySortDir, setHistorySortDir] = useState<"asc" | "desc">("desc");
  const [run, setRun] = useState<BatchRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [resultSort, setResultSort] = useState<{ key: ResultSortKey; dir: "asc" | "desc" }>({
    key: "row_no",
    dir: "asc"
  });
  const [colHelpOpen, setColHelpOpen] = useState<ColHelpKey | null>(null);
  const [settingHelpOpen, setSettingHelpOpen] = useState<SettingHelpKey | null>(null);
  const [rowDetail, setRowDetail] = useState<BatchItemResult | null>(null);
  const reportRef = useRef<HTMLElement | null>(null);
  const pollRef = useRef<number | null>(null);

  const reloadHistory = useCallback(async () => {
    if (!window.ragApi.listBatchTestRuns) return;
    const res = await window.ragApi.listBatchTestRuns({
      limit: 50,
      sortBy: historySortBy,
      sortDir: historySortDir
    });
    setHistory(res.runs ?? []);
  }, [historySortBy, historySortDir]);

  const reloadSettings = useCallback(async () => {
    if (!window.ragApi.listBatchTestSettings) return;
    const res = await window.ragApi.listBatchTestSettings();
    setSettingsList(res.settings ?? []);
  }, []);

  async function openChunkDocument(chunk: BatchContextChunk): Promise<void> {
    const docId = (chunk.documentId || "").trim();
    const fileName = chunk.fileName || docId || "Dokument";
    const focusIndex =
      chunk.chunkIndex != null && Number.isFinite(Number(chunk.chunkIndex))
        ? Number(chunk.chunkIndex)
        : null;
    const snippet = chunk.text || "";
    // Fenster synchron öffnen (sonst Popup-Blocker nach await)
    const win = window.open("", "_blank");
    if (!win) {
      setError("Popup blockiert – bitte Popups für diese Seite erlauben.");
      return;
    }
    win.document.open();
    win.document.write(
      `<!DOCTYPE html><html><head><meta charset="utf-8"/><title>${escapeHtml(fileName)}</title></head>` +
        `<body style="font:14px system-ui;background:#0f172a;color:#e2e8f0;padding:16px">Lade Dokument…</body></html>`
    );
    win.document.close();

    const write = (chunks: Array<{ chunkIndex: number; text: string }>, title: string, fallback: string) => {
      const focusIdx = focusIndex;
      let matched = focusIdx != null ? chunks.findIndex((c) => c.chunkIndex === focusIdx) : -1;
      if (matched < 0 && snippet) {
        const needle = snippet.slice(0, 120);
        matched = chunks.findIndex((c) => c.text.includes(needle));
      }
      const bodyChunks =
        chunks.length > 0
          ? chunks
              .map((c, i) => {
                const active = i === matched ? " is-active" : "";
                const id = i === matched ? ' id="chunk-focus"' : "";
                return `<section class="chunk${active}"${id}><h2>Chunk ${escapeHtml(String(c.chunkIndex))}</h2><pre>${escapeHtml(c.text || "—")}</pre></section>`;
              })
              .join("\n")
          : `<section class="chunk is-active" id="chunk-focus"><h2>Chunk</h2><pre>${escapeHtml(fallback || "—")}</pre></section>`;
      win.document.open();
      win.document.write(`<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"/>
<title>${escapeHtml(title)}</title>
<style>
  body { margin: 0; font: 14px/1.45 "Segoe UI", system-ui, sans-serif; background: #0f172a; color: #e2e8f0; }
  header { position: sticky; top: 0; z-index: 2; padding: 12px 16px; background: #020617; border-bottom: 1px solid #334155; }
  header h1 { margin: 0; font-size: 16px; }
  header p { margin: 4px 0 0; color: #94a3b8; font-size: 12px; }
  main { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
  .chunk { border: 1px solid #334155; border-radius: 10px; padding: 12px; background: #111827; }
  .chunk.is-active { border-color: #38bdf8; box-shadow: 0 0 0 1px #38bdf8; background: #0c4a6e33; }
  .chunk h2 { margin: 0 0 8px; font-size: 13px; color: #7dd3fc; }
  pre { margin: 0; white-space: pre-wrap; word-break: break-word; font: inherit; }
</style></head>
<body>
  <header>
    <h1>${escapeHtml(title)}</h1>
    <p>${matched >= 0 ? "Passender Chunk hervorgehoben." : "Dokument / Chunk-Text"}</p>
  </header>
  <main>${bodyChunks}</main>
  <script>
    const el = document.getElementById("chunk-focus");
    if (el) el.scrollIntoView({ behavior: "instant", block: "start" });
  </script>
</body></html>`);
      win.document.close();
    };

    if (!docId) {
      write([], fileName, snippet);
      return;
    }
    try {
      const corpus = await window.ragApi.getCorpus(docId);
      write(parseCorpusJsonl(corpus), `${fileName} · ${docId.slice(0, 12)}…`, snippet);
    } catch (err) {
      write([], `${fileName} (Chunk-Text)`, snippet || (err instanceof Error ? err.message : String(err)));
    }
  }

  const reloadEnvironments = useCallback(async (): Promise<void> => {
    try {
      const [defaults, appSettings] = await Promise.all([
        window.ragApi.getBatchTestDefaults().catch(() => null),
        window.ragApi.getSettings().catch(() => null)
      ]);

      const fromApp = (appSettings?.postgresEnvironments || []).map((env) => ({
        id: String(env.id || "").trim(),
        name: String(env.name || env.id || "").trim(),
        vectorBackend: env.vectorBackend,
        familyId: String(env.familyId || env.id || "").trim(),
        familyName: String(env.familyName || env.name || env.id || "").trim(),
        embeddingModel: env.embeddingModel,
        chunkSize: env.chunkSize,
        chunkOverlap: env.chunkOverlap
      })).filter((env) => env.id);

      const fromDefaults = Array.isArray(defaults?.environments)
        ? defaults.environments
            .map((env) => ({
              id: String((env as { id?: string }).id || "").trim(),
              name: String((env as { name?: string }).name || (env as { id?: string }).id || "").trim(),
              vectorBackend: (env as { vectorBackend?: string }).vectorBackend,
              familyId: String(
                (env as { familyId?: string }).familyId || (env as { id?: string }).id || ""
              ).trim(),
              familyName: String(
                (env as { familyName?: string }).familyName ||
                  (env as { name?: string }).name ||
                  (env as { id?: string }).id ||
                  ""
              ).trim(),
              embeddingModel: (env as { embeddingModel?: string }).embeddingModel,
              chunkSize: (env as { chunkSize?: number }).chunkSize,
              chunkOverlap: (env as { chunkOverlap?: number }).chunkOverlap
            }))
            .filter((env) => env.id)
        : [];

      // App-Settings sind Quelle der Wahrheit; Defaults nur als Fallback
      type EnvRow = {
        id: string;
        name: string;
        vectorBackend?: string;
        familyId: string;
        familyName: string;
        embeddingModel?: string;
        chunkSize?: number;
        chunkOverlap?: number;
      };
      const byId = new Map<string, EnvRow>();
      for (const env of fromDefaults) byId.set(env.id, env);
      for (const env of fromApp) byId.set(env.id, env);
      const envList = Array.from(byId.values());
      setEnvironments(envList);

      const fromFamilies = Array.isArray((defaults as { families?: unknown } | null)?.families)
        ? (
            (
              defaults as {
                families: Array<{
                  familyId?: string;
                  familyName?: string;
                  instanceCount?: number;
                  instanceIds?: string[];
                }>;
              }
            ).families || []
          )
            .map((f) => ({
              familyId: String(f.familyId || "").trim(),
              familyName: String(f.familyName || f.familyId || "").trim(),
              instanceCount: Number(f.instanceCount || (f.instanceIds || []).length || 0),
              instanceIds: Array.isArray(f.instanceIds) ? f.instanceIds.map(String) : []
            }))
            .filter((f) => f.familyId)
        : [];

      const map = new Map<
        string,
        { familyId: string; familyName: string; instanceCount: number; instanceIds: string[] }
      >();
      for (const env of envList) {
        const fid = env.familyId || env.id;
        const cur = map.get(fid) || {
          familyId: fid,
          familyName: env.familyName || env.name || fid,
          instanceCount: 0,
          instanceIds: [] as string[]
        };
        cur.instanceCount += 1;
        cur.instanceIds.push(env.id);
        if (!cur.familyName) cur.familyName = env.familyName || env.name || fid;
        map.set(fid, cur);
      }
      // Familien aus Settings bevorzugen; Defaults nur ergänzen
      for (const f of fromFamilies) {
        if (!map.has(f.familyId)) map.set(f.familyId, f);
      }
      const familyList = Array.from(map.values());
      setFamilies(familyList);

      const preferredEnv =
        String(defaults?.activeEnvironmentId || appSettings?.activePostgresEnvironmentId || "").trim();
      const nextEnv =
        (preferredEnv && envList.some((e) => e.id === preferredEnv) ? preferredEnv : "") ||
        envList[0]?.id ||
        "";
      setSelectedEnvironmentId((prev) =>
        prev && envList.some((e) => e.id === prev) ? prev : nextEnv
      );

      const preferredFamily =
        String((defaults as { activeFamilyId?: string } | null)?.activeFamilyId || "").trim() ||
        envList.find((e) => e.id === nextEnv)?.familyId ||
        familyList[0]?.familyId ||
        "";
      setSelectedFamilyId((prev) =>
        prev && familyList.some((f) => f.familyId === prev)
          ? prev
          : preferredFamily && familyList.some((f) => f.familyId === preferredFamily)
            ? preferredFamily
            : familyList[0]?.familyId || ""
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const [defaults, modelsRes, liveChat] = await Promise.all([
          window.ragApi.getBatchTestDefaults().catch(() => null),
          window.ragApi.listOllamaModels().catch(() => ({ models: [] as { name: string }[] })),
          window.ragApi.getChatSettings().catch(() => null)
        ]);
        const modelNames = (modelsRes.models || []).map((m) => m.name).filter(Boolean);
        setOllamaModels(modelNames);

        await reloadEnvironments();

        const liveModel = liveChat?.llmModel?.trim() || "";
        const chatFromDefaults = (defaults?.chatSettings || {}) as BatchChatSettings;
        setChatSettings((old) => ({
          ...old,
          ...chatFromDefaults,
          llmModel: liveModel || chatFromDefaults.llmModel || old.llmModel || modelNames[0] || ""
        }));
        if (defaults?.evalJudge) {
          setEvalJudge((old) => {
            const next = { ...old, ...(defaults.evalJudge as BatchEvalJudge) };
            if (!next.llmModel && modelNames.includes("qwen2.5:latest")) {
              next.llmModel = "qwen2.5:latest";
            } else if (!next.llmModel && modelNames.length > 0) {
              next.llmModel = modelNames[0] ?? "";
            }
            return next;
          });
        }
        await reloadSettings();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, [reloadEnvironments, reloadSettings]);

  useEffect(() => {
    if (!connectionReady) return;
    void reloadHistory();
  }, [connectionReady, historySortBy, historySortDir, reloadHistory]);

  useEffect(() => {
    if (environments.length === 0) return;
    if (!environments.some((e) => e.id === selectedEnvironmentId)) {
      setSelectedEnvironmentId(environments[0]?.id || "");
    }
  }, [environments, selectedEnvironmentId]);

  useEffect(() => {
    if (families.length === 0) return;
    if (!families.some((f) => f.familyId === selectedFamilyId)) {
      setSelectedFamilyId(families[0]?.familyId || "");
    }
  }, [families, selectedFamilyId]);

  useEffect(() => {
    if (!selectedFamilyId || runAllFamilyInstances) return;
    const inFamily = environments.filter((e) => (e.familyId || e.id) === selectedFamilyId);
    if (inFamily.length > 0 && !inFamily.some((e) => e.id === selectedEnvironmentId)) {
      setSelectedEnvironmentId(inFamily[0]?.id || "");
    }
  }, [selectedFamilyId, runAllFamilyInstances, environments, selectedEnvironmentId]);

  useEffect(() => {
    return () => {
      if (pollRef.current != null) window.clearInterval(pollRef.current);
    };
  }, []);

  function stopPolling(): void {
    if (pollRef.current != null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  function startPolling(runId: string, familyRunId?: string | null): void {
    stopPolling();
    familyPollIdRef.current = familyRunId || null;
    pollRef.current = window.setInterval(() => {
      void (async () => {
        try {
          let next = await window.ragApi.getBatchTestRun(runId);
          const fid = familyPollIdRef.current || next.familyRunId || null;

          if (fid && (next.status === "done" || next.status === "error" || next.status === "cancelled")) {
            const listed = await window.ragApi.listBatchTestRuns({ limit: 100 });
            const siblings = listed.runs.filter((r) => r.familyRunId === fid);
            const active = siblings.find((r) => r.status === "queued" || r.status === "running");
            if (active) {
              setRun(active);
              stopPolling();
              startPolling(active.runId, fid);
              await reloadHistory();
              return;
            }
            const total = next.familyInstanceTotal ?? siblings[0]?.familyInstanceTotal ?? 0;
            const maxIdx = Math.max(0, ...siblings.map((r) => r.familyInstanceIndex ?? 0));
            if (next.status === "done" && total > 0 && maxIdx < total) {
              setRun(next);
              return;
            }
          }

          setRun(next);
          if (next.status === "done" || next.status === "error" || next.status === "cancelled") {
            stopPolling();
            setBusy(false);
            familyPollIdRef.current = null;
            await reloadHistory();
          }
        } catch (err) {
          stopPolling();
          setBusy(false);
          familyPollIdRef.current = null;
          setError(err instanceof Error ? err.message : String(err));
        }
      })();
    }, 1200);
  }

  function applySettingsToForm(s: BatchTestSettings): void {
    setSelectedSettingsId(s.settingsId);
    setSettingsName(s.name);
    setChatSettings({ ...DEFAULT_CHAT, ...s.chatSettings });
    setEvalJudge({ ...DEFAULT_JUDGE, ...s.evalJudge });
  }

  function applySnapshotFromRun(r: BatchRun): void {
    const snap = r.settingsSnapshot;
    if (snap?.chatSettings) setChatSettings({ ...DEFAULT_CHAT, ...snap.chatSettings });
    if (snap?.evalJudge) setEvalJudge({ ...DEFAULT_JUDGE, ...snap.evalJudge });
    if (typeof r.evaluateAnswers === "boolean") setEvaluateAnswers(r.evaluateAnswers);
    if (r.language === "de" || r.language === "en") setLanguage(r.language);
    setSettingsName(`Kopie: ${r.fileName || r.runId.slice(0, 8)}`);
  }

  async function startRun(): Promise<void> {
    if (!file || !connectionReady || !window.ragApi.startBatchTest) return;
    setError("");
    setBusy(true);
    setRun(null);
    familyPollIdRef.current = null;
    try {
      const envId =
        selectedEnvironmentId ||
        environments.find((e) => (e.familyId || e.id) === selectedFamilyId)?.id ||
        environments[0]?.id ||
        undefined;
      const started = await window.ragApi.startBatchTest(file, {
        evaluateAnswers,
        language: language || undefined,
        settingsId: selectedSettingsId || undefined,
        settingsName: settingsName || undefined,
        environmentId: runAllFamilyInstances ? undefined : envId,
        familyId: runAllFamilyInstances ? selectedFamilyId || undefined : undefined,
        runAllInstances: runAllFamilyInstances && Boolean(selectedFamilyId),
        chatSettings: chatSettings as unknown as Record<string, unknown>,
        evalJudge: evalJudge as unknown as Record<string, unknown>
      });
      setRun(started);
      startPolling(started.runId, started.familyRunId);
    } catch (err) {
      setBusy(false);
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function cancelRun(): Promise<void> {
    if (!run?.runId) return;
    try {
      const next = await window.ragApi.cancelBatchTest(run.runId);
      setRun(next);
      await reloadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function saveSettings(): Promise<void> {
    try {
      const saved = await window.ragApi.saveBatchTestSettings({
        settingsId: selectedSettingsId || null,
        name: settingsName || "Test-Profil",
        chatSettings: chatSettings as unknown as Record<string, unknown>,
        evalJudge: evalJudge as unknown as Record<string, unknown>
      });
      setSelectedSettingsId(saved.settingsId);
      setSettingsName(saved.name);
      await reloadSettings();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function deleteSettings(): Promise<void> {
    if (!selectedSettingsId) return;
    if (!window.confirm(t("bulk.settings.deleteConfirm"))) return;
    try {
      await window.ragApi.deleteBatchTestSettings(selectedSettingsId);
      setSelectedSettingsId("");
      setSettingsName("Mein Test-Profil");
      await reloadSettings();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function copySettingsFromCurrentRun(): Promise<void> {
    if (!run?.runId) return;
    try {
      const saved = await window.ragApi.copyBatchTestSettingsFromRun(run.runId, settingsName);
      applySettingsToForm(saved);
      await reloadSettings();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function openHistoryRun(runId: string): Promise<void> {
    try {
      const full = await window.ragApi.getBatchTestRun(runId);
      setRun(full);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function deleteHistoryRun(runId: string): Promise<void> {
    if (!window.confirm(t("bulk.history.deleteConfirm"))) return;
    try {
      await window.ragApi.deleteBatchTestRun(runId);
      if (run?.runId === runId) setRun(null);
      await reloadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  function openReportWindow(width: number, height: number): Window | null {
    // Kein "noopener" in features: sonst liefert window.open oft null, obwohl das Tab offen ist.
    const win = window.open("", "_blank", `width=${width},height=${height}`);
    if (win) {
      try {
        win.opener = null;
      } catch {
        // ignore
      }
    }
    return win;
  }

  function exportPdf(): void {
    if (!reportRef.current) return;
    const win = openReportWindow(1100, 800);
    if (!win) {
      setError(t("bulk.popupBlocked"));
      return;
    }
    const styles = Array.from(document.querySelectorAll('link[rel="stylesheet"], style'))
      .map((el) => el.outerHTML)
      .join("\n");
    win.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Bulk Test Report</title>
      ${styles}
      <style>
        body { background: #fff !important; color: #0f172a !important; padding: 24px; }
        .bulk-report { box-shadow: none !important; border: none !important; }
        .no-print { display: none !important; }
      </style>
    </head><body>${reportRef.current.outerHTML}
    <script>setTimeout(function(){window.print();}, 400);</script>
    </body></html>`);
    win.document.close();
  }

  function buildA4HtmlOverview(source: BatchRun): string {
    const s = source.summary;
    const rows = source.results ?? [];
    const ar = avgJudge(s, "answerRelevance");
    const ac = avgJudge(s, "answerCorrectness");
    const rowHtml = rows
      .map((r) => {
        const err = formatRowError(r);
        return `<tr class="${err !== "—" ? "err" : ""}">
          <td>${r.row_no}</td>
          <td>${escapeHtml(r.question_id || "")}</td>
          <td>${escapeHtml(r.question_type || "—")}</td>
          <td>${escapeHtml(fmtMs(r.latency_ms))}</td>
          <td>${escapeHtml(fmtJudgeScore(r.judge_answer_relevance, { evaluateEnabled: source.evaluateAnswers }))}</td>
          <td>${escapeHtml(fmtJudgeScore(r.judge_answer_correctness, { evaluateEnabled: source.evaluateAnswers }))}</td>
          <td class="wrap">${multiLineHtml(r.question)}</td>
          <td class="wrap">${multiLineHtml(r.answer)}</td>
          <td class="wrap err-col">${multiLineHtml(err === "—" ? "" : err, "—")}</td>
        </tr>`;
      })
      .join("");

    return `<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8"/>
  <title>Bulk-Test ${escapeHtml(source.fileName || source.runId)}</title>
  <style>
    @page { size: A4; margin: 10mm; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font: 10px/1.35 "Segoe UI", system-ui, sans-serif;
      color: #0f172a;
      background: #fff;
    }
    .sheet {
      width: 190mm;
      margin: 0 auto;
      padding: 2mm 0;
    }
    h1 {
      font-size: 14px;
      margin: 0 0 2px;
      break-after: avoid;
      page-break-after: avoid;
    }
    .meta {
      color: #475569;
      margin-bottom: 8px;
      break-after: avoid;
      page-break-after: avoid;
    }
    .settings-box {
      border: 1px solid #cbd5e1;
      border-radius: 4px;
      padding: 6px 8px;
      margin-bottom: 8px;
      background: #f8fafc;
      break-inside: avoid;
      page-break-inside: avoid;
      font-size: 9px;
      line-height: 1.4;
    }
    .settings-box strong { display: block; margin-bottom: 3px; font-size: 10px; }
    .settings-box div { color: #334155; }
    .stats {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 4px;
      margin-bottom: 8px;
      break-inside: avoid;
      page-break-inside: avoid;
    }
    .stat {
      border: 1px solid #cbd5e1;
      border-radius: 4px;
      padding: 4px 6px;
    }
    .stat span { display: block; color: #64748b; font-size: 9px; }
    .stat strong { font-size: 12px; }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    thead {
      display: table-header-group;
    }
    tbody {
      display: table-row-group;
    }
    tr {
      break-inside: avoid;
      page-break-inside: avoid;
    }
    th, td {
      border-bottom: 1px solid #e2e8f0;
      padding: 3px 4px;
      text-align: left;
      vertical-align: top;
      word-break: break-word;
    }
    th {
      background: #f1f5f9;
      font-size: 9px;
    }
    td.meta-col {
      white-space: nowrap;
    }
    td.wrap {
      white-space: normal;
      line-height: 1.35;
    }
    tr.err td { color: #b91c1c; }
    td.err-col { color: #b91c1c; font-size: 9px; }
    .actions { margin-top: 8px; }
    .actions button {
      font: inherit;
      padding: 4px 10px;
      cursor: pointer;
    }
    @media print {
      .actions { display: none; }
      .sheet { width: auto; }
      thead { display: table-header-group; }
      tr { break-inside: avoid; page-break-inside: avoid; }
    }
  </style>
</head>
<body>
  <div class="sheet">
    <h1>Bulk-Test Übersicht</h1>
    <div class="meta">
      ${escapeHtml(source.fileName || "—")} · ${escapeHtml(source.createdAt || "")}
      ${source.finishedAt ? ` → ${escapeHtml(source.finishedAt)}` : ""}
      · ${escapeHtml(source.status)}
      · ${escapeHtml(source.environmentName || "—")}
      · ${escapeHtml(source.llmModel || "—")}
    </div>
    <div class="settings-box">
      <strong>Lauf-Settings (für Vergleich)</strong>
      ${formatSettingsSnapshotLines(source)
        .map((line) => `<div>${escapeHtml(line)}</div>`)
        .join("")}
    </div>
    <div class="stats">
      <div class="stat"><span>Fragen</span><strong>${s?.questionCount ?? rows.length}</strong></div>
      <div class="stat"><span>Erfolg</span><strong>${escapeHtml(fmtPct(s?.successRate))}</strong></div>
      <div class="stat"><span>Latenz Ø</span><strong>${escapeHtml(fmtMs(s?.latencyMs?.mean))}</strong></div>
      <div class="stat"><span>AR Ø</span><strong>${ar != null ? ar.toFixed(3) : "—"}</strong></div>
      <div class="stat"><span>AC Ø</span><strong>${ac != null ? ac.toFixed(3) : "—"}</strong></div>
      <div class="stat"><span>Chunks Ø</span><strong>${escapeHtml(fmtNum(s?.avgChunkCount, 1))}</strong></div>
    </div>
    <table>
      <thead>
        <tr>
          <th style="width:6mm">#</th>
          <th style="width:12mm">ID</th>
          <th style="width:12mm">Typ</th>
          <th style="width:11mm">Latenz</th>
          <th style="width:9mm">AR</th>
          <th style="width:9mm">AC</th>
          <th style="width:34%">Frage</th>
          <th style="width:34%">Antwort</th>
          <th style="width:16%">Fehler</th>
        </tr>
      </thead>
      <tbody>${rowHtml || `<tr><td colspan="9">Keine Ergebnisse</td></tr>`}</tbody>
    </table>
    <div class="actions">
      <button type="button" onclick="window.print()">Drucken / PDF</button>
    </div>
  </div>
</body>
</html>`;
  }

  function writeHtmlToWindow(win: Window, html: string): void {
    win.document.open();
    win.document.write(html);
    win.document.close();
  }

  function exportRunJson(source: BatchRun): void {
    const blob = new Blob([JSON.stringify(source, null, 2)], {
      type: "application/json;charset=utf-8"
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `bulk-test-${source.runId.slice(0, 8)}.json`;
    a.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
  }

  function openA4HtmlOverview(source: BatchRun): void {
    const html = buildA4HtmlOverview(source);
    const win = openReportWindow(900, 1200);
    if (win) {
      writeHtmlToWindow(win, html);
      return;
    }
    // Fallback ohne Popup: Blob-URL im gleichen Tab-Kontext
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener";
    a.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
  }

  async function openA4FromHistory(runId: string): Promise<void> {
    // Fenster sofort im Click-Handler öffnen (sonst blockiert der Browser nach await).
    const win = openReportWindow(900, 1200);
    if (win) {
      writeHtmlToWindow(
        win,
        `<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Lade…</title></head>
         <body style="font:14px system-ui;padding:24px;color:#334155">Lade Testdaten…</body></html>`
      );
    }
    try {
      const full = await window.ragApi.getBatchTestRun(runId);
      setRun(full);
      const html = buildA4HtmlOverview(full);
      if (win && !win.closed) {
        writeHtmlToWindow(win, html);
      } else {
        openA4HtmlOverview(full);
      }
    } catch (err) {
      if (win && !win.closed) win.close();
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  function toggleResultSort(key: ResultSortKey): void {
    setResultSort((old) =>
      old.key === key ? { key, dir: old.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" }
    );
  }

  const sortedResults = useMemo(() => {
    const rows = [...(run?.results ?? [])];
    const { key, dir } = resultSort;
    const mul = dir === "asc" ? 1 : -1;
    rows.sort((a, b) => {
      const av = a[key];
      const bv = b[key];
      if (typeof av === "number" || typeof bv === "number") {
        return ((Number(av) || 0) - (Number(bv) || 0)) * mul;
      }
      return String(av ?? "").localeCompare(String(bv ?? "")) * mul;
    });
    return rows;
  }, [run?.results, resultSort]);

  const summary = run?.summary;
  const judgeItems = useMemo(() => {
    if (!summary?.judge) return [];
    return [
      { key: "answerRelevance", label: t("bulk.metric.answerRelevance") },
      { key: "contextRelevance", label: t("bulk.metric.contextRelevance") },
      { key: "groundedness", label: t("bulk.metric.groundedness") },
      { key: "answerCorrectness", label: t("bulk.metric.correctness") },
      { key: "objectiveCorrectness", label: t("bulk.metric.objCorrectness") }
    ]
      .filter((m) => (summary.judge?.[m.key]?.count ?? 0) > 0 && summary.judge?.[m.key]?.mean != null)
      .map((m) => ({ label: m.label, value: summary.judge![m.key]!.mean ?? 0, max: 1 }));
  }, [summary, t]);

  const typeItems = useMemo(() => {
    if (!summary?.byType) return [];
    return Object.entries(summary.byType).map(([label, value]) => ({ label, value }));
  }, [summary]);

  return (
    <section className="panel bulk-panel">
      <h2>{t("bulk.title")}</h2>
      <p className="upload-hint">{t("bulk.intro")}</p>

      <div className="bulk-run-context" role="status">
        <div>
          <span className="bulk-run-context__label">{t("bulk.context.chatModel")}</span>
          <strong>{chatSettings.llmModel || "—"}</strong>
        </div>
        <div>
          <span className="bulk-run-context__label">{t("bulk.context.judgeModel")}</span>
          <strong>{evalJudge.llmModel || "—"}</strong>
        </div>
        <div>
          <span className="bulk-run-context__label">{t("bulk.context.environment")}</span>
          <strong>
            {runAllFamilyInstances
              ? families.find((f) => f.familyId === selectedFamilyId)?.familyName ||
                selectedFamilyId ||
                "—"
              : environments.find((e) => e.id === selectedEnvironmentId)?.name ||
                selectedEnvironmentId ||
                "—"}
          </strong>
          {run?.familyInstanceIndex && run?.familyInstanceTotal ? (
            <span className="upload-hint" style={{ display: "block" }}>
              {t("bulk.familyProgress")
                .replace("{current}", String(run.familyInstanceIndex))
                .replace("{total}", String(run.familyInstanceTotal))}
            </span>
          ) : null}
        </div>
      </div>

      <div className="bulk-settings-grid">
        <div className="bulk-settings-card">
          <h3>{t("bulk.settings.chatTitle")}</h3>
          <label>
            <SettingLabel
              helpKey="environment"
              label={t("bulk.family")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <select
              value={selectedFamilyId}
              onChange={(e) => {
                const fid = e.target.value;
                setSelectedFamilyId(fid);
                const firstInFamily = environments.find((env) => (env.familyId || env.id) === fid);
                if (firstInFamily) setSelectedEnvironmentId(firstInFamily.id);
              }}
              disabled={busy}
              style={{ cursor: busy ? "wait" : "pointer" }}
            >
              {families.length === 0 ? (
                <option value="">{t("bulk.settings.environmentEmpty")}</option>
              ) : null}
              {families.map((fam) => (
                <option key={fam.familyId} value={fam.familyId}>
                  {fam.familyName || fam.familyId} ({fam.instanceCount})
                </option>
              ))}
            </select>
          </label>
          <p className="upload-hint">
            {t("bulk.familyHint").replace(
              "{n}",
              String(families.find((f) => f.familyId === selectedFamilyId)?.instanceCount || 0)
            )}{" "}
            <button
              type="button"
              className="btn-ghost-inline"
              disabled={busy}
              onClick={() => void reloadEnvironments()}
            >
              {t("bulk.reloadEnvs")}
            </button>
          </p>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={runAllFamilyInstances}
              onChange={(e) => setRunAllFamilyInstances(e.target.checked)}
              disabled={busy}
            />
            {t("bulk.familyAll")}
          </label>
          <label>
            <SettingLabel
              helpKey="environment"
              label={runAllFamilyInstances ? t("bulk.instanceFallback") : t("bulk.settings.environment")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <select
              value={selectedEnvironmentId}
              onChange={(e) => setSelectedEnvironmentId(e.target.value)}
              disabled={busy || runAllFamilyInstances}
              style={{ cursor: busy || runAllFamilyInstances ? "not-allowed" : "pointer" }}
            >
              {environments.length === 0 ? (
                <option value="">{t("bulk.settings.environmentEmpty")}</option>
              ) : null}
              {(runAllFamilyInstances
                ? environments.filter((e) => !selectedFamilyId || (e.familyId || e.id) === selectedFamilyId)
                : environments.filter((e) => !selectedFamilyId || (e.familyId || e.id) === selectedFamilyId)
              ).map((env) => (
                <option key={env.id} value={env.id}>
                  {env.name || env.id}
                  {env.vectorBackend ? ` · ${env.vectorBackend}` : ""}
                </option>
              ))}
            </select>
          </label>
          {runAllFamilyInstances ? (
            <p className="upload-hint">{t("bulk.instanceDisabledHint")}</p>
          ) : null}
          <label>
            <SettingLabel
              helpKey="llmModel"
              label={t("bulk.settings.llmModel")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            {ollamaModels.length > 0 ? (
              <select
                value={chatSettings.llmModel ?? ""}
                onChange={(e) => setChatSettings((o) => ({ ...o, llmModel: e.target.value }))}
              >
                {chatSettings.llmModel && !ollamaModels.includes(chatSettings.llmModel) ? (
                  <option value={chatSettings.llmModel}>
                    {chatSettings.llmModel} ({t("bulk.settings.modelNotListed")})
                  </option>
                ) : null}
                {ollamaModels.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            ) : (
              <input
                value={chatSettings.llmModel ?? ""}
                onChange={(e) => setChatSettings((o) => ({ ...o, llmModel: e.target.value }))}
              />
            )}
          </label>
          <label>
            <SettingLabel
              helpKey="llmBaseUrl"
              label={t("bulk.settings.llmBaseUrl")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <input
              value={chatSettings.llmBaseUrl ?? ""}
              onChange={(e) => setChatSettings((o) => ({ ...o, llmBaseUrl: e.target.value }))}
            />
          </label>
          <label>
            <SettingLabel
              helpKey="llmApiKey"
              label={t("bulk.settings.llmApiKey")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <input
              value={chatSettings.llmApiKey ?? ""}
              onChange={(e) => setChatSettings((o) => ({ ...o, llmApiKey: e.target.value }))}
            />
          </label>
          <label>
            <SettingLabel
              helpKey="temperature"
              label={t("bulk.settings.temperature")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <input
              type="number"
              step="0.05"
              value={chatSettings.temperature}
              onChange={(e) =>
                setChatSettings((o) => ({ ...o, temperature: Number(e.target.value) || 0 }))
              }
            />
          </label>
          <label>
            <SettingLabel
              helpKey="maxTokens"
              label={t("bulk.settings.maxTokens")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <input
              type="number"
              value={chatSettings.maxTokens}
              onChange={(e) =>
                setChatSettings((o) => ({ ...o, maxTokens: Number(e.target.value) || 0 }))
              }
            />
          </label>
          <label>
            <SettingLabel
              helpKey="systemPrompt"
              label={t("bulk.settings.systemPrompt")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <textarea
              rows={4}
              value={chatSettings.systemPrompt}
              onChange={(e) => setChatSettings((o) => ({ ...o, systemPrompt: e.target.value }))}
            />
          </label>
        </div>

        <div className="bulk-settings-card">
          <h3>{t("bulk.settings.retrievalTitle")}</h3>
          <p className="upload-hint">{t("bulk.settings.retrievalHint")}</p>
          <label>
            <SettingLabel
              helpKey="topK"
              label={t("bulk.settings.topK")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <input
              type="number"
              min={1}
              value={chatSettings.topK}
              onChange={(e) => setChatSettings((o) => ({ ...o, topK: Number(e.target.value) || 1 }))}
            />
          </label>
          <label>
            <SettingLabel
              helpKey="retrievalCandidateK"
              label={t("bulk.settings.retrievalCandidateK")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <input
              type="number"
              min={0}
              placeholder={t("bulk.settings.retrievalCandidateKAuto")}
              value={chatSettings.retrievalCandidateK ?? ""}
              onChange={(e) => {
                const raw = e.target.value.trim();
                setChatSettings((o) => ({
                  ...o,
                  retrievalCandidateK: raw === "" ? null : Math.max(1, Number(raw) || 1)
                }));
              }}
            />
          </label>
          <label>
            <SettingLabel
              helpKey="rerankSimilarity"
              label={t("bulk.settings.rerankSimilarity")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <input
              type="number"
              step="0.01"
              min={0}
              value={chatSettings.rerankSimilarityWeight}
              onChange={(e) =>
                setChatSettings((o) => ({
                  ...o,
                  rerankSimilarityWeight: Number(e.target.value) || 0
                }))
              }
            />
          </label>
          <label>
            <SettingLabel
              helpKey="rerankLexical"
              label={t("bulk.settings.rerankLexical")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <input
              type="number"
              step="0.01"
              min={0}
              value={chatSettings.rerankLexicalWeight}
              onChange={(e) =>
                setChatSettings((o) => ({
                  ...o,
                  rerankLexicalWeight: Number(e.target.value) || 0
                }))
              }
            />
          </label>
          <label>
            <SettingLabel
              helpKey="rerankNumeric"
              label={t("bulk.settings.rerankNumeric")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <input
              type="number"
              step="0.01"
              min={0}
              value={chatSettings.rerankNumericWeight}
              onChange={(e) =>
                setChatSettings((o) => ({
                  ...o,
                  rerankNumericWeight: Number(e.target.value) || 0
                }))
              }
            />
          </label>
        </div>

        <div className="bulk-settings-card">
          <h3>{t("bulk.settings.judgeTitle")}</h3>
          <label>
            <SettingLabel
              helpKey="judgeModel"
              label={t("bulk.settings.judgeModel")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            {ollamaModels.length > 0 ? (
              <select
                value={evalJudge.llmModel}
                onChange={(e) => setEvalJudge((o) => ({ ...o, llmModel: e.target.value }))}
              >
                {evalJudge.llmModel && !ollamaModels.includes(evalJudge.llmModel) ? (
                  <option value={evalJudge.llmModel}>
                    {evalJudge.llmModel} ({t("bulk.settings.modelNotListed")})
                  </option>
                ) : null}
                {ollamaModels.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            ) : (
              <input
                value={evalJudge.llmModel}
                onChange={(e) => setEvalJudge((o) => ({ ...o, llmModel: e.target.value }))}
              />
            )}
          </label>
          <label>
            <SettingLabel
              helpKey="judgeBaseUrl"
              label={t("bulk.settings.judgeBaseUrl")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <input
              value={evalJudge.llmBaseUrl}
              onChange={(e) => setEvalJudge((o) => ({ ...o, llmBaseUrl: e.target.value }))}
            />
          </label>
          <label>
            <SettingLabel
              helpKey="judgeApiKey"
              label={t("bulk.settings.judgeApiKey")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <input
              value={evalJudge.llmApiKey}
              onChange={(e) => setEvalJudge((o) => ({ ...o, llmApiKey: e.target.value }))}
            />
          </label>
          <label>
            <SettingLabel
              helpKey="judgeTemperature"
              label={t("bulk.settings.judgeTemperature")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <input
              type="number"
              step="0.05"
              value={evalJudge.temperature}
              onChange={(e) =>
                setEvalJudge((o) => ({ ...o, temperature: Number(e.target.value) || 0 }))
              }
            />
          </label>
          <label>
            <SettingLabel
              helpKey="judgeMaxTokens"
              label={t("bulk.settings.judgeMaxTokens")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <input
              type="number"
              value={evalJudge.maxTokens}
              onChange={(e) =>
                setEvalJudge((o) => ({ ...o, maxTokens: Number(e.target.value) || 0 }))
              }
            />
          </label>
          <label>
            <SettingLabel
              helpKey="judgeMaxContext"
              label={t("bulk.settings.judgeMaxContext")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <input
              type="number"
              value={evalJudge.maxContextChars}
              onChange={(e) =>
                setEvalJudge((o) => ({ ...o, maxContextChars: Number(e.target.value) || 0 }))
              }
            />
          </label>
          <label>
            <SettingLabel
              helpKey="judgeMaxRetries"
              label={t("bulk.settings.judgeMaxRetries")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <input
              type="number"
              value={evalJudge.maxRetries}
              onChange={(e) =>
                setEvalJudge((o) => ({ ...o, maxRetries: Number(e.target.value) || 0 }))
              }
            />
          </label>
          <label>
            <SettingLabel
              helpKey="judgeRetrySleep"
              label={t("bulk.settings.judgeRetrySleep")}
              t={t}
              onOpen={setSettingHelpOpen}
            />
            <input
              type="number"
              step="0.1"
              value={evalJudge.retrySleepSec}
              onChange={(e) =>
                setEvalJudge((o) => ({ ...o, retrySleepSec: Number(e.target.value) || 0 }))
              }
            />
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={evalJudge.claimLevel !== false}
              disabled={busy}
              onChange={(e) => setEvalJudge((o) => ({ ...o, claimLevel: e.target.checked }))}
            />
            <span className="bulk-setting-label">
              <span>{t("bulk.settings.claimLevel")}</span>
              <SettingHelp helpKey="claimLevel" t={t} onOpen={setSettingHelpOpen} />
            </span>
          </label>
        </div>
      </div>

      <div className="bulk-setup input-grid">
        <label>
          <SettingLabel
            helpKey="profile"
            label={t("bulk.settings.profile")}
            t={t}
            onOpen={setSettingHelpOpen}
          />
          <select
            value={selectedSettingsId}
            onChange={(e) => {
              const id = e.target.value;
              setSelectedSettingsId(id);
              const found = settingsList.find((s) => s.settingsId === id);
              if (found) applySettingsToForm(found);
            }}
          >
            <option value="">{t("bulk.settings.profileNone")}</option>
            {settingsList.map((s) => (
              <option key={s.settingsId} value={s.settingsId}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <SettingLabel
            helpKey="profileName"
            label={t("bulk.settings.profileName")}
            t={t}
            onOpen={setSettingHelpOpen}
          />
          <input value={settingsName} onChange={(e) => setSettingsName(e.target.value)} />
        </label>
        <label className="bulk-file-label">
          <SettingLabel helpKey="file" label={t("bulk.file")} t={t} onOpen={setSettingHelpOpen} />
          <input
            type="file"
            accept=".yaml,.yml,.json,.csv"
            disabled={busy}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          {file ? <span className="bulk-file-name">{file.name}</span> : null}
        </label>
        <label>
          <SettingLabel helpKey="language" label={t("bulk.language")} t={t} onOpen={setSettingHelpOpen} />
          <select
            value={language}
            disabled={busy}
            onChange={(e) => setLanguage(e.target.value as "" | "de" | "en")}
          >
            <option value="">{t("bulk.languageAuto")}</option>
            <option value="de">DE</option>
            <option value="en">EN</option>
          </select>
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={evaluateAnswers}
            disabled={busy}
            onChange={(e) => setEvaluateAnswers(e.target.checked)}
          />
          <span className="bulk-setting-label">
            <span>{t("bulk.evaluate")}</span>
            <SettingHelp helpKey="evaluate" t={t} onOpen={setSettingHelpOpen} />
          </span>
        </label>
      </div>
      <p className="upload-hint">{t("bulk.fileHint")}</p>

      <div className="button-row">
        <button type="button" onClick={() => void saveSettings()}>
          {t("bulk.settings.save")}
        </button>
        <button
          type="button"
          className="btn-danger"
          onClick={() => void deleteSettings()}
          disabled={!selectedSettingsId}
        >
          {t("bulk.settings.delete")}
        </button>
        <button
          type="button"
          onClick={() => void copySettingsFromCurrentRun()}
          disabled={!run}
        >
          {t("bulk.settings.copyFromRun")}
        </button>
        <button type="button" disabled={!file || !connectionReady || busy} onClick={() => void startRun()}>
          {busy ? t("bulk.running") : t("bulk.start")}
        </button>
        {busy && run ? (
          <button type="button" className="btn-danger" onClick={() => void cancelRun()}>
            {t("bulk.cancel")}
          </button>
        ) : null}
        {run && (run.status === "done" || run.status === "cancelled" || run.status === "error") ? (
          <>
            <button type="button" onClick={exportPdf}>
              {t("bulk.exportPdf")}
            </button>
            <button type="button" onClick={() => openA4HtmlOverview(run)}>
              {t("bulk.history.htmlA4")}
            </button>
            <button type="button" onClick={() => exportRunJson(run)}>
              {t("bulk.exportJson")}
            </button>
            <button type="button" onClick={() => applySnapshotFromRun(run)}>
              {t("bulk.settings.loadFromRun")}
            </button>
          </>
        ) : null}
      </div>

      {!connectionReady ? <p className="upload-hint">{t("settings.testFirst")}</p> : null}
      {error ? <p className="connection-error">{error}</p> : null}

      {run ? (
        <div className="bulk-progress">
          <div className="bulk-progress__meta">
            <span>
              {t("bulk.status")}: <strong>{run.status}</strong>
            </span>
            <span>
              {run.current}/{run.total} · {run.progress}%
            </span>
          </div>
          <div className="bulk-progress__track">
            <div className="bulk-progress__fill" style={{ width: `${run.progress}%` }} />
          </div>
          <p className="upload-hint">{run.message}</p>
          {run.error ? <p className="connection-error">{run.error}</p> : null}
        </div>
      ) : null}

      <div className="bulk-history">
        <div className="bulk-history__header">
          <h3>{t("bulk.history.title")}</h3>
          <div className="bulk-history__sort">
            <label>
              {t("bulk.history.sortBy")}
              <select
                value={historySortBy}
                onChange={(e) => setHistorySortBy(e.target.value)}
              >
                <option value="createdAt">{t("bulk.history.col.created")}</option>
                <option value="successRate">{t("bulk.history.col.success")}</option>
                <option value="latencyMean">{t("bulk.history.col.latency")}</option>
                <option value="arMean">{t("bulk.history.col.ar")}</option>
                <option value="acMean">{t("bulk.history.col.ac")}</option>
                <option value="status">{t("bulk.history.col.status")}</option>
                <option value="fileName">{t("bulk.history.col.file")}</option>
              </select>
            </label>
            <button
              type="button"
              onClick={() => {
                setHistorySortDir((d) => (d === "asc" ? "desc" : "asc"));
              }}
            >
              {historySortDir === "asc" ? "↑" : "↓"}
            </button>
            <button type="button" onClick={() => void reloadHistory()}>
              {t("bulk.history.refresh")}
            </button>
          </div>
        </div>
        <div className="bulk-history__table-wrap">
          <table className="bulk-results-table">
            <thead>
              <tr>
                <th>{t("bulk.history.col.created")}</th>
                <th>{t("bulk.history.col.file")}</th>
                <th>{t("bulk.history.col.status")}</th>
                <th>{t("bulk.history.col.success")}</th>
                <th>{t("bulk.history.col.latency")}</th>
                <th>{t("bulk.history.col.ar")}</th>
                <th>{t("bulk.history.col.ac")}</th>
                <th>{t("bulk.history.col.env")}</th>
                <th>{t("bulk.history.col.model")}</th>
                <th>{t("bulk.history.col.embedding")}</th>
                <th>{t("bulk.history.col.topK")}</th>
                <th>{t("bulk.history.col.chunk")}</th>
                <th>{t("bulk.history.col.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.runId} className={run?.runId === h.runId ? "is-active-row" : ""}>
                  <td>{h.createdAt}</td>
                  <td>{h.fileName}</td>
                  <td>{h.status}</td>
                  <td>{fmtPct(h.summary?.successRate)}</td>
                  <td>{fmtMs(h.summary?.latencyMs?.mean)}</td>
                  <td>{fmtNum(avgJudge(h.summary, "answerRelevance"), 3)}</td>
                  <td>{fmtNum(avgJudge(h.summary, "answerCorrectness"), 3)}</td>
                  <td title={h.settingsSnapshot?.environment?.id || h.environmentId}>{snapEnvName(h)}</td>
                  <td className="bulk-cell-oneline" title={h.settingsSnapshot?.chatSettings?.llmModel || h.llmModel}>
                    {h.settingsSnapshot?.chatSettings?.llmModel || h.llmModel || "—"}
                  </td>
                  <td className="bulk-cell-oneline" title={snapEmbedding(h)}>
                    {snapEmbedding(h)}
                  </td>
                  <td>{snapTopK(h)}</td>
                  <td>{snapChunkSize(h)}</td>
                  <td className="bulk-history__actions">
                    <button type="button" onClick={() => void openHistoryRun(h.runId)}>
                      {t("bulk.history.open")}
                    </button>
                    <button type="button" onClick={() => void openA4FromHistory(h.runId)}>
                      {t("bulk.history.htmlA4")}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        void (async () => {
                          try {
                            const full = await window.ragApi.getBatchTestRun(h.runId);
                            exportRunJson(full);
                          } catch (err) {
                            setError(err instanceof Error ? err.message : String(err));
                          }
                        })();
                      }}
                    >
                      {t("bulk.exportJson")}
                    </button>
                    <button type="button" onClick={() => applySnapshotFromRun(h)}>
                      {t("bulk.settings.loadFromRun")}
                    </button>
                    <button type="button" className="btn-danger" onClick={() => void deleteHistoryRun(h.runId)}>
                      {t("bulk.history.delete")}
                    </button>
                  </td>
                </tr>
              ))}
              {history.length === 0 ? (
                <tr>
                  <td colSpan={13}>{t("bulk.history.empty")}</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      {run &&
      (run.status === "done" ||
        run.status === "cancelled" ||
        (run.status === "error" && (run.results?.length ?? 0) > 0)) ? (
        <article className="bulk-report" ref={reportRef}>
          <header className="bulk-report__header">
            <div>
              <h3>{t("bulk.reportTitle")}</h3>
              <p>
                {run.fileName} · {run.createdAt}
                {run.finishedAt ? ` → ${run.finishedAt}` : ""}
              </p>
            </div>
            <div className="bulk-report__meta">
              <div>
                <span>{t("bulk.env")}</span>
                <strong>
                  {run.environmentName || "—"} ({run.environmentId || "—"})
                </strong>
              </div>
              <div>
                <span>{t("bulk.model")}</span>
                <strong>{run.llmModel || "—"}</strong>
              </div>
              {run.settingsName ? (
                <div>
                  <span>{t("bulk.settings.profile")}</span>
                  <strong>{run.settingsName}</strong>
                </div>
              ) : null}
            </div>
          </header>

          {run.settingsSnapshot ? (
            <div className="bulk-settings-snapshot">
              <h4>{t("bulk.settings.snapshotTitle")}</h4>
              <ul>
                {formatSettingsSnapshotLines(run).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {summary ? (
            <>
              <div className="bulk-stat-grid">
                <div className="bulk-stat">
                  <span>{t("bulk.stat.questions")}</span>
                  <strong>{summary.questionCount}</strong>
                </div>
                <div className="bulk-stat">
                  <span>{t("bulk.stat.success")}</span>
                  <strong>{fmtPct(summary.successRate)}</strong>
                </div>
                <div className="bulk-stat">
                  <span>{t("bulk.stat.errors")}</span>
                  <strong>{summary.errorCount}</strong>
                </div>
                <div className="bulk-stat">
                  <span>{t("bulk.stat.latency")}</span>
                  <strong>{fmtMs(summary.latencyMs.mean)}</strong>
                </div>
                <div className="bulk-stat">
                  <span>{t("bulk.stat.chunks")}</span>
                  <strong>{fmtNum(summary.avgChunkCount, 1)}</strong>
                </div>
                <div className="bulk-stat">
                  <span>{t("bulk.stat.tps")}</span>
                  <strong>{fmtNum(summary.avgTokensPerSecond, 2)}</strong>
                </div>
                <div className="bulk-stat">
                  <span>{t("bulk.stat.ar")}</span>
                  <strong>{fmtNum(avgJudge(summary, "answerRelevance"), 3)}</strong>
                </div>
                <div className="bulk-stat">
                  <span>{t("bulk.stat.ac")}</span>
                  <strong>{fmtNum(avgJudge(summary, "answerCorrectness"), 3)}</strong>
                </div>
              </div>
              <div className="bulk-charts">
                {typeItems.length > 0 ? <BarChart title={t("bulk.chart.byType")} items={typeItems} /> : null}
                {judgeItems.length > 0 ? <BarChart title={t("bulk.chart.judge")} items={judgeItems} /> : null}
                {summary.latencyMs.mean != null ? (
                  <BarChart
                    title={t("bulk.chart.latency")}
                    items={[
                      { label: "min", value: summary.latencyMs.min ?? 0 },
                      { label: "Ø", value: summary.latencyMs.mean ?? 0 },
                      { label: "max", value: summary.latencyMs.max ?? 0 }
                    ]}
                  />
                ) : null}
              </div>
            </>
          ) : null}

          <div className="bulk-results-table-wrap">
            <h4>{t("bulk.results")}</h4>
            <table className="bulk-results-table">
              <thead>
                <tr>
                  {(
                    [
                      ["row_no", "#", "row_no"],
                      ["question_id", "ID", "question_id"],
                      ["question_type", t("bulk.col.type"), "question_type"],
                      ["latency_ms", t("bulk.col.latency"), "latency_ms"],
                      ["chunk_count", t("bulk.col.chunks"), "chunk_count"],
                      ["judge_answer_relevance", "AR", "judge_answer_relevance"],
                      ["judge_answer_correctness", "AC", "judge_answer_correctness"],
                      ["error", t("bulk.col.error"), "error"]
                    ] as [ResultSortKey, string, ColHelpKey][]
                  ).map(([key, label, helpKey]) => (
                    <th key={key}>
                      <span className="bulk-th-label">
                        <button type="button" className="bulk-sort-btn" onClick={() => toggleResultSort(key)}>
                          {label}
                          {resultSort.key === key ? (resultSort.dir === "asc" ? " ↑" : " ↓") : ""}
                        </button>
                        <ColumnHelp helpKey={helpKey} t={t} onOpen={setColHelpOpen} />
                      </span>
                    </th>
                  ))}
                  <th>
                    <span className="bulk-th-label">
                      {t("bulk.col.question")}
                      <ColumnHelp helpKey="question" t={t} onOpen={setColHelpOpen} />
                    </span>
                  </th>
                  <th>
                    <span className="bulk-th-label">
                      {t("bulk.col.answer")}
                      <ColumnHelp helpKey="answer" t={t} onOpen={setColHelpOpen} />
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedResults.map((row) => (
                  <tr
                    key={`${row.row_no}-${row.question_id}`}
                    className={`bulk-row-clickable${row.error || row.judge_error ? " is-error" : ""}`}
                    onClick={() => setRowDetail(row)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setRowDetail(row);
                      }
                    }}
                    tabIndex={0}
                    title={t("bulk.rowDetail.hint")}
                  >
                    <td>{row.row_no}</td>
                    <td>{row.question_id}</td>
                    <td>{row.question_type || "—"}</td>
                    <td>{fmtMs(row.latency_ms)}</td>
                    <td>{row.chunk_count}</td>
                    <td>
                      {fmtJudgeScore(row.judge_answer_relevance, {
                        evaluateEnabled: run.evaluateAnswers
                      })}
                    </td>
                    <td>
                      {fmtJudgeScore(row.judge_answer_correctness, {
                        evaluateEnabled: run.evaluateAnswers
                      })}
                    </td>
                    <td className="bulk-cell-error bulk-cell-oneline" title={formatRowError(row)}>
                      {oneLine(formatRowError(row))}
                    </td>
                    <td className="bulk-cell-text bulk-cell-oneline" title={row.question}>
                      {oneLine(row.question)}
                    </td>
                    <td className="bulk-cell-text bulk-cell-oneline" title={row.answer || undefined}>
                      {oneLine(row.answer)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      ) : null}

      {colHelpOpen ? (
        <div
          className="bulk-help-overlay"
          role="presentation"
          onClick={() => setColHelpOpen(null)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setColHelpOpen(null);
          }}
        >
          <div
            className="bulk-help-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="bulk-help-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="bulk-help-title">{t(colHelpKey(colHelpOpen, "title"))}</h3>
            <p>{t(colHelpKey(colHelpOpen, "body"))}</p>
            <button type="button" onClick={() => setColHelpOpen(null)}>
              {t("bulk.colHelp.close")}
            </button>
          </div>
        </div>
      ) : null}

      {settingHelpOpen ? (
        <div
          className="bulk-help-overlay"
          role="presentation"
          onClick={() => setSettingHelpOpen(null)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setSettingHelpOpen(null);
          }}
        >
          <div
            className="bulk-help-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="bulk-setting-help-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="bulk-setting-help-title">{t(settingHelpKey(settingHelpOpen, "title"))}</h3>
            <p>{t(settingHelpKey(settingHelpOpen, "body"))}</p>
            <button type="button" onClick={() => setSettingHelpOpen(null)}>
              {t("bulk.colHelp.close")}
            </button>
          </div>
        </div>
      ) : null}

      {rowDetail ? (
        <div
          className="bulk-help-overlay"
          role="presentation"
          onClick={() => setRowDetail(null)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setRowDetail(null);
          }}
        >
          <div
            className="bulk-help-dialog bulk-row-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="bulk-row-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="bulk-row-title">
              {t("bulk.rowDetail.title")} #{rowDetail.row_no} · {rowDetail.question_id || "—"}
            </h3>
            <dl className="bulk-row-dialog__grid">
              <dt>{t("bulk.col.type")}</dt>
              <dd>{rowDetail.question_type || "—"}</dd>
              <dt>{t("bulk.col.latency")}</dt>
              <dd>{fmtMs(rowDetail.latency_ms)}</dd>
              <dt>{t("bulk.col.chunks")}</dt>
              <dd>{rowDetail.chunk_count}</dd>
              <dt>AR</dt>
              <dd>
                {fmtJudgeScore(rowDetail.judge_answer_relevance, {
                  evaluateEnabled: Boolean(run?.evaluateAnswers)
                })}
              </dd>
              <dt>AC</dt>
              <dd>
                {fmtJudgeScore(rowDetail.judge_answer_correctness, {
                  evaluateEnabled: Boolean(run?.evaluateAnswers)
                })}
              </dd>
              <dt>CR</dt>
              <dd>{fmtNum(rowDetail.judge_context_relevance, 3)}</dd>
              <dt>GR</dt>
              <dd>{fmtNum(rowDetail.judge_groundedness, 3)}</dd>
              <dt>{t("bulk.rowDetail.errorChat")}</dt>
              <dd className="bulk-cell-error bulk-row-dialog__block">
                {(rowDetail.error || "").trim() || "—"}
              </dd>
              <dt>{t("bulk.rowDetail.errorJudge")}</dt>
              <dd className="bulk-cell-error bulk-row-dialog__block">
                {(rowDetail.judge_error || "").trim() || "—"}
              </dd>
              <dt>{t("bulk.rowDetail.notes")}</dt>
              <dd>{rowDetail.judge_notes || "—"}</dd>
              <dt>{t("bulk.rowDetail.groundTruth")}</dt>
              <dd className="bulk-row-dialog__block">{rowDetail.ground_truth || "—"}</dd>
              <dt>{t("bulk.col.question")}</dt>
              <dd className="bulk-row-dialog__block">{rowDetail.question || "—"}</dd>
              <dt>{t("bulk.col.answer")}</dt>
              <dd className="bulk-row-dialog__block">{rowDetail.answer || "—"}</dd>
              <dt>{t("bulk.rowDetail.chunksSummary")}</dt>
              <dd className="bulk-row-dialog__block">
                {(rowDetail.context_chunks?.length ?? 0) > 0 ? (
                  <>
                    <p className="upload-hint bulk-chunk-hint">{t("bulk.rowDetail.chunkClickHint")}</p>
                    <ul className="bulk-chunk-list">
                      {rowDetail.context_chunks!.map((ch, idx) => {
                        const label = `${idx + 1}. ${ch.fileName || "?"} #c${ch.chunkIndex ?? "?"} · sim=${
                          ch.similarity != null && Number.isFinite(Number(ch.similarity))
                            ? Number(ch.similarity).toFixed(3)
                            : "—"
                        }`;
                        return (
                          <li key={`${ch.documentId || "x"}-${ch.chunkIndex}-${idx}`}>
                            <button
                              type="button"
                              className="bulk-chunk-link"
                              title={t("bulk.rowDetail.chunkOpen")}
                              onClick={() => void openChunkDocument(ch)}
                            >
                              {label}
                            </button>
                            {ch.text ? (
                              <div className="bulk-chunk-preview">
                                {(() => {
                                  const cleaned = (ch.text || "").replace(/\s+/g, " ").trim();
                                  return cleaned.length > 160 ? `${cleaned.slice(0, 157)}…` : cleaned;
                                })()}
                              </div>
                            ) : null}
                          </li>
                        );
                      })}
                    </ul>
                  </>
                ) : (
                  rowDetail.chunks_summary || "—"
                )}
              </dd>
              <dt>{t("bulk.rowDetail.tokens")}</dt>
              <dd>
                {fmtNum(rowDetail.prompt_tokens, 0)} / {fmtNum(rowDetail.completion_tokens, 0)} /{" "}
                {fmtNum(rowDetail.total_tokens, 0)}
                {rowDetail.tokens_per_second != null
                  ? ` · ${fmtNum(rowDetail.tokens_per_second, 2)} tok/s`
                  : ""}
              </dd>
            </dl>
            <button type="button" onClick={() => setRowDetail(null)}>
              {t("bulk.colHelp.close")}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
