const els = {
  apiBaseUrl: document.getElementById("apiBaseUrl"),
  apiKey: document.getElementById("apiKey"),
  language: document.getElementById("language"),
  questionInput: document.getElementById("questionInput"),
  askBtn: document.getElementById("askBtn"),
  clearBtn: document.getElementById("clearBtn"),
  status: document.getElementById("status"),
  resultPanel: document.getElementById("resultPanel"),
  answerText: document.getElementById("answerText"),
  sourceCount: document.getElementById("sourceCount"),
  sourcesList: document.getElementById("sourcesList"),
  historyCount: document.getElementById("historyCount"),
  historyList: document.getElementById("historyList"),
  feedbackPanel: document.getElementById("feedbackPanel"),
  feedbackUpBtn: document.getElementById("feedbackUpBtn"),
  feedbackDownBtn: document.getElementById("feedbackDownBtn"),
  feedbackComment: document.getElementById("feedbackComment"),
  feedbackStatus: document.getElementById("feedbackStatus"),
};

const SESSION_KEY = "not_qa_console_history_v1";
const API_KEY_STORAGE = "not_qa_api_key_v1";
let sessionHistory = loadHistory();
let currentRequestId = null;
let feedbackSubmitted = false;
renderHistory();

const defaultApiFromConfig =
  typeof window.__RAG_DEFAULT_API_URL__ === "string" && window.__RAG_DEFAULT_API_URL__.trim()
    ? window.__RAG_DEFAULT_API_URL__.trim()
    : "";
if (defaultApiFromConfig) {
  els.apiBaseUrl.value = defaultApiFromConfig;
}

const defaultKeyFromConfig =
  typeof window.__RAG_DEFAULT_API_KEY__ === "string" && window.__RAG_DEFAULT_API_KEY__.trim()
    ? window.__RAG_DEFAULT_API_KEY__.trim()
    : "";
const storedApiKey = localStorage.getItem(API_KEY_STORAGE) || "";
els.apiKey.value = storedApiKey || defaultKeyFromConfig;
els.apiKey.addEventListener("change", () => {
  localStorage.setItem(API_KEY_STORAGE, els.apiKey.value.trim());
});

function apiHeaders(includeJson = true) {
  const headers = {};
  if (includeJson) {
    headers["Content-Type"] = "application/json";
  }
  const key = els.apiKey.value.trim();
  if (key) {
    headers["X-API-Key"] = key;
  }
  return headers;
}

els.askBtn.addEventListener("click", onAsk);
els.clearBtn.addEventListener("click", onClear);
els.feedbackUpBtn.addEventListener("click", () => void submitFeedback(true));
els.feedbackDownBtn.addEventListener("click", () => void submitFeedback(false));
els.questionInput.addEventListener("keydown", (ev) => {
  if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter") {
    onAsk();
  }
});

async function onAsk() {
  const question = els.questionInput.value.trim();
  if (!question) {
    setStatus("Please enter a question.");
    return;
  }

  const base = els.apiBaseUrl.value.trim().replace(/\/$/, "");
  setStatus("Querying local RAG API...");
  els.askBtn.disabled = true;
  resetFeedbackState();

  try {
    const response = await fetch(`${base}/api/chat`, {
      method: "POST",
      headers: apiHeaders(),
      body: JSON.stringify({
        message: question,
        history: [],
        language: els.language.value,
        clientSource: "qa_site",
      }),
    });

    if (!response.ok) {
      const details = await response.text();
      throw new Error(`API ${response.status}: ${details}`);
    }

    const data = await response.json();
    renderResult(question, data);
    pushHistory(question, data);
    setStatus("Done.");
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  } finally {
    els.askBtn.disabled = false;
  }
}

function onClear() {
  sessionHistory = [];
  localStorage.removeItem(SESSION_KEY);
  renderHistory();
  resetFeedbackState();
  els.resultPanel.classList.add("hidden");
  setStatus("Session cleared.");
}

function resetFeedbackState() {
  currentRequestId = null;
  feedbackSubmitted = false;
  els.feedbackComment.value = "";
  els.feedbackStatus.textContent = "";
  els.feedbackPanel.classList.add("hidden");
  els.feedbackUpBtn.disabled = false;
  els.feedbackDownBtn.disabled = false;
}

function renderResult(question, data) {
  els.resultPanel.classList.remove("hidden");
  els.answerText.textContent = data.answer || "No answer returned.";

  const chunks = data.contextChunks || data.context_chunks || [];
  renderSources(chunks);

  if (!chunks.length) {
    els.sourcesList.innerHTML = '<div class="source-item">No source chunks returned.</div>';
  }

  currentRequestId = data.requestId || data.request_id || null;
  if (currentRequestId) {
    els.feedbackPanel.classList.remove("hidden");
  } else {
    els.feedbackPanel.classList.add("hidden");
  }

  setStatus(`Answered: ${truncate(question, 64)}`);
}

async function submitFeedback(helpful) {
  if (!currentRequestId || feedbackSubmitted) {
    return;
  }

  const base = els.apiBaseUrl.value.trim().replace(/\/$/, "");
  const comment = els.feedbackComment.value.trim();
  els.feedbackUpBtn.disabled = true;
  els.feedbackDownBtn.disabled = true;
  els.feedbackStatus.textContent = "Saving feedback...";

  try {
    const response = await fetch(
      `${base}/api/chat/requests/${encodeURIComponent(currentRequestId)}/feedback`,
      {
        method: "POST",
        headers: apiHeaders(),
        body: JSON.stringify({
          helpful,
          comment: comment || undefined,
        }),
      }
    );

    if (!response.ok) {
      const details = await response.text();
      throw new Error(`API ${response.status}: ${details}`);
    }

    feedbackSubmitted = true;
    els.feedbackStatus.textContent = "Thanks for your feedback.";
    setStatus(helpful ? "Feedback saved: helpful." : "Feedback saved: not helpful.");
  } catch (err) {
    els.feedbackUpBtn.disabled = false;
    els.feedbackDownBtn.disabled = false;
    els.feedbackStatus.textContent = `Could not save feedback: ${err.message}`;
  }
}

function renderSources(chunks) {
  els.sourceCount.textContent = `${chunks.length} chunks`;

  els.sourcesList.innerHTML = chunks
    .map((chunk) => {
      const fileName = chunk.fileName || chunk.file_name || "unknown-file";
      const chunkIndex = chunk.chunkIndex ?? chunk.chunk_index ?? "?";
      const score = chunk.score ?? "n/a";
      const text = chunk.text || "";
      return `
        <article class="source-item">
          <div class="source-meta">${escapeHtml(fileName)} | chunk ${escapeHtml(String(chunkIndex))} | score ${escapeHtml(String(score))}</div>
          <p class="source-text">${escapeHtml(text)}</p>
        </article>
      `;
    })
    .join("");
}

function pushHistory(question, data) {
  sessionHistory.unshift({
    at: new Date().toISOString(),
    question,
    answer: data.answer || "",
    sourceCount: (data.contextChunks || data.context_chunks || []).length,
    requestId: data.requestId || data.request_id || null,
  });
  sessionHistory = sessionHistory.slice(0, 50);
  localStorage.setItem(SESSION_KEY, JSON.stringify(sessionHistory));
  renderHistory();
}

function renderHistory() {
  els.historyCount.textContent = `${sessionHistory.length} items`;
  if (!sessionHistory.length) {
    els.historyList.innerHTML = '<div class="history-item">No questions yet.</div>';
    return;
  }

  els.historyList.innerHTML = sessionHistory
    .map(
      (item) => `
      <article class="history-item">
        <div class="history-meta">${escapeHtml(formatDate(item.at))} | ${escapeHtml(String(item.sourceCount))} chunks</div>
        <p class="history-question">Q: ${escapeHtml(item.question)}</p>
        <p class="history-answer">A: ${escapeHtml(truncate(item.answer, 360))}</p>
      </article>
    `
    )
    .join("");
}

function loadHistory() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function setStatus(text) {
  els.status.textContent = text;
}

function truncate(text, max) {
  return text.length > max ? `${text.slice(0, max - 1)}...` : text;
}

function formatDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
