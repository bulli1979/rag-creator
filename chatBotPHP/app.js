// HTTPS deployments use the same-origin PHP proxy to avoid mixed-content requests.
// Plain HTTP and file-based development can call the local API directly.
const PROXY_MODE = window.location.protocol === 'https:';
const API_BASE   = PROXY_MODE ? '.' : 'http://127.0.0.1:8000';

const els = {
  apiBaseUrl: document.getElementById("apiBaseUrl"),
  language: document.getElementById("language"),
  healthDot: document.getElementById("healthDot"),
  healthText: document.getElementById("healthText"),
  questionInput: document.getElementById("questionInput"),
  askBtn: document.getElementById("askBtn"),
  clearBtn: document.getElementById("clearBtn"),
  status: document.getElementById("status"),
  chatPanel: document.getElementById("chatPanel"),
  chatThread: document.getElementById("chatThread"),
  historyCount: document.getElementById("historyCount"),
  historyList: document.getElementById("historyList"),
};

const SESSION_KEY = "not_qa_console_history_v1";
const MAX_QUERY_CHARS = 8000;
const MAX_HISTORY_MESSAGES = 20;
const MAX_HISTORY_CHARS = 40000;
const MAX_PROXY_BODY_BYTES = 60 * 1024;
let sessionHistory = loadHistory();
renderHistory();

// Conversation context sent to the backend so follow-up questions work.
// Each entry: { role: 'user'|'assistant', content: string }
let chatHistory = [];

// Pending log entries (not yet flushed to server).
let pendingLogs = [];

function generateLogId() {
  return Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
}

async function flushLogs() {
  if (pendingLogs.length === 0) return;
  const entries = [...pendingLogs];
  pendingLogs = [];

  try {
    await fetch(`${API_BASE}/proxy.php`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "log", entries }),
    });
  } catch { /* log silently */ }
}

// --- Health check: green/red dot ---
function setHealth(healthy, msg) {
  if (!els.healthDot || !els.healthText) return;
  els.healthDot.className = `health-dot ${healthy ? "healthy" : "unhealthy"}`;
  els.healthText.textContent = msg;
}

async function checkHealth() {
  const url = PROXY_MODE ? `${API_BASE}/proxy.php` : `${(els.apiBaseUrl?.value?.trim().replace(/\/$/, '') ?? API_BASE)}/api/health`;
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ health_check: true })
    });
    if (!res.ok) { setHealth(false, "Backend unreachable"); return; }
    const txt = await res.text();
    let data;
    try { data = JSON.parse(txt); } catch { setHealth(false, "Unresponsive backend"); return; }
    // If it returned an error from proxy.php or API
    if (data.error || (res.status >= 400 && res.status < 500)) { setHealth(false, "Backend unavailable"); return; }
    setHealth(true, "Backend ready");
  } catch {
    setHealth(false, "Cannot reach backend");
  }
}

// Check health on load and every 60 seconds
checkHealth();
setInterval(checkHealth, 60000);

els.askBtn.addEventListener("click", onAsk);
els.clearBtn.addEventListener("click", onClear);
els.questionInput.addEventListener("keydown", (ev) => {
  if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter") {
    onAsk();
  }
});

async function onAsk() {
  const question = els.questionInput.value.trim().slice(0, MAX_QUERY_CHARS);
  if (!question) {
    setStatus("Please enter a question.");
    return;
  }

  const apiUrl = PROXY_MODE
    ? `${API_BASE}/proxy.php`
    : `${(els.apiBaseUrl?.value?.trim().replace(/\/$/, '') ?? API_BASE)}/api/chat`;
  setStatus("Querying RAG API...");
  els.askBtn.disabled = true;

  // Show user bubble immediately
  appendUserBubble(question);
  els.questionInput.value = '';

  // Show typing indicator
  const typingEl = appendTypingIndicator();

  try {
    const payload = buildChatPayload(question);
    const response = await fetch(apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    typingEl.remove();

    if (!response.ok) {
      const details = await response.text();
      throw new Error(`API ${response.status}: ${details}`);
    }

    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      throw new Error(`Backend returned non-JSON: expected JSON but got HTML or whitespace — the backend is likely down or misconfigured.`);
    }
    const answer = data.answer || 'No answer returned.';
    const chunks = data.contextChunks || data.context_chunks || [];
    const citedIds = new Set([...answer.matchAll(/\[(D-[a-f0-9]+-C\d+)\]/gi)].map(match => match[1]));
    const citedChunks = chunks.filter(chunk => citedIds.has(chunk.citationId));

    // Create log entry before rendering the bubble so logId is available for thumb buttons.
    const logId = generateLogId();
    const sources = citedChunks.map(({ text, ...meta }) => {
      const urlMatch = (text || '').match(/https?:\/\/\S+/);
      return { ...meta, url: urlMatch ? urlMatch[0] : (meta.fileName || meta.file_name || '') };
    });
    pendingLogs.push({
      id: logId,
      q: question,
      a: answer,
      lang: els.language?.value ?? 'en',
      sources,
    });
    flushLogs();

    appendAssistantBubble(answer, citedChunks, logId, question, sources);
    pushHistory(question, data, citedChunks.length);
    chatHistory = boundedHistory([
      ...chatHistory,
      { role: 'user', content: question },
      { role: 'assistant', content: answer },
    ]);

    const turns = chatHistory.length / 2;
    setStatus(`Turn ${turns} — type a follow-up or click New Conversation to start fresh.`);
  } catch (err) {
    typingEl.remove();
    appendErrorBubble(err.message);
    setStatus(`Error: ${err.message}`);
  } finally {
    els.askBtn.disabled = false;
    els.questionInput.focus();
  }
}

function buildChatPayload(question) {
  const payload = {
    message: question,
    history: boundedHistory(chatHistory),
    language: els.language?.value ?? 'en',
  };

  while (payload.history.length && encodedSize(payload) > MAX_PROXY_BODY_BYTES) {
    payload.history.splice(0, Math.min(2, payload.history.length));
  }
  return payload;
}

function boundedHistory(history) {
  const selected = [];
  let remainingChars = MAX_HISTORY_CHARS;

  for (const message of history.slice(-MAX_HISTORY_MESSAGES).reverse()) {
    const content = String(message.content ?? '').trim();
    if (!content) continue;
    const boundedContent = content.slice(-remainingChars);
    selected.push({ role: message.role, content: boundedContent });
    remainingChars -= boundedContent.length;
    if (remainingChars === 0) break;
  }

  selected.reverse();
  if (selected[0]?.role === 'assistant') selected.shift();
  return selected;
}

function encodedSize(value) {
  return new TextEncoder().encode(JSON.stringify(value)).byteLength;
}

function onClear() {
  sessionHistory = [];
  chatHistory = [];
  localStorage.removeItem(SESSION_KEY);
  renderHistory();
  els.chatThread.innerHTML = '';
  els.chatPanel.classList.add('hidden');
  setStatus('Idle');
}

function appendUserBubble(question) {
  els.chatPanel.classList.remove('hidden');
  const div = document.createElement('div');
  div.className = 'chat-bubble user-bubble';
  div.textContent = question;
  els.chatThread.appendChild(div);
  div.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function appendAssistantBubble(answer, chunks, logId, question, sources) {
  const wrap = document.createElement('div');
  wrap.className = 'chat-bubble assistant-bubble';

  const answerEl = document.createElement('p');
  answerEl.className = 'answer-text';
  answerEl.textContent = answer;
  wrap.appendChild(answerEl);

  if (chunks.length) {
    const details = document.createElement('details');
    details.className = 'sources-details';
    const summary = document.createElement('summary');
    summary.textContent = `${chunks.length} cited source${chunks.length === 1 ? '' : 's'}`;
    details.appendChild(summary);
    chunks.forEach(chunk => {
      const item = document.createElement('div');
      item.className = 'source-item';
      const title = chunk.title || chunk.fileName || chunk.file_name || 'Unknown document';
      const citationId = chunk.citationId || '';
      const status = chunk.status && chunk.status !== 'active' ? ` | ${chunk.status}` : '';
      const authority = chunk.authority && !String(chunk.authority).startsWith('tier_1') ? ` | ${chunk.authority}` : '';
      item.innerHTML = `<div class="source-meta">${escapeHtml(citationId)} | ${escapeHtml(title)}${escapeHtml(status)}${escapeHtml(authority)}</div><p class="source-text">${escapeHtml(chunk.text || '')}</p>`;
      details.appendChild(item);
    });
    wrap.appendChild(details);
  }

  // Thumbs up / down feedback row.
  if (logId) {
    const fbRow = document.createElement('div');
    fbRow.className = 'feedback-row';

    const upBtn  = document.createElement('button');
    upBtn.className  = 'feedback-btn';
    upBtn.title      = 'Good answer';
    upBtn.textContent = '👍';

    const downBtn = document.createElement('button');
    downBtn.className  = 'feedback-btn';
    downBtn.title      = 'Bad answer';
    downBtn.textContent = '👎';

    function sendFeedback(vote) {
      upBtn.disabled   = true;
      downBtn.disabled = true;
      upBtn.classList.toggle('feedback-selected',   vote === 'up');
      downBtn.classList.toggle('feedback-selected', vote === 'down');

      // Send feedback as its own log entry (same id, only feedback field).
      pendingLogs.push({ id: logId, q: question, a: answer, feedback: vote, sources: sources || [] });
      flushLogs();
    }

    upBtn.addEventListener('click',   () => sendFeedback('up'));
    downBtn.addEventListener('click', () => sendFeedback('down'));

    fbRow.appendChild(upBtn);
    fbRow.appendChild(downBtn);
    wrap.appendChild(fbRow);
  }

  els.chatThread.appendChild(wrap);
  wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function appendTypingIndicator() {
  const div = document.createElement('div');
  div.className = 'chat-bubble assistant-bubble typing-indicator';
  div.innerHTML = '<span></span><span></span><span></span>';
  els.chatThread.appendChild(div);
  div.scrollIntoView({ behavior: 'smooth', block: 'start' });
  return div;
}

function appendErrorBubble(msg) {
  const div = document.createElement('div');
  div.className = 'chat-bubble error-bubble';
  div.textContent = `Error: ${msg}`;
  els.chatThread.appendChild(div);
  div.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function pushHistory(question, data, sourceCount) {
  sessionHistory.unshift({
    at: new Date().toISOString(),
    question,
    answer: data.answer || "",
    sourceCount,
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
