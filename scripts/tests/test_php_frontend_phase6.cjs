// Function-level fixtures with a minimal DOM stub; not browser acceptance.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const nodes = new Map();
const storage = new Map();
const node = () => ({ value: 'en', innerHTML: '', textContent: '',
  classList: { add() {}, remove() {} }, addEventListener() {} });
const context = vm.createContext({
  window: { location: { protocol: 'http:' } },
  document: { getElementById(id) { if (!nodes.has(id)) nodes.set(id, node()); return nodes.get(id); } },
  localStorage: { getItem(key) { return storage.get(key) || null; },
    setItem(key, value) { storage.set(key, value); }, removeItem(key) { storage.delete(key); } },
  setInterval() {}, TextEncoder,
  fetch: async () => ({ ok: true, status: 200, text: async () => JSON.stringify({
    pythonWorker: {status:'ok'}, vectorDatabase: {status:'ok'}, claimVerifier:{status:'ok'} }) }),
});
vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../../chatBotPHP/app.js'), 'utf8'), context);
const run = code => vm.runInContext(code, context);
assert.equal(run('PROXY_MODE'), true);
run(`chatHistory = [{role:'user',content:'What is NOTCAM?'},
  {role:'assistant',content:'NOTCAM is infrared.'}];`);
let payload = JSON.parse(run('JSON.stringify(buildChatPayload("Can it observe at 500nm?"))'));
assert.equal(payload.history[0].content, 'What is NOTCAM?');
assert.equal(payload.history[1].role, 'assistant');
run(`chatHistory = Array.from({length:40}, (_,i) => ({
  role:i%2 ? 'assistant':'user', content:'é'.repeat(3000)+i }));`);
assert.ok(run('buildChatPayload("What is FIES?").history.length <= MAX_HISTORY_MESSAGES'));
assert.ok(run('encodedSize(buildChatPayload("What is FIES?")) <= MAX_PROXY_BODY_BYTES'));
assert.equal(run('buildChatPayload("What is FIES?").history[0].role'), 'user');
assert.ok(run('boundedHistory(chatHistory).reduce((n,m)=>n+m.content.length,0) <= MAX_HISTORY_CHARS'));
storage.set('not_qa_console_history_v1', 'malformed');
assert.equal(run('loadHistory().length'), 0);
run('onClear()');
assert.equal(run('chatHistory.length'), 0);
assert.equal(storage.has('not_qa_console_history_v1'), false);
assert.equal(nodes.get('chatThread').innerHTML, '');
assert.equal(run('escapeHtml("<script>&")'), '&lt;script&gt;&amp;');
console.log('PHP frontend function fixtures passed: proxy, history bounds/context/clear, malformed storage, escaping. Not a browser test.');
