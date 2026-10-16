
/* NOTBot Admin — frontend */
'use strict';

// ── state ────────────────────────────────────────────────────────────
let chatHistory = [];
let appSettings = null;   // full /api/settings response
let chatSettings = null;  // full /api/chat/settings response
let editingEnvId = null;

// ── helpers ──────────────────────────────────────────────────────────
function qs(sel) { return document.querySelector(sel); }

function toast(msg, type = 'success', ms = 3500) {
  const el = qs('#toast');
  el.textContent = msg;
  el.className = 'toast ' + type;
  el.style.display = 'block';
  clearTimeout(el._t);
  el._t = setTimeout(() => { el.style.display = 'none'; }, ms);
}

function setHealth(online, msg) {
  const b = qs('#health-badge');
  if (online) {
    b.className = 'health online';
    b.innerHTML = '<span class="dot green"></span> ' + (msg || 'Backend online');
  } else {
    b.className = 'health offline';
    b.innerHTML = '<span class="dot red"></span> ' + (msg || 'Backend offline');
  }
}

// Lightweight Markdown → HTML (handles most common patterns)
function md(text) {
  if (!text) return '';
  let h = text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    // code blocks (must come before inline code)
    .replace(/```[\w]*\n?([\s\S]*?)```/g, (_,c)=>'<pre><code>'+c.trim()+'</code></pre>')
    // inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // headings
    .replace(/^### (.+)$/gm,'<h3>$1</h3>')
    .replace(/^## (.+)$/gm,'<h2>$1</h2>')
    .replace(/^# (.+)$/gm,'<h1>$1</h1>')
    // bold / italic
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,'<em>$1</em>')
    // blockquote
    .replace(/^> (.+)$/gm,'<blockquote>$1</blockquote>')
    // unordered list
    .replace(/^\s*[-*+] (.+)$/gm,'<li>$1</li>')
    // ordered list
    .replace(/^\s*\d+\. (.+)$/gm,'<li>$1</li>')
    // links
    .replace(/\[([^\]]+)]\((https?:\/\/[^)]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>')
    // bare URLs
    .replace(/(?<![">])(https?:\/\/[^\s<>'"]+)/g,'<a href="$1" target="_blank" rel="noopener">$1</a>')
    // line breaks to <br> (only outside block elements)
    .replace(/\n/g,'<br>');
  // Wrap consecutive <li> in <ul>
  h = h.replace(/(<li>.*?<\/li>(<br>)?)+/g, m => '<ul>' + m.replace(/<br>/g,'') + '</ul>');
  return h;
}

// ── tabs ─────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    qs('#tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'llm')  loadLlmSettings();
    if (btn.dataset.tab === 'db')   loadDbSettings();
  });
});

// ── health check ─────────────────────────────────────────────────────
async function checkHealth() {
  try {
    const r = await fetch('/api/health');
    if (r.ok) {
      const d = await r.json();
      // Backend returns nested health; treat 2xx as online
      setHealth(true, 'Backend online');
    } else {
      setHealth(false, 'Backend error ' + r.status);
    }
  } catch(e) {
    setHealth(false, 'Backend unreachable');
  }
}

// ── chat ─────────────────────────────────────────────────────────────
function appendMsg(role, html, sources, metrics) {
  const box = qs('#chat-messages');
  const empty = box.querySelector('.empty-state');
  if (empty) empty.remove();

  const wrap = document.createElement('div');
  wrap.className = 'msg ' + role;

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = html;

  if (sources && sources.length) {
    const sdiv = document.createElement('div');
    sdiv.className = 'sources';
    sdiv.innerHTML = '<strong style="font-size:.75rem;color:#606080">Sources</strong>';
    sources.forEach(s => {
      const item = document.createElement('div');
      item.className = 'source-item';
      const rawPath = s.sourcePath || s.source || '';
      const label = s.fileName || s.documentId || rawPath.split('/').pop() || rawPath;
      const rel = s.similarity != null ? Math.round(s.similarity * 100) + '%' : '';
      item.innerHTML = `<span title="${rawPath}">${label}</span><span class="source-relevance">${rel}</span>`;
      sdiv.appendChild(item);
    });
    bubble.appendChild(sdiv);
  }

  if (metrics && Object.keys(metrics).length) {
    const mdiv = document.createElement('div');
    mdiv.className = 'metrics';
    const fmt = (k, v) => {
      if (k === 'elapsedMs') return Math.round(v) + ' ms';
      if (k === 'tokensPerSecond') return (+v).toFixed(1) + ' t/s';
      return Math.round(v);
    };
    const labels = {elapsedMs:'Time', promptTokens:'Prompt', completionTokens:'Output', totalTokens:'Total', tokensPerSecond:'Speed'};
    Object.entries(metrics).forEach(([k,v]) => {
      if (v == null) return;
      const sp = document.createElement('span');
      sp.className = 'metric';
      sp.textContent = (labels[k] || k) + ': ' + fmt(k, v);
      mdiv.appendChild(sp);
    });
    bubble.appendChild(mdiv);
  }

  wrap.appendChild(bubble);
  box.appendChild(wrap);
  box.scrollTop = box.scrollHeight;
  return wrap;
}

function appendTyping() {
  const box = qs('#chat-messages');
  const wrap = document.createElement('div');
  wrap.className = 'msg assistant typing';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = '';
  wrap.appendChild(bubble);
  box.appendChild(wrap);
  box.scrollTop = box.scrollHeight;
  return wrap;
}

async function sendMessage() {
  const input = qs('#chat-input');
  const text = input.value.trim();
  if (!text) return;

  appendMsg('user', md(text));
  chatHistory.push({ role: 'user', content: text });
  input.value = '';
  input.style.height = 'auto';

  const btn = qs('#send-btn');
  btn.disabled = true;
  const typing = appendTyping();

  const lang = qs('#lang-select').value;
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, history: chatHistory.slice(0,-1), language: lang }),
    });
    typing.remove();
    if (!r.ok) {
      const err = await r.text();
      appendMsg('assistant', '<span style="color:#e94560">Error ' + r.status + ': ' + err + '</span>');
    } else {
      const d = await r.json();
      const answer = d.answer || d.message || JSON.stringify(d);
      appendMsg('assistant', md(answer), d.contextChunks, d.metrics);
      chatHistory.push({ role: 'assistant', content: answer });
    }
  } catch(e) {
    typing.remove();
    appendMsg('assistant', '<span style="color:#e94560">Network error: ' + e.message + '</span>');
  } finally {
    btn.disabled = false;
    input.focus();
  }
}

qs('#send-btn').addEventListener('click', sendMessage);
qs('#chat-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
// auto-resize textarea
qs('#chat-input').addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 180) + 'px';
});

// ── LLM Settings ─────────────────────────────────────────────────────
async function loadLlmSettings() {
  try {
    const r = await fetch('/api/chat/settings');
    if (!r.ok) throw new Error(r.status);
    chatSettings = await r.json();
    fillLlmForm(chatSettings);
  } catch(e) {
    toast('Failed to load LLM settings: ' + e.message, 'error');
  }
}

function fillLlmForm(s) {
  qs('#llm-base-url').value     = s.llmBaseUrl    || s.llm_base_url    || '';
  qs('#llm-model').value        = s.llmModel       || s.llm_model       || '';
  qs('#llm-api-key').value      = s.llmApiKey      || s.llm_api_key     || '';
  const temp = s.temperature ?? 0.3;
  qs('#llm-temperature').value  = temp;
  qs('#temp-val').textContent   = temp;
  qs('#llm-max-tokens').value   = s.maxTokens      || s.max_tokens      || 2048;
  qs('#llm-top-k').value        = s.topK           || s.top_k           || 5;
  qs('#llm-system-prompt').value= s.systemPrompt   || s.system_prompt   || '';
  qs('#llm-encryption-key').value = s.encryptionKey || s.encryption_key || '';
}

qs('#llm-temperature').addEventListener('input', function() {
  qs('#temp-val').textContent = (+this.value).toFixed(2);
});

qs('#llm-save-btn').addEventListener('click', async () => {
  const payload = {
    llmApiKey:    qs('#llm-api-key').value.trim(),
    llmBaseUrl:   qs('#llm-base-url').value.trim(),
    llmModel:     qs('#llm-model').value.trim(),
    temperature:  parseFloat(qs('#llm-temperature').value),
    maxTokens:    parseInt(qs('#llm-max-tokens').value, 10),
    topK:         parseInt(qs('#llm-top-k').value, 10),
    systemPrompt: qs('#llm-system-prompt').value,
    encryptionKey:qs('#llm-encryption-key').value,
  };
  try {
    const r = await fetch('/api/chat/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error(await r.text());
    chatSettings = await r.json();
    fillLlmForm(chatSettings);
    toast('LLM settings saved');
  } catch(e) {
    toast('Save failed: ' + e.message, 'error');
  }
});

qs('#llm-reload-btn').addEventListener('click', () => loadLlmSettings());

qs('#llm-fetch-models-btn').addEventListener('click', async () => {
  const listEl = qs('#model-list');
  listEl.innerHTML = '<span style="color:#606080;font-size:.8rem">Fetching…</span>';
  try {
    const r = await fetch('/api/llm/models');
    if (!r.ok) throw new Error(r.status + ' ' + await r.text());
    const d = await r.json();
    const models = d.models || d;
    listEl.innerHTML = '';
    (Array.isArray(models) ? models : []).forEach(m => {
      const name = typeof m === 'string' ? m : (m.name || m.id || JSON.stringify(m));
      const pill = document.createElement('span');
      pill.className = 'model-pill';
      pill.textContent = name;
      pill.title = 'Click to use this model';
      pill.addEventListener('click', () => { qs('#llm-model').value = name; });
      listEl.appendChild(pill);
    });
    if (!models.length) listEl.innerHTML = '<span style="color:#606080;font-size:.8rem">No models found</span>';
  } catch(e) {
    listEl.innerHTML = '<span style="color:#e94560;font-size:.8rem">Error: ' + e.message + '</span>';
  }
});

// ── DB Environments ───────────────────────────────────────────────────
async function loadDbSettings() {
  try {
    const r = await fetch('/api/settings');
    if (!r.ok) throw new Error(r.status);
    appSettings = await r.json();
    renderEnvList();
    updateActiveEnvBar();
  } catch(e) {
    toast('Failed to load DB settings: ' + e.message, 'error');
  }
}

function renderEnvList() {
  const container = qs('#env-list');
  container.innerHTML = '';
  if (!appSettings) return;

  const envs = appSettings.postgresEnvironments || appSettings.postgres_environments || [];
  const activeId = appSettings.activePostgresEnvironmentId || appSettings.active_postgres_environment_id;

  envs.forEach(e => {
    const row = document.createElement('div');
    row.className = 'env-row' + (e.id === activeId ? ' active' : '');
    row.innerHTML = `
      <span class="env-name">${e.name || e.id}</span>
      <span class="env-detail">${e.dbHost || e.db_host || ''}:${e.dbPort || e.db_port || 5432} / ${e.dbName || e.db_name || ''}</span>
      <div class="env-actions">
        ${e.id !== activeId ? `<button class="btn btn-sm btn-secondary set-active-btn" data-id="${e.id}">Set active</button>` : '<span style="color:#e94560;font-size:.78rem">active</span>'}
        <button class="btn btn-sm btn-secondary edit-env-btn" data-id="${e.id}">Edit</button>
      </div>`;
    container.appendChild(row);
  });

  container.querySelectorAll('.set-active-btn').forEach(btn => {
    btn.addEventListener('click', e => { e.stopPropagation(); setActiveEnv(btn.dataset.id); });
  });
  container.querySelectorAll('.edit-env-btn').forEach(btn => {
    btn.addEventListener('click', e => { e.stopPropagation(); openEnvEditor(btn.dataset.id); });
  });
}

function updateActiveEnvBar() {
  if (!appSettings) return;
  const envs = appSettings.postgresEnvironments || appSettings.postgres_environments || [];
  const activeId = appSettings.activePostgresEnvironmentId || appSettings.active_postgres_environment_id;
  const env = envs.find(e => e.id === activeId) || envs[0];
  if (env) {
    qs('#active-env-bar').textContent =
      'Active DB env: ' + (env.name || env.id) + ' — ' + (env.dbHost || env.db_host || 'localhost') +
      ':' + (env.dbPort || env.db_port || 5432) + ' / ' + (env.dbName || env.db_name || '');
  }
}

async function setActiveEnv(id) {
  if (!appSettings) return;
  const key = appSettings.postgresEnvironments ? 'activePostgresEnvironmentId' : 'active_postgres_environment_id';
  appSettings[key] = id;
  await saveAppSettings();
  renderEnvList();
  updateActiveEnvBar();
}

async function saveAppSettings() {
  try {
    const r = await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(appSettings),
    });
    if (!r.ok) throw new Error(await r.text());
    appSettings = await r.json();
    toast('DB settings saved');
  } catch(e) {
    toast('Save failed: ' + e.message, 'error');
  }
}

function openEnvEditor(id) {
  const envs = appSettings.postgresEnvironments || appSettings.postgres_environments || [];
  const env = id ? envs.find(e => e.id === id) : null;
  editingEnvId = id || null;

  qs('#env-editor-title').textContent = env ? 'Edit Environment' : 'New Environment';
  qs('#env-id').value               = env ? env.id : crypto.randomUUID().slice(0,12);
  qs('#env-name').value             = env ? (env.name || '') : '';
  qs('#env-backend').value          = env ? (env.vectorBackend || env.vector_backend || 'postgres') : 'postgres';
  qs('#env-host').value             = env ? (env.dbHost || env.db_host || 'localhost') : 'localhost';
  qs('#env-port').value             = env ? (env.dbPort || env.db_port || 5432) : 5432;
  qs('#env-db').value               = env ? (env.dbName || env.db_name || 'rag') : 'rag';
  qs('#env-user').value             = env ? (env.dbUser || env.db_user || 'postgres') : 'postgres';
  qs('#env-password').value         = env ? (env.dbPassword || env.db_password || '') : '';
  qs('#env-schema').value           = env ? (env.dbSchema || env.db_schema || 'public') : 'public';
  qs('#env-table').value            = env ? (env.dbTableName || env.db_table_name || 'rag_documents') : 'rag_documents';

  qs('#env-delete-btn').style.display = env ? '' : 'none';
  qs('#env-editor').style.display = 'block';
  qs('#env-editor').scrollIntoView({ behavior: 'smooth' });
}

qs('#env-add-btn').addEventListener('click', () => openEnvEditor(null));
qs('#env-cancel-btn').addEventListener('click', () => { qs('#env-editor').style.display = 'none'; });

qs('#env-save-btn').addEventListener('click', async () => {
  if (!appSettings) return;
  const envObj = {
    id:            qs('#env-id').value,
    name:          qs('#env-name').value.trim() || qs('#env-id').value,
    vectorBackend: qs('#env-backend').value,
    dbHost:        qs('#env-host').value.trim(),
    dbPort:        parseInt(qs('#env-port').value, 10),
    dbName:        qs('#env-db').value.trim(),
    dbUser:        qs('#env-user').value.trim(),
    dbPassword:    qs('#env-password').value,
    dbSchema:      qs('#env-schema').value.trim(),
    dbTableName:   qs('#env-table').value.trim(),
    sqliteFilePath: '',
    qdrantLocalPath: '',
  };

  const key = appSettings.postgresEnvironments ? 'postgresEnvironments' : 'postgres_environments';
  let envs = [...(appSettings[key] || [])];
  const idx = envs.findIndex(e => e.id === editingEnvId);
  if (idx >= 0) {
    envs[idx] = envObj;
  } else {
    envs.push(envObj);
  }
  appSettings[key] = envs;
  await saveAppSettings();
  renderEnvList();
  updateActiveEnvBar();
  qs('#env-editor').style.display = 'none';
});

qs('#env-delete-btn').addEventListener('click', async () => {
  if (!editingEnvId || !appSettings) return;
  const key = appSettings.postgresEnvironments ? 'postgresEnvironments' : 'postgres_environments';
  const envs = (appSettings[key] || []).filter(e => e.id !== editingEnvId);
  if (!envs.length) { toast('Cannot delete the last environment', 'error'); return; }
  appSettings[key] = envs;
  // If deleted the active env, switch to first
  const activeKey = appSettings.activePostgresEnvironmentId !== undefined
    ? 'activePostgresEnvironmentId' : 'active_postgres_environment_id';
  if (appSettings[activeKey] === editingEnvId) appSettings[activeKey] = envs[0].id;
  await saveAppSettings();
  renderEnvList();
  updateActiveEnvBar();
  qs('#env-editor').style.display = 'none';
});

// ── init ─────────────────────────────────────────────────────────────
(async () => {
  await checkHealth();
  setInterval(checkHealth, 30000);
  // Pre-load settings so active env bar is populated
  try {
    const r = await fetch('/api/settings');
    if (r.ok) {
      appSettings = await r.json();
      updateActiveEnvBar();
    }
  } catch(_) {}
})();
