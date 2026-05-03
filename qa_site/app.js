const els = {
  apiBaseUrl: document.getElementById("apiBaseUrl"),
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
};

const SESSION_KEY = "not_qa_console_history_v1";
let sessionHistory = loadHistory();
renderHistory();

els.askBtn.addEventListener("click", onAsk);
els.clearBtn.addEventListener("click", onClear);
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

  try {
    const response = await fetch(`${base}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: question,
        history: [],
        language: els.language.value,
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
  setStatus("Session cleared.");
}

function renderResult(question, data) {
  els.resultPanel.classList.remove("hidden");
  els.answerText.textContent = data.answer || "No answer returned.";

  const chunks = data.contextChunks || data.context_chunks || [];
  renderSources(chunks);

  if (!chunks.length) {
    els.sourcesList.innerHTML = '<div class="source-item">No source chunks returned.</div>';
  }

  setStatus(`Answered: ${truncate(question, 64)}`);
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
