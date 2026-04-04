// OmniRAG — OpenCode Home Template
// Sidebar rail + panel + peek + drawer + transitions

const API = '';
let activePipeline = null;
let lastPeekPipeline = null;
let hoverPipeline = null;
let peekTimeout = null;
let currentPage = 'home';
let pipelines = [];
let healthData = null;

// ─── Colors for pipeline avatars ───
const COLORS = ['#6b1f4a','#1a5f4a','#3b2f80','#7c4a1e','#1a4a6b','#6b1a2f','#2f6b1a','#4a1a6b'];
const colorFor = (name) => COLORS[Math.abs([...name].reduce((h,c) => ((h << 5) - h + c.charCodeAt(0)) | 0, 0)) % COLORS.length];
const initialFor = (name) => name.charAt(0).toUpperCase();

// ─── Health ───
async function checkHealth() {
  try {
    healthData = await fetch(`${API}/health`).then(r => r.json());
    document.getElementById('status-dot').className = 'status-dot online';
    document.getElementById('status-text').textContent = `v${healthData.version} — Healthy`;
    // Rail bottom status
    const railDot = document.getElementById('rail-status-dot');
    const railVer = document.getElementById('rail-version');
    if (railDot) railDot.className = 'status-dot online';
    if (railVer) railVer.textContent = `v${healthData.version}\nHealthy`;
  } catch {
    document.getElementById('status-dot').className = 'status-dot offline';
    document.getElementById('status-text').textContent = 'Offline';
    const railDot = document.getElementById('rail-status-dot');
    const railVer = document.getElementById('rail-version');
    if (railDot) railDot.className = 'status-dot offline';
    if (railVer) railVer.textContent = 'Offline';
  }
}

// ─── Pipelines ───
async function loadPipelines() {
  try { pipelines = await fetch(`${API}/pipelines/`).then(r => r.json()); } catch { pipelines = []; }
  renderRail();
  renderDrawerRail();
  if (currentPage === 'home') renderHome();
  if (activePipeline) renderPipelinePanel(activePipeline);
}

// ─── Rail ───
function renderRail() {
  const el = document.getElementById('rail-items');
  el.innerHTML = pipelines.map(p => `
    <div class="pipeline-avatar ${activePipeline === p.name ? 'active' : ''}"
         style="background:${colorFor(p.name)}"
         data-name="${p.name}"
         onclick="selectPipeline('${p.name}')"
         onmouseenter="peekIn('${p.name}')"
         onmouseleave="peekOut()"
         title="${p.name}">
      ${initialFor(p.name)}
    </div>
  `).join('');
}

function renderDrawerRail() {
  const el = document.getElementById('drawer-rail');
  el.innerHTML = pipelines.map(p => `
    <div class="pipeline-avatar ${activePipeline === p.name ? 'active' : ''}"
         style="background:${colorFor(p.name)}; width:36px; height:36px; border-radius:8px; font-size:12px;"
         onclick="selectPipeline('${p.name}'); closeDrawer();">
      ${initialFor(p.name)}
    </div>
  `).join('') + `
    <div style="flex:1"></div>
    <div class="rail-icon" style="width:28px;height:28px;" onclick="navigate('settings'); closeDrawer();">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
    </div>
  `;
}

// ─── Pipeline Panel (sidebar + drawer + peek) ───
function renderPipelinePanel(name) {
  const p = pipelines.find(x => x.name === name);
  if (!p) return '';
  const html = `
    <div style="padding:14px 16px 8px;">
      <div style="font-size:14px;font-weight:500;color:var(--text)">${p.name}</div>
      <div style="font-size:11px;color:var(--text-dim);font-family:var(--mono)">${p.strategy} · ${p.stage_count} stages · v${p.version}</div>
    </div>
    <div style="padding:8px 8px 12px;">
      <button class="invoke-btn" onclick="showInvoke('${p.name}')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        Invoke pipeline
      </button>
      <button class="invoke-btn" onclick="viewPlan('${p.name}')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        View execution plan
      </button>
    </div>
    <div style="padding:0 12px 4px; font-size:11px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.04em;">Description</div>
    <div style="padding:0 12px 12px; font-size:13px; color:var(--text-dim); line-height:1.5;">${p.description || 'No description'}</div>
  `;
  // Desktop panel
  document.getElementById('panel-header').innerHTML = '';
  document.getElementById('panel-content').innerHTML = html;
  // Drawer panel
  document.getElementById('drawer-panel').innerHTML = html;
  return html;
}

// ─── Peek System (hover-peek, 180ms in / 120ms out) ───
function peekIn(name) {
  disarmPeek();
  hoverPipeline = name;
  lastPeekPipeline = name;
  const peek = document.getElementById('peek-panel');
  const inner = document.getElementById('peek-inner');
  const p = pipelines.find(x => x.name === name);
  if (!p || activePipeline === name) { peek.classList.remove('visible'); return; }
  inner.innerHTML = renderPipelinePanel(name) || '';
  // Re-render panel content for peek specifically
  inner.innerHTML = `
    <div style="padding:14px 16px 8px;">
      <div style="font-size:14px;font-weight:500;color:var(--text)">${p.name}</div>
      <div style="font-size:11px;color:var(--text-dim);font-family:var(--mono)">${p.strategy} · ${p.stage_count} stages</div>
    </div>
    <div style="padding:8px 8px 12px;">
      <button class="invoke-btn" onclick="selectPipeline('${p.name}'); peekClose();">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        Open pipeline
      </button>
    </div>
    <div style="padding:0 12px; font-size:13px; color:var(--text-dim); line-height:1.5;">${p.description || 'No description'}</div>
  `;
  peek.classList.add('visible');
}

function peekOut() {
  armPeek();
}

function peekClose() {
  hoverPipeline = null;
  document.getElementById('peek-panel').classList.remove('visible');
}

function armPeek() {
  disarmPeek();
  peekTimeout = setTimeout(() => {
    hoverPipeline = null;
    document.getElementById('peek-panel').classList.remove('visible');
    peekTimeout = null;
  }, 300);
}

function disarmPeek() {
  if (peekTimeout) { clearTimeout(peekTimeout); peekTimeout = null; }
}

// Peek panel hover keeps it open
document.addEventListener('DOMContentLoaded', () => {
  const peek = document.getElementById('peek-panel');
  if (peek) {
    peek.addEventListener('mouseenter', disarmPeek);
    peek.addEventListener('mouseleave', armPeek);
  }
});

// ─── Select Pipeline ───
function selectPipeline(name) {
  activePipeline = name;
  currentPage = 'pipeline';
  peekClose();
  renderRail();
  renderDrawerRail();
  renderPipelinePanel(name);
  renderPipelineMain(name);
}

function renderPipelineMain(name) {
  const p = pipelines.find(x => x.name === name);
  if (!p) return;
  const body = document.getElementById('main-body');
  body.innerHTML = `
    <div style="max-width:700px;">
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:20px;">
        <div>
          <h2 style="font-size:18px; font-weight:600; color:var(--text); margin-bottom:2px;">${p.name}</h2>
          <div style="font-size:12px; color:var(--text-dim); font-family:var(--mono);">${p.strategy} strategy · ${p.stage_count} stages · version ${p.version}</div>
        </div>
        <button class="btn btn-primary" onclick="showInvoke('${p.name}')">Invoke</button>
      </div>
      <div class="card">
        <div class="card-title">Description</div>
        <div class="card-body"><p style="color:var(--text-dim)">${p.description || 'No description provided.'}</p></div>
      </div>
      <div class="card">
        <div class="card-title">Quick Actions</div>
        <div class="card-body" style="display:flex; gap:8px; flex-wrap:wrap;">
          <button class="btn" onclick="showInvoke('${p.name}')">Invoke (Sync)</button>
          <button class="btn" onclick="viewPlan('${p.name}')">Execution Plan</button>
          <a href="/docs" target="_blank" class="btn">API Docs</a>
        </div>
      </div>
    </div>
    <div id="pipeline-result"></div>
  `;
}

// ─── Navigation ───
function navigate(page) {
  currentPage = page;
  activePipeline = null;
  renderRail();
  const body = document.getElementById('main-body');
  if (page === 'home') return renderHome();
  if (page === 'metrics') return renderMetrics(body);
  if (page === 'settings') return renderSettings(body);
  if (page === 'api-docs') return renderEmbedded(body, '/docs', 'API Docs (Swagger)');
  if (page === 'redoc') return renderEmbedded(body, '/redoc', 'ReDoc');
}

function renderEmbedded(body, src, title) {
  body.innerHTML = `
    <div style="display:flex; flex-direction:column; height:100%; margin:-24px -20px; overflow:hidden;">
      <div style="display:flex; align-items:center; justify-content:space-between; padding:10px 16px; border-bottom:1px solid var(--border); flex-shrink:0;">
        <span style="font-size:14px; font-weight:500; color:var(--text);">${title}</span>
        <div style="display:flex; gap:8px;">
          <button class="btn" onclick="window.open('${src}','_blank')" style="font-size:11px; padding:3px 10px;">Open in new tab</button>
          <button class="btn" onclick="navigate('home')" style="font-size:11px; padding:3px 10px;">Close</button>
        </div>
      </div>
      <iframe src="${src}" style="flex:1; border:none; width:100%; min-height:0; background:#fff;"></iframe>
    </div>
  `;
}

// ─── Drawer ───
function toggleDrawer() {
  document.getElementById('drawer-overlay').classList.toggle('open');
  document.getElementById('drawer-nav').classList.toggle('open');
}
function closeDrawer() {
  document.getElementById('drawer-overlay').classList.remove('open');
  document.getElementById('drawer-nav').classList.remove('open');
}
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawer(); });

// ─── Toast ───
function showToast(msg, type = 'success') {
  let region = document.querySelector('.toast-region');
  if (!region) { region = document.createElement('div'); region.className = 'toast-region'; document.body.appendChild(region); }
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  region.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// ─── Pages ───
function renderHome() {
  const body = document.getElementById('main-body');
  const rows = pipelines.map(p => `
    <div class="home-pipeline-row" onclick="selectPipeline('${p.name}')">
      <div>
        <div class="home-pipeline-name">${p.name}</div>
        <div class="home-pipeline-meta">${p.strategy} · ${p.stage_count} stages</div>
      </div>
      <span class="badge badge-info">${p.strategy}</span>
    </div>
  `).join('');

  body.innerHTML = `
    <div class="home-landing">
      <div class="home-logo"><span>Omni</span>RAG</div>
      <button class="home-status-btn" onclick="checkHealth()">
        <div class="status-dot ${healthData ? 'online' : ''}" style="width:8px;height:8px;"></div>
        ${healthData ? `v${healthData.version}` : 'Check status'}
      </button>

      ${pipelines.length > 0 ? `
        <div class="home-section">
          <div class="home-section-header">
            <div class="home-section-title">Pipelines</div>
            <button class="btn" onclick="showUpload()">Upload Pipeline</button>
          </div>
          ${rows}
        </div>
      ` : `
        <div class="empty-state" style="margin-top:40px;">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity:0.3;color:var(--text-dim)"><path d="M4 4h6v6H4zM14 4h6v6h-6zM9 10l5 4M4 14h6v6H4z"/></svg>
          <p>No pipelines uploaded yet.</p>
          <button class="btn btn-primary" onclick="showUpload()">Upload Pipeline</button>
        </div>
      `}

      <div class="home-section">
        <div class="home-section-header">
          <div class="home-section-title">Adapters</div>
        </div>
        <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(140px,1fr)); gap:8px;">
          ${['file_loader','recursive_splitter','memory','huggingface','qdrant','cross_encoder','openai_gen','ollama_gen'].map(a => `
            <div class="card" style="padding:10px; margin:0;">
              <code style="font-size:11px;">${a}</code>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;

  // Clear desktop panel when on home
  document.getElementById('panel-header').innerHTML = '';
  document.getElementById('panel-content').innerHTML = `
    <div style="padding:16px 8px; text-align:center; color:var(--text-muted); font-size:13px;">
      Select a pipeline from the rail
    </div>
  `;
}

function showUpload() {
  const body = document.getElementById('main-body');
  body.innerHTML = `
    <div style="max-width:700px;">
      <h2 style="font-size:18px; font-weight:600; color:var(--text); margin-bottom:16px;">Upload Pipeline YAML</h2>
      <textarea id="yaml-input" placeholder='version: "4.0"
name: my_pipeline
execution:
  strategy: single
stages:
  - id: retrieve
    adapter: memory
    params: { top_k: 3 }
    input: query
  - id: generate
    adapter: ollama_gen
    params: { model: tinyllama }
    input: retrieve'></textarea>
      <div style="margin-top:12px; display:flex; gap:8px;">
        <button class="btn btn-primary" onclick="uploadPipeline()">Upload</button>
        <button class="btn" onclick="navigate('home')">Cancel</button>
      </div>
    </div>
  `;
}

async function uploadPipeline() {
  const yaml = document.getElementById('yaml-input').value;
  if (!yaml.trim()) { showToast('YAML required', 'error'); return; }
  try {
    const r = await fetch(`${API}/pipelines/`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({yaml_content:yaml}) });
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    showToast(`Pipeline "${data.name}" uploaded (${data.stage_count} stages)`);
    await loadPipelines();
    selectPipeline(data.name);
  } catch(e) { showToast(e.message, 'error'); }
}

function showInvoke(name) {
  const body = document.getElementById('main-body');
  body.innerHTML = `
    <div style="max-width:700px;">
      <h2 style="font-size:18px; font-weight:600; color:var(--text); margin-bottom:16px;">Invoke: ${name}</h2>
      <div style="margin-bottom:12px;">
        <label style="font-size:12px; color:var(--text-dim); display:block; margin-bottom:4px;">Query</label>
        <input class="input" id="invoke-query" placeholder="What is Retrieval-Augmented Generation?" />
      </div>
      <div style="display:flex; gap:8px;">
        <button class="btn btn-primary" onclick="doInvoke('${name}')">Execute</button>
        <button class="btn" onclick="selectPipeline('${name}')">Cancel</button>
      </div>
      <div id="invoke-result"></div>
    </div>
  `;
}

async function doInvoke(name) {
  const query = document.getElementById('invoke-query').value;
  if (!query) { showToast('Query required', 'error'); return; }
  const result = document.getElementById('invoke-result');
  result.innerHTML = '<div style="display:flex;align-items:center;gap:8px;margin-top:16px;"><div class="spinner"></div> Executing...</div>';
  try {
    const r = await fetch(`${API}/pipelines/${name}/invoke`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({query, params:{}}) });
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    result.innerHTML = `
      <div class="card" style="margin-top:16px;">
        <div class="card-title">Result</div>
        <div class="card-body">
          <p style="margin-bottom:8px;"><strong style="color:var(--text)">Answer:</strong> ${data.answer}</p>
          <p><strong style="color:var(--text)">Confidence:</strong> <span class="badge badge-info">${(data.confidence*100).toFixed(1)}%</span></p>
        </div>
      </div>
    `;
    showToast('Pipeline executed');
  } catch(e) { result.innerHTML = `<div class="card" style="margin-top:16px;"><div class="card-title" style="color:var(--error)">Error</div><div class="card-body"><code>${e.message}</code></div></div>`; }
}

async function viewPlan(name) {
  const body = document.getElementById('main-body');
  body.innerHTML = '<div style="display:flex;align-items:center;gap:8px;"><div class="spinner"></div> Loading plan...</div>';
  try {
    const data = await fetch(`${API}/pipelines/${name}/plan`).then(r => r.json());
    body.innerHTML = `
      <div style="max-width:700px;">
        <h2 style="font-size:18px; font-weight:600; color:var(--text); margin-bottom:16px;">Execution Plan: ${name}</h2>
        <pre>${JSON.stringify(data, null, 2)}</pre>
        <button class="btn" style="margin-top:12px;" onclick="selectPipeline('${name}')">Back</button>
      </div>
    `;
  } catch(e) { body.innerHTML = `<div class="card"><div class="card-title" style="color:var(--error)">Error</div><div class="card-body"><code>${e.message}</code></div></div>`; }
}

function renderMetrics(body) {
  body.innerHTML = `
    <div style="max-width:700px;">
      <h2 style="font-size:18px; font-weight:600; color:var(--text); margin-bottom:16px;">Metrics</h2>
      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px,1fr)); gap:12px;">
        <div class="card"><div class="card-title">Status</div><div class="card-body"><span class="badge badge-success">Healthy</span></div></div>
        <div class="card"><div class="card-title">Version</div><div class="card-body"><code>${healthData?.version || '—'}</code></div></div>
        <div class="card"><div class="card-title">Pipelines</div><div class="card-body" style="font-size:24px;font-weight:700;color:var(--text)">${pipelines.length}</div></div>
        <div class="card"><div class="card-title">Strategies</div><div class="card-body">
          <span class="badge badge-info">single</span> <span class="badge badge-info">fallback</span> <span class="badge badge-info">ensemble</span> <span class="badge badge-info">vote</span>
        </div></div>
      </div>
    </div>
  `;
}

function renderSettings(body) {
  body.innerHTML = `
    <div style="max-width:700px;">
      <h2 style="font-size:18px; font-weight:600; color:var(--text); margin-bottom:16px;">Configuration</h2>
      <div class="card">
        <table>
          <thead><tr><th>Variable</th><th>Default</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>OMNIRAG_HOST</code></td><td>127.0.0.1</td><td>Bind host</td></tr>
            <tr><td><code>OMNIRAG_PORT</code></td><td>8100</td><td>Bind port</td></tr>
            <tr><td><code>OMNIRAG_WORKERS</code></td><td>1</td><td>Workers</td></tr>
            <tr><td><code>OMNIRAG_API_KEYS</code></td><td><em>empty</em></td><td>API keys</td></tr>
            <tr><td><code>OMNIRAG_RATE_LIMIT</code></td><td>100</td><td>Req/min</td></tr>
            <tr><td><code>OMNIRAG_COMPILER</code></td><td>true</td><td>Compiler</td></tr>
            <tr><td><code>OMNIRAG_LOG_LEVEL</code></td><td>INFO</td><td>Log level</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// ─── Init ──���
checkHealth();
setInterval(checkHealth, 15000);
loadPipelines();
