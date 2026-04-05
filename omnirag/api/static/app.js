// OmniRAG — OpenCode Home Template
// Sidebar rail + panel + peek + drawer + transitions

const API = '';
let activePipeline = null;
let lastPeekPipeline = null;
let hoverPipeline = null;
let peekTimeout = null;
let currentPage = 'home';
let pipelines = [];
let activeMainTab = 'rag';
let chatMessages = [];
let healthData = null;

// ─── Colors for pipeline avatars ───
const COLORS = ['#6b1f4a','#1a5f4a','#3b2f80','#7c4a1e','#1a4a6b','#6b1a2f','#2f6b1a','#4a1a6b'];
const colorFor = (name) => COLORS[Math.abs([...name].reduce((h,c) => ((h << 5) - h + c.charCodeAt(0)) | 0, 0)) % COLORS.length];
const initialFor = (name) => name.charAt(0).toUpperCase();

// ─── Health ───
async function checkHealth() {
  try {
    healthData = await fetch(`${API}/health`).then(r => r.json());
    // Footer status
    const fDot = document.getElementById('footer-status-dot');
    const fText = document.getElementById('footer-status-text');
    if (fDot) fDot.className = 'status-dot online';
    if (fText) fText.textContent = `v${healthData.version} · Healthy`;
  } catch {
    const fDot = document.getElementById('footer-status-dot');
    const fText = document.getElementById('footer-status-text');
    if (fDot) fDot.className = 'status-dot offline';
    if (fText) fText.textContent = 'Offline';
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
    <div class="rail-icon" style="width:28px;height:28px;" onclick="navigate('metrics'); closeDrawer();" title="Metrics">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>
    </div>
    <div class="rail-icon" style="width:28px;height:28px;" onclick="navigate('howto'); closeDrawer();" title="How To">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z"/><path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z"/></svg>
    </div>
    <div class="rail-icon" style="width:28px;height:28px;" onclick="navigate('settings'); closeDrawer();" title="Settings">
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
  if (page === 'howto') return renderHowTo(body);
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

      <div class="home-section">
        <div class="card" style="margin:0 0 8px;">
          <div style="display:flex; gap:8px; align-items:flex-end;">
            <div style="flex:1;">
              <label style="font-size:11px; color:var(--text-dim); display:block; margin-bottom:4px;">Source URI</label>
              <input class="input" id="intake-source" placeholder="/path/to/docs/*.pdf  or  https://...  or  s3://...  or  github://..." />
            </div>
            <button class="btn btn-primary" onclick="runIntake()" style="white-space:nowrap;">Ingest</button>
          </div>
          <div id="intake-result" style="margin-top:8px;"></div>
        </div>
        <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:4px;">
          <input type="file" id="intake-file-picker" multiple style="display:none" onchange="handleFilePick(this)" accept="application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/html,text/csv,text/markdown,application/json,application/xml,application/octet-stream" />
          <button class="btn" onclick="document.getElementById('intake-file-picker').click()" style="font-size:11px; padding:3px 8px;">Browse files</button>
          <button class="btn" onclick="fetchUrlViaBrowser()" style="font-size:11px; padding:3px 8px;">Fetch URL</button>
          <button class="btn" onclick="document.getElementById('intake-source').value='s3://bucket/prefix/'" style="font-size:11px; padding:3px 8px;">S3</button>
          <button class="btn" onclick="document.getElementById('intake-source').value='github://owner/repo/docs'" style="font-size:11px; padding:3px 8px;">GitHub</button>
          <button class="btn" onclick="showIntakeJobs()" style="font-size:11px; padding:3px 8px;">View Jobs</button>
        </div>
      </div>

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
        <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(160px,1fr)); gap:8px;">
          ${getAdapterCards()}
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

function renderHowTo(body) {
  body.innerHTML = `
    <div style="max-width:740px; margin:0 auto;">
      <div style="margin-bottom:32px;">
        <h1 style="font-size:22px; font-weight:700; color:var(--text); margin-bottom:4px;">How To Use OmniRAG</h1>
        <p style="font-size:14px; color:var(--text-dim);">Step-by-step guide to the control plane for RAG systems.</p>
      </div>

      <!-- Step 1 -->
      <div class="card" style="margin-bottom:16px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
          <div style="width:28px; height:28px; border-radius:50%; background:var(--accent); color:#fff; display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:700; flex-shrink:0;">1</div>
          <div class="card-title" style="margin:0;">Define a Pipeline in YAML</div>
        </div>
        <p style="color:var(--text-dim); margin-bottom:12px;">A pipeline is a directed graph of stages — ingestion, chunking, embedding, retrieval, reranking, and generation. Each stage maps to an adapter.</p>
        <pre>version: "4.0"
name: local_ollama_rag
description: "Local RAG — Ollama + in-memory store"

execution:
  strategy: single

stages:
  - id: load
    adapter: file_loader
    params:
      path: ./data
      glob: "*.txt"

  - id: chunk
    adapter: recursive_splitter
    params:
      chunk_size: 256
      overlap: 30
    input: load

  - id: store
    adapter: memory
    params:
      mode: upsert
    input: chunk

  - id: retrieve
    adapter: memory
    params:
      top_k: 3
    input: query

  - id: generate
    adapter: ollama_gen
    params:
      model: tinyllama
      base_url: http://localhost:11434
      temperature: 0.5
    input: retrieve

output: GenerationResult</pre>
      </div>

      <!-- Step 2 -->
      <div class="card" style="margin-bottom:16px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
          <div style="width:28px; height:28px; border-radius:50%; background:var(--accent); color:#fff; display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:700; flex-shrink:0;">2</div>
          <div class="card-title" style="margin:0;">Upload the Pipeline</div>
        </div>
        <p style="color:var(--text-dim); margin-bottom:12px;">Click the <strong style="color:var(--text)">+</strong> button in the sidebar or use the API:</p>
        <div style="display:flex; gap:8px; margin-bottom:12px;">
          <button class="btn btn-primary" onclick="showUpload()">Upload Pipeline</button>
        </div>
        <p style="color:var(--text-muted); font-size:12px; margin-bottom:8px;">Or via cURL:</p>
        <pre>curl -X POST http://localhost:8100/pipelines/ \\
  -H "Content-Type: application/json" \\
  -d '{"yaml_content": "&lt;your YAML here&gt;"}'</pre>
        <p style="color:var(--text-dim); margin-top:10px;">Response:</p>
        <pre>{
  "name": "local_ollama_rag",
  "description": "Local RAG — Ollama + in-memory store",
  "version": "4.0",
  "stage_count": 5,
  "strategy": "single"
}</pre>
      </div>

      <!-- Step 3 -->
      <div class="card" style="margin-bottom:16px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
          <div style="width:28px; height:28px; border-radius:50%; background:var(--accent); color:#fff; display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:700; flex-shrink:0;">3</div>
          <div class="card-title" style="margin:0;">Invoke the Pipeline</div>
        </div>
        <p style="color:var(--text-dim); margin-bottom:12px;">Click a pipeline in the sidebar, then press <strong style="color:var(--text)">Invoke</strong>. Or use the API:</p>
        <pre>curl -X POST http://localhost:8100/pipelines/local_ollama_rag/invoke \\
  -H "Content-Type: application/json" \\
  -d '{"query": "What is RAG?", "params": {}}'</pre>
        <p style="color:var(--text-dim); margin-top:10px;">Response:</p>
        <pre>{
  "answer": "RAG (Retrieval-Augmented Generation) combines ...",
  "citations": ["data/rag-overview.txt"],
  "confidence": 0.87,
  "metadata": {}
}</pre>
      </div>

      <!-- Step 4 -->
      <div class="card" style="margin-bottom:16px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
          <div style="width:28px; height:28px; border-radius:50%; background:var(--accent); color:#fff; display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:700; flex-shrink:0;">4</div>
          <div class="card-title" style="margin:0;">View the Execution Plan</div>
        </div>
        <p style="color:var(--text-dim); margin-bottom:12px;">The compiler analyzes your pipeline DAG, detects deterministic sub-graphs, and fuses them for faster execution.</p>
        <pre>GET /pipelines/local_ollama_rag/plan

{
  "pipeline": "local_ollama_rag",
  "analysis": {
    "total_stages": 5,
    "deterministic": ["load", "chunk", "store"],
    "interpreted": ["retrieve", "generate"],
    "fused_subgraphs": 1
  },
  "execution_plan": [
    { "type": "compiled", "stages": ["load","chunk","store"] },
    { "type": "interpreted", "stages": ["retrieve","generate"] }
  ]
}</pre>
      </div>

      <!-- Step 5 -->
      <div class="card" style="margin-bottom:16px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
          <div style="width:28px; height:28px; border-radius:50%; background:var(--accent); color:#fff; display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:700; flex-shrink:0;">5</div>
          <div class="card-title" style="margin:0;">Use Execution Strategies</div>
        </div>
        <p style="color:var(--text-dim); margin-bottom:12px;">Choose how pipelines run by setting <code>execution.strategy</code> in your YAML:</p>
        <table style="margin-bottom:12px;">
          <thead><tr><th>Strategy</th><th>Behavior</th><th>Use Case</th></tr></thead>
          <tbody>
            <tr><td><code>single</code></td><td>Run one pipeline</td><td>Default, lowest latency</td></tr>
            <tr><td><code>fallback</code></td><td>Try A → if low confidence → try B, C...</td><td>High availability</td></tr>
            <tr><td><code>ensemble</code></td><td>Run all in parallel, merge results</td><td>Maximum quality</td></tr>
            <tr><td><code>vote</code></td><td>Majority vote weighted by confidence</td><td>Disagreement resolution</td></tr>
          </tbody>
        </table>
        <p style="color:var(--text-muted); font-size:12px;">Example — fallback strategy:</p>
        <pre>execution:
  strategy: fallback
  fallback_threshold: 0.6</pre>
      </div>

      <!-- Step 6 -->
      <div class="card" style="margin-bottom:16px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
          <div style="width:28px; height:28px; border-radius:50%; background:var(--accent); color:#fff; display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:700; flex-shrink:0;">6</div>
          <div class="card-title" style="margin:0;">Built-in Adapters</div>
        </div>
        <p style="color:var(--text-dim); margin-bottom:12px;">8 adapters ship out of the box. Use them as <code>adapter:</code> values in your pipeline stages.</p>
        <table>
          <thead><tr><th>Adapter</th><th>Category</th><th>Dependencies</th></tr></thead>
          <tbody>
            <tr><td><code>file_loader</code></td><td>Ingestion</td><td>None</td></tr>
            <tr><td><code>recursive_splitter</code></td><td>Chunking</td><td>None</td></tr>
            <tr><td><code>memory</code></td><td>Retrieval</td><td>None</td></tr>
            <tr><td><code>huggingface</code></td><td>Embedding</td><td><code>pip install omnirag[huggingface]</code></td></tr>
            <tr><td><code>qdrant</code></td><td>Vector DB</td><td><code>pip install omnirag[qdrant]</code></td></tr>
            <tr><td><code>cross_encoder</code></td><td>Reranking</td><td><code>pip install omnirag[huggingface]</code></td></tr>
            <tr><td><code>openai_gen</code></td><td>Generation</td><td><code>openai</code></td></tr>
            <tr><td><code>ollama_gen</code></td><td>Generation</td><td>None (REST API)</td></tr>
          </tbody>
        </table>
      </div>

      <!-- Step 7 -->
      <div class="card" style="margin-bottom:16px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
          <div style="width:28px; height:28px; border-radius:50%; background:var(--accent); color:#fff; display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:700; flex-shrink:0;">7</div>
          <div class="card-title" style="margin:0;">Async Invocation & WebSocket Streaming</div>
        </div>
        <p style="color:var(--text-dim); margin-bottom:12px;">For long-running pipelines, use async invoke and poll for results:</p>
        <pre># Submit async
curl -X POST http://localhost:8100/pipelines/my_pipeline/invoke_async \\
  -H "Content-Type: application/json" \\
  -d '{"query": "Summarize all documents", "params": {}}'

# Response: {"task_id": "abc123"}

# Poll
curl http://localhost:8100/tasks/abc123</pre>
        <p style="color:var(--text-dim); margin-top:12px;">For real-time streaming, connect via WebSocket:</p>
        <pre>ws://localhost:8100/ws/chat

# Send: {"pipeline": "my_pipeline", "query": "..."}
# Receive: streaming chunks as they generate</pre>
      </div>

      <!-- Step 8 -->
      <div class="card" style="margin-bottom:16px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
          <div style="width:28px; height:28px; border-radius:50%; background:var(--accent); color:#fff; display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:700; flex-shrink:0;">8</div>
          <div class="card-title" style="margin:0;">CLI Commands</div>
        </div>
        <p style="color:var(--text-dim); margin-bottom:12px;">OmniRAG also works from the command line:</p>
        <pre># Validate a pipeline YAML
omnirag validate examples/simple_rag.yaml

# Run a pipeline directly
omnirag run examples/local_ollama_pipeline.yaml \\
  --query "What is RAG?"

# Start the API server
omnirag serve --host 0.0.0.0 --port 8100</pre>
      </div>

      <!-- Quick Reference -->
      <div class="card" style="margin-bottom:16px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2"><path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
          <div class="card-title" style="margin:0;">API Quick Reference</div>
        </div>
        <table>
          <thead><tr><th>Method</th><th>Endpoint</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><span class="badge badge-success">GET</span></td><td><code>/health</code></td><td>Health check</td></tr>
            <tr><td><span class="badge badge-info">GET</span></td><td><code>/metrics</code></td><td>Prometheus metrics</td></tr>
            <tr><td><span class="badge badge-info">POST</span></td><td><code>/pipelines/</code></td><td>Upload pipeline YAML</td></tr>
            <tr><td><span class="badge badge-success">GET</span></td><td><code>/pipelines/</code></td><td>List all pipelines</td></tr>
            <tr><td><span class="badge badge-success">GET</span></td><td><code>/pipelines/{name}</code></td><td>Get pipeline info</td></tr>
            <tr><td><span class="badge badge-success">GET</span></td><td><code>/pipelines/{name}/plan</code></td><td>Execution plan</td></tr>
            <tr><td><span class="badge badge-info">POST</span></td><td><code>/pipelines/{name}/invoke</code></td><td>Invoke (sync)</td></tr>
            <tr><td><span class="badge badge-info">POST</span></td><td><code>/pipelines/{name}/invoke_async</code></td><td>Invoke (async)</td></tr>
            <tr><td><span class="badge badge-success">GET</span></td><td><code>/tasks/{id}</code></td><td>Poll async result</td></tr>
            <tr><td><span class="badge badge-warning">WS</span></td><td><code>/ws/chat</code></td><td>Real-time streaming</td></tr>
          </tbody>
        </table>
        <div style="margin-top:12px; display:flex; gap:8px;">
          <button class="btn" onclick="navigate('api-docs')">Open API Docs</button>
          <button class="btn" onclick="navigate('redoc')">Open ReDoc</button>
        </div>
      </div>

      <!-- Example Pipelines -->
      <div class="card" style="margin-bottom:32px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2"><path d="M4 4h6v6H4zM14 4h6v6h-6zM9 10l5 4M4 14h6v6H4z"/></svg>
          <div class="card-title" style="margin:0;">Example Pipelines</div>
        </div>
        <p style="color:var(--text-dim); margin-bottom:12px;">Paste any of these into the Upload form to try them:</p>

        <div style="margin-bottom:16px;">
          <p style="font-size:13px; font-weight:500; color:var(--text); margin-bottom:6px;">Minimal — In-Memory Retrieval</p>
          <pre>version: "4.0"
name: minimal_rag
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
    input: retrieve</pre>
        </div>

        <div style="margin-bottom:16px;">
          <p style="font-size:13px; font-weight:500; color:var(--text); margin-bottom:6px;">Fallback — Try OpenAI, fall back to Ollama</p>
          <pre>version: "4.0"
name: fallback_rag
execution:
  strategy: fallback
  fallback_threshold: 0.5
stages:
  - id: retrieve
    adapter: qdrant
    params: { top_k: 5 }
    input: query
  - id: generate_primary
    adapter: openai_gen
    params: { model: gpt-4 }
    input: retrieve
  - id: generate_fallback
    adapter: ollama_gen
    params: { model: llama3 }
    input: retrieve</pre>
        </div>

        <div>
          <p style="font-size:13px; font-weight:500; color:var(--text); margin-bottom:6px;">Ensemble — Parallel execution + merge</p>
          <pre>version: "4.0"
name: ensemble_rag
execution:
  strategy: ensemble
  ensemble_merge: rerank
stages:
  - id: embed
    adapter: huggingface
    params: { model: BAAI/bge-large-en }
    input: query
  - id: retrieve_qdrant
    adapter: qdrant
    params: { top_k: 5 }
    input: embed
  - id: retrieve_memory
    adapter: memory
    params: { top_k: 5 }
    input: embed
  - id: rerank
    adapter: cross_encoder
    input: [retrieve_qdrant, retrieve_memory]
  - id: generate
    adapter: openai_gen
    params: { model: gpt-4 }
    input: rerank</pre>
        </div>
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

// ─── Main Tabs (RAG / OmniGraph / Graph / Chat) ───

function switchMainTab(tab) {
  activeMainTab = tab;
  // Update tab buttons
  document.querySelectorAll('.main-tab').forEach(el => {
    el.classList.toggle('active', el.dataset.tab === tab);
  });
  // Show/hide content areas
  const mainBody = document.getElementById('main-body');
  const chatBody = document.getElementById('chat-body');
  if (tab === 'chat') {
    mainBody.style.display = 'none';
    chatBody.style.display = 'flex';
    if (chatMessages.length === 0) renderChatWelcome();
  } else {
    mainBody.style.display = '';
    chatBody.style.display = 'none';
    if (tab === 'rag') renderCurrentPage();
    else if (tab === 'graphrag') renderGraphRAGTab();
    else if (tab === 'graph') renderGraphTab();
  }
}

function renderCurrentPage() {
  if (currentPage === 'home') renderHome();
  else if (activePipeline) renderPipelineMain(activePipeline);
}

function renderGraphRAGTab() {
  const body = document.getElementById('main-body');
  body.innerHTML = `
    <div style="max-width:700px;">
      <!-- Query Section -->
      <div class="card" style="margin-bottom:12px;">
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:10px;">
          <span style="font-size:16px;">🔮</span>
          <span style="font-size:14px; font-weight:600; color:var(--text);">OmniGraph Query</span>
        </div>
        <div style="display:flex; gap:8px; margin-bottom:10px;">
          <input class="input" id="graphrag-query" placeholder="Ask a question about your knowledge graph..." style="flex:1;" />
        </div>
        <div style="display:flex; gap:6px; flex-wrap:wrap; margin-bottom:8px;">
          <button class="btn btn-primary" onclick="graphragQuery('route')" style="font-size:12px;">Auto Route</button>
          <button class="btn" onclick="graphragQuery('local')" style="font-size:12px;">Local</button>
          <button class="btn" onclick="graphragQuery('global')" style="font-size:12px;">Global</button>
          <button class="btn" onclick="graphragQuery('drift')" style="font-size:12px;">DRIFT</button>
          <button class="btn" onclick="graphragQuery('hybrid')" style="font-size:12px;">Hybrid</button>
        </div>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <select id="extraction-mode" class="input" style="width:auto; font-size:11px; padding:4px 8px;">
            <option value="hybrid">Extraction: Hybrid</option>
            <option value="llm">Extraction: LLM</option>
            <option value="regex">Extraction: Regex</option>
            <option value="schema">Extraction: Schema</option>
          </select>
          <select id="schema-select" class="input" style="width:auto; font-size:11px; padding:4px 8px;">
            <option value="default">Schema: Default</option>
            <option value="legal">Schema: Legal</option>
            <option value="medical">Schema: Medical</option>
            <option value="financial">Schema: Financial</option>
          </select>
        </div>
      </div>
      <div id="graphrag-result"></div>

      <!-- Graph Stats -->
      <div class="card" style="margin-bottom:12px;">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
          <div style="display:flex; align-items:center; gap:6px;">
            <span style="font-size:14px;">📊</span>
            <span class="card-title" style="margin:0;">Knowledge Graph</span>
          </div>
          <button class="btn" onclick="loadGraphStats()" style="font-size:11px; padding:3px 8px;">Refresh</button>
        </div>
        <div id="graphrag-stats">Loading...</div>
      </div>

      <!-- Tools & Services -->
      <div class="card" style="margin-bottom:12px;">
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:10px;">
          <span style="font-size:14px;">🛠</span>
          <span class="card-title" style="margin:0;">Services</span>
        </div>
        <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(130px,1fr)); gap:6px;">
          <div class="card" style="padding:8px; margin:0; cursor:pointer; text-align:center;" onclick="showMCPTools()">
            <div style="font-size:16px; margin-bottom:2px;">🔌</div>
            <div style="font-size:11px; color:var(--text);">MCP Tools</div>
            <div style="font-size:10px; color:var(--text-dim);">5 tools</div>
          </div>
          <div class="card" style="padding:8px; margin:0; cursor:pointer; text-align:center;" onclick="showWorkflows()">
            <div style="font-size:16px; margin-bottom:2px;">⚡</div>
            <div style="font-size:11px; color:var(--text);">Workflows</div>
            <div style="font-size:10px; color:var(--text-dim);">LangGraph</div>
          </div>
          <div class="card" style="padding:8px; margin:0; cursor:pointer; text-align:center;" onclick="showAgents()">
            <div style="font-size:16px; margin-bottom:2px;">🤖</div>
            <div style="font-size:11px; color:var(--text);">Agents</div>
            <div style="font-size:10px; color:var(--text-dim);">AutoGen</div>
          </div>
          <div class="card" style="padding:8px; margin:0; cursor:pointer; text-align:center;" onclick="showAnalytics()">
            <div style="font-size:16px; margin-bottom:2px;">📈</div>
            <div style="font-size:11px; color:var(--text);">Analytics</div>
            <div style="font-size:10px; color:var(--text-dim);">Export</div>
          </div>
          <div class="card" style="padding:8px; margin:0; cursor:pointer; text-align:center;" onclick="showTraces()">
            <div style="font-size:16px; margin-bottom:2px;">🔍</div>
            <div style="font-size:11px; color:var(--text);">Traces</div>
            <div style="font-size:10px; color:var(--text-dim);">Audit</div>
          </div>
          <div class="card" style="padding:8px; margin:0; cursor:pointer; text-align:center;" onclick="showContracts()">
            <div style="font-size:16px; margin-bottom:2px;">📋</div>
            <div style="font-size:11px; color:var(--text);">Contracts</div>
            <div style="font-size:10px; color:var(--text-dim);">23 ABCs</div>
          </div>
        </div>
      </div>

      <!-- Router Rules -->
      <div class="card" style="margin-bottom:12px;">
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:8px;">
          <span style="font-size:14px;">🧭</span>
          <span class="card-title" style="margin:0;">Query Router</span>
          <span class="badge badge-info" style="font-size:10px;">25 rules · 3 stages</span>
        </div>
        <div style="font-size:12px; color:var(--text-dim); line-height:1.6;">
          <strong style="color:var(--text);">Stage 1:</strong> 25 YAML regex patterns (global/local/drift/basic/hybrid)<br>
          <strong style="color:var(--text);">Stage 2:</strong> BERT classifier (MiniLM-L6, 4 classes)<br>
          <strong style="color:var(--text);">Stage 3:</strong> Dynamic override (6 conditions: coverage, ACL, budget, load, cache, feedback)
        </div>
      </div>
    </div>
  `;
  loadGraphStats();
}

// ─── OmniGraph Sub-pages ───

async function showMCPTools() {
  const body = document.getElementById('main-body');
  body.innerHTML = '<div style="padding:0 0 12px;"><button onclick="renderGraphRAGTab()" style="display:flex;align-items:center;justify-content:center;width:24px;height:24px;background:none;border:none;color:var(--text-dim);cursor:pointer;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg></button></div>';
  try {
    const tools = await fetch(`${API}/v1/mcp/tools`).then(r => r.json());
    body.innerHTML += `<div style="max-width:700px;"><h2 style="font-size:16px;font-weight:600;color:var(--text);margin-bottom:12px;">MCP Tools (${tools.length})</h2>` +
      tools.map(t => `<div class="card" style="margin-bottom:8px;"><div class="card-title">${t.name}</div><div style="font-size:12px;color:var(--text-dim);">${t.description}</div></div>`).join('') + '</div>';
  } catch(e) { body.innerHTML += `<p style="color:var(--error);">${e.message}</p>`; }
}

async function showWorkflows() {
  const body = document.getElementById('main-body');
  body.innerHTML = '<div style="padding:0 0 12px;"><button onclick="renderGraphRAGTab()" style="display:flex;align-items:center;justify-content:center;width:24px;height:24px;background:none;border:none;color:var(--text-dim);cursor:pointer;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg></button></div>';
  try {
    const data = await fetch(`${API}/v1/workflows`).then(r => r.json());
    body.innerHTML += `<div style="max-width:700px;"><h2 style="font-size:16px;font-weight:600;color:var(--text);margin-bottom:12px;">Workflows</h2>` +
      `<p style="color:var(--text-dim); margin-bottom:12px;">Available: ${data.available?.join(', ') || 'None registered yet'}</p>` +
      `<p style="color:var(--text-dim);">Runs: ${data.runs?.length || 0}</p></div>`;
  } catch(e) { body.innerHTML += `<p style="color:var(--error);">${e.message}</p>`; }
}

async function showAgents() {
  const body = document.getElementById('main-body');
  body.innerHTML = `<div style="padding:0 0 12px;"><button onclick="renderGraphRAGTab()" style="display:flex;align-items:center;justify-content:center;width:24px;height:24px;background:none;border:none;color:var(--text-dim);cursor:pointer;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg></button></div>
    <div style="max-width:700px;">
      <h2 style="font-size:16px;font-weight:600;color:var(--text);margin-bottom:12px;">Multi-Agent (AutoGen)</h2>
      <div class="card"><div class="card-title">🔬 Researcher</div><div style="font-size:12px;color:var(--text-dim);">Searches knowledge graph for entities, relationships, evidence</div></div>
      <div class="card"><div class="card-title">📝 Analyst</div><div style="font-size:12px;color:var(--text-dim);">Synthesizes findings into coherent narrative with citations</div></div>
      <div class="card"><div class="card-title">✅ Reviewer</div><div style="font-size:12px;color:var(--text-dim);">Validates accuracy, completeness, citations. Approves or requests revision</div></div>
    </div>`;
}

async function showAnalytics() {
  const body = document.getElementById('main-body');
  body.innerHTML = '<div style="padding:0 0 12px;"><button onclick="renderGraphRAGTab()" style="display:flex;align-items:center;justify-content:center;width:24px;height:24px;background:none;border:none;color:var(--text-dim);cursor:pointer;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg></button></div>';
  try {
    const data = await fetch(`${API}/v1/analytics/summary`).then(r => r.json());
    body.innerHTML += `<div style="max-width:700px;"><h2 style="font-size:16px;font-weight:600;color:var(--text);margin-bottom:12px;">Analytics</h2>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;">
        <div class="card" style="padding:10px;margin:0;text-align:center;"><div style="font-size:20px;font-weight:700;color:var(--text);">${data.entities||0}</div><div style="font-size:11px;color:var(--text-dim);">Entities</div></div>
        <div class="card" style="padding:10px;margin:0;text-align:center;"><div style="font-size:20px;font-weight:700;color:var(--text);">${data.relationships||0}</div><div style="font-size:11px;color:var(--text-dim);">Relationships</div></div>
        <div class="card" style="padding:10px;margin:0;text-align:center;"><div style="font-size:20px;font-weight:700;color:var(--text);">${data.communities||0}</div><div style="font-size:11px;color:var(--text-dim);">Communities</div></div>
        <div class="card" style="padding:10px;margin:0;text-align:center;"><div style="font-size:20px;font-weight:700;color:var(--text);">${data.reports||0}</div><div style="font-size:11px;color:var(--text-dim);">Reports</div></div>
        <div class="card" style="padding:10px;margin:0;text-align:center;"><div style="font-size:20px;font-weight:700;color:var(--text);">${data.traces||0}</div><div style="font-size:11px;color:var(--text-dim);">Traces</div></div>
      </div>
      <div style="margin-top:12px; display:flex; gap:6px; flex-wrap:wrap;">
        <a href="/v1/analytics/entities" target="_blank" class="btn" style="font-size:11px; padding:3px 8px;">Export Entities</a>
        <a href="/v1/analytics/communities" target="_blank" class="btn" style="font-size:11px; padding:3px 8px;">Export Communities</a>
        <a href="/v1/analytics/relationships" target="_blank" class="btn" style="font-size:11px; padding:3px 8px;">Export Relationships</a>
      </div>
    </div>`;
  } catch(e) { body.innerHTML += `<p style="color:var(--error);">${e.message}</p>`; }
}

async function showTraces() {
  const body = document.getElementById('main-body');
  body.innerHTML = '<div style="padding:0 0 12px;"><button onclick="renderGraphRAGTab()" style="display:flex;align-items:center;justify-content:center;width:24px;height:24px;background:none;border:none;color:var(--text-dim);cursor:pointer;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg></button></div>';
  try {
    const data = await fetch(`${API}/lineage`).then(r => r.json());
    body.innerHTML += `<div style="max-width:700px;"><h2 style="font-size:16px;font-weight:600;color:var(--text);margin-bottom:12px;">Query Traces & Lineage</h2>
      <p style="color:var(--text-dim);margin-bottom:8px;">Events: ${data.counts?.events||0} · Tombstones: ${data.counts?.tombstones||0}</p>
      ${data.events?.length ? data.events.slice(0,10).map(e => `<div class="card" style="padding:8px;margin-bottom:4px;font-size:12px;"><code>${e.event_type}</code> ${e.from_state||''} → ${e.to_state||''} <span style="color:var(--text-muted);">${e.job_id?.slice(0,12)||''}</span></div>`).join('') : '<p style="color:var(--text-muted);">No traces yet. Run a query to generate traces.</p>'}
    </div>`;
  } catch(e) { body.innerHTML += `<p style="color:var(--error);">${e.message}</p>`; }
}

function showContracts() {
  const body = document.getElementById('main-body');
  const contracts = ['Parser','Normalizer','Extractor','EntityResolver','GraphBuilder','CommunityBuilder','ReportGenerator','Embedder','GraphStore','VectorStore','TextIndex','GraphAlgorithm','QueryRouter','RetrievalPlanner','GraphRetriever','VectorRetriever','HybridRetriever','ContextBuilder','AuthorizationEngine','CacheManager','Reasoner','AnswerSynthesizer','TraceRecorder','WorkflowRunner','ToolProvider'];
  body.innerHTML = `<div style="padding:0 0 12px;"><button onclick="renderGraphRAGTab()" style="display:flex;align-items:center;justify-content:center;width:24px;height:24px;background:none;border:none;color:var(--text-dim);cursor:pointer;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg></button></div>
    <div style="max-width:700px;"><h2 style="font-size:16px;font-weight:600;color:var(--text);margin-bottom:12px;">Service Contracts (${contracts.length})</h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:6px;">
      ${contracts.map(c => `<div class="card" style="padding:6px 10px;margin:0;"><code style="font-size:11px;">${c}</code></div>`).join('')}
    </div></div>`;
}

async function graphragQuery(mode) {
  const query = document.getElementById('graphrag-query').value;
  if (!query) { showToast('Query required', 'error'); return; }
  const result = document.getElementById('graphrag-result');
  result.innerHTML = '<div style="display:flex;align-items:center;gap:8px;margin-top:12px;"><div class="spinner"></div> Querying...</div>';
  try {
    const r = await fetch(`${API}/graphrag/query/${mode}`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ query, user_principal: 'public' }),
    });
    const data = await r.json();
    result.innerHTML = `
      <div class="card" style="margin-top:12px;">
        <div class="card-title">Result <span class="badge badge-info">${data.mode || mode}</span></div>
        <div class="card-body">
          <p style="color:var(--text); margin-bottom:8px;">${data.answer || 'No answer'}</p>
          ${data.citations?.length ? '<p style="color:var(--text-dim); font-size:12px;">Citations: ' + data.citations.map(c => '<code>' + c.chunk_id?.slice(0,8) + '</code>').join(', ') + '</p>' : ''}
          <p style="color:var(--text-muted); font-size:11px; margin-top:8px;">
            Mode: ${data.mode || mode} · Latency: ${data.latency_ms || '—'}ms · Cache: ${data.cache_hit ? 'HIT' : 'MISS'}
          </p>
        </div>
      </div>
    `;
  } catch(e) { result.innerHTML = `<div class="card" style="margin-top:12px;"><div class="card-title" style="color:var(--error)">Error</div><div class="card-body"><code>${e.message}</code></div></div>`; }
}

async function loadGraphStats() {
  try {
    const data = await fetch(`${API}/graphrag/stats`).then(r => r.json());
    document.getElementById('graphrag-stats').innerHTML = `
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(120px,1fr)); gap:8px;">
        <div><strong style="color:var(--text)">${data.graph?.entities || 0}</strong><br><span style="font-size:11px; color:var(--text-dim)">Entities</span></div>
        <div><strong style="color:var(--text)">${data.graph?.relationships || 0}</strong><br><span style="font-size:11px; color:var(--text-dim)">Relationships</span></div>
        <div><strong style="color:var(--text)">${data.graph?.communities || 0}</strong><br><span style="font-size:11px; color:var(--text-dim)">Communities</span></div>
        <div><strong style="color:var(--text)">${data.graph?.reports || 0}</strong><br><span style="font-size:11px; color:var(--text-dim)">Reports</span></div>
        <div><strong style="color:var(--text)">${data.cache?.hits || 0}</strong><br><span style="font-size:11px; color:var(--text-dim)">Cache Hits</span></div>
        <div><strong style="color:var(--text)">${data.stale_communities || 0}</strong><br><span style="font-size:11px; color:var(--text-dim)">Stale</span></div>
      </div>
    `;
  } catch { document.getElementById('graphrag-stats').textContent = 'Failed to load stats'; }
}

function renderGraphTab() {
  const body = document.getElementById('main-body');
  body.innerHTML = `
    <div style="display:flex; flex-direction:column; height:100%; margin:-24px -20px;">
      <!-- Toolbar Row 1 -->
      <div style="display:flex; align-items:center; gap:6px; padding:8px 12px; border-bottom:1px solid var(--border); flex-shrink:0; flex-wrap:wrap;">
        <input class="input" id="entity-search" placeholder="Search entity..." style="flex:1; min-width:120px; font-size:12px; padding:5px 8px;" />
        <button class="btn btn-primary" onclick="searchAndFocusEntity()" style="font-size:11px; padding:4px 10px;">Search</button>
        <button class="btn" onclick="loadGraphData()" style="font-size:11px; padding:4px 10px;">Reload</button>
        <button class="btn" onclick="addSampleData()" style="font-size:11px; padding:4px 10px;">+ Sample</button>
        <select id="layout-select" onchange="switchLayout(this.value)" class="input" style="width:auto; font-size:11px; padding:4px 6px;">
          <option value="force">Force</option>
          <option value="hierarchy">Hierarchy</option>
          <option value="circular">Circular</option>
        </select>
        <select id="color-mode" onchange="switchColorMode(this.value)" class="input" style="width:auto; font-size:11px; padding:4px 6px;">
          <option value="type">Color: Type</option>
          <option value="community">Color: Community</option>
        </select>
        <button class="btn" id="path-btn" onclick="togglePathMode()" style="font-size:11px; padding:4px 10px;">🔗 Path</button>
        <button class="btn" onclick="exportGraphPNG()" style="font-size:11px; padding:4px 10px;">📷</button>
        <span id="collab-indicator" style="font-size:11px; color:var(--text-muted);"></span>
      </div>
      <!-- Body: Filter Panel + Canvas -->
      <div style="flex:1; display:flex; overflow:hidden;">
        <!-- Filter Panel (V2) -->
        <div id="filter-panel" style="width:160px; flex-shrink:0; background:var(--bg-base); border-right:1px solid var(--border); padding:8px; overflow-y:auto; font-size:11px; scrollbar-width:none;">
          <div style="font-weight:600; color:var(--text); margin-bottom:6px;">Filters</div>
          <div style="margin-bottom:8px;">
            <div style="color:var(--text-dim); margin-bottom:4px;">Entity Types</div>
            <div id="filter-types"></div>
          </div>
          <div style="margin-bottom:8px;">
            <div style="color:var(--text-dim); margin-bottom:4px;">Relationships</div>
            <div id="filter-rels"></div>
          </div>
          <div style="margin-bottom:8px;">
            <div style="color:var(--text-dim); margin-bottom:4px;">Weight ≥</div>
            <input type="range" id="filter-weight" min="0" max="5" step="0.5" value="0" style="width:100%;" oninput="applyFilters()">
            <div style="display:flex; justify-content:space-between; color:var(--text-muted);"><span>0</span><span id="weight-val">0</span><span>5</span></div>
          </div>
          <div style="margin-bottom:8px;">
            <div style="color:var(--text-dim); margin-bottom:4px;">Community</div>
            <select id="filter-community" class="input" style="font-size:10px; padding:3px;" onchange="applyFilters()">
              <option value="">All</option>
            </select>
          </div>
          <div style="color:var(--text-muted); margin-bottom:6px;" id="filter-count"></div>
          <button class="btn" onclick="resetFilters()" style="font-size:10px; padding:3px 8px; width:100%;">Reset</button>
        </div>
        <!-- Canvas -->
        <div style="flex:1; position:relative; overflow:hidden; background:#0a0c0f;">
          <canvas id="graph-canvas" style="width:100%; height:100%; cursor:grab;"></canvas>
          <!-- Legend -->
          <div id="graph-legend" style="position:absolute; top:8px; right:8px; background:rgba(13,13,13,0.9); border:1px solid var(--border); border-radius:6px; padding:6px 10px; font-size:9px;"></div>
          <!-- Node detail + comments panel -->
          <div id="node-detail" style="display:none; position:absolute; bottom:8px; left:8px; right:8px; background:rgba(13,13,13,0.95); border:1px solid var(--border); border-radius:8px; padding:10px; font-size:11px; max-height:40%; overflow-y:auto;"></div>
          <!-- Path info -->
          <div id="path-info" style="display:none; position:absolute; top:8px; left:8px; background:rgba(99,102,241,0.15); border:1px solid #6366f1; border-radius:6px; padding:6px 10px; font-size:11px; color:var(--text);"></div>
          <!-- Stats -->
          <div id="graph-canvas-stats" style="position:absolute; bottom:8px; right:8px; font-size:9px; color:#444;"></div>
        </div>
      </div>
    </div>
  `;
  initGraphCanvas();
  loadGraphData();
}

// ─── Knowledge Graph Visualization (V1–V8 Full Engine) ───

const graphViz = {
  nodes: [], edges: [], canvas: null, ctx: null,
  width: 0, height: 0,
  offsetX: 0, offsetY: 0, scale: 1,
  dragging: null, panning: false, panStart: {x:0,y:0},
  selected: null, animFrame: null,
  // V1: layout
  layout: 'force',
  // V2: filters
  filters: { types: new Set(), relTypes: new Set(), weightMin: 0, search: '', community: '' },
  // V3: pathfinding
  pathMode: false, pathSource: null, pathTarget: null, pathNodes: new Set(), pathEdges: new Set(),
  // V4: color mode
  colorMode: 'type', communityColors: {},
  // V6: expand/collapse
  expansions: new Map(),
  // V8: comments
  comments: {},
};

const TYPE_COLORS = {
  PERSON: '#6366f1', ORG: '#4caf50', PRODUCT: '#f59e0b',
  PROJECT: '#ef4444', CONCEPT: '#06b6d4', LOCATION: '#a855f7',
  EVENT: '#ec4899', REGULATORY_TERM: '#f97316', ENTITY: '#888',
};

function initGraphCanvas() {
  const canvas = document.getElementById('graph-canvas');
  if (!canvas) return;
  graphViz.canvas = canvas;
  graphViz.ctx = canvas.getContext('2d');

  const resize = () => {
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    graphViz.width = rect.width;
    graphViz.height = rect.height;
    graphViz.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    drawGraph();
  };
  resize();
  window.addEventListener('resize', resize);

  // Mouse/touch events
  canvas.addEventListener('mousedown', graphMouseDown);
  canvas.addEventListener('mousemove', graphMouseMove);
  canvas.addEventListener('mouseup', graphMouseUp);
  canvas.addEventListener('wheel', graphWheel);
  canvas.addEventListener('touchstart', graphTouchStart, {passive:false});
  canvas.addEventListener('touchmove', graphTouchMove, {passive:false});
  canvas.addEventListener('touchend', graphTouchEnd);
  canvas.addEventListener('dblclick', graphDblClick);
}

function toScreen(x, y) {
  return { x: (x + graphViz.offsetX) * graphViz.scale + graphViz.width/2,
           y: (y + graphViz.offsetY) * graphViz.scale + graphViz.height/2 };
}
function toWorld(sx, sy) {
  return { x: (sx - graphViz.width/2) / graphViz.scale - graphViz.offsetX,
           y: (sy - graphViz.height/2) / graphViz.scale - graphViz.offsetY };
}

function findNodeAt(sx, sy) {
  const w = toWorld(sx, sy);
  for (const n of graphViz.nodes) {
    const dx = n.x - w.x, dy = n.y - w.y;
    if (dx*dx + dy*dy < (n.radius||16) * (n.radius||16)) return n;
  }
  return null;
}

function graphMouseDown(e) {
  const rect = graphViz.canvas.getBoundingClientRect();
  const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
  const node = findNodeAt(sx, sy);
  if (node) {
    graphViz.dragging = node;
    graphViz.canvas.style.cursor = 'grabbing';
  } else {
    graphViz.panning = true;
    graphViz.panStart = {x: e.clientX, y: e.clientY};
    graphViz.canvas.style.cursor = 'grabbing';
  }
}
function graphMouseMove(e) {
  const rect = graphViz.canvas.getBoundingClientRect();
  if (graphViz.dragging) {
    const w = toWorld(e.clientX - rect.left, e.clientY - rect.top);
    graphViz.dragging.x = w.x;
    graphViz.dragging.y = w.y;
    graphViz.dragging.fx = w.x;
    graphViz.dragging.fy = w.y;
    drawGraph();
  } else if (graphViz.panning) {
    graphViz.offsetX += (e.clientX - graphViz.panStart.x) / graphViz.scale;
    graphViz.offsetY += (e.clientY - graphViz.panStart.y) / graphViz.scale;
    graphViz.panStart = {x: e.clientX, y: e.clientY};
    drawGraph();
  }
}
function graphMouseUp(e) {
  if (graphViz.dragging) {
    delete graphViz.dragging.fx;
    delete graphViz.dragging.fy;
    selectNode(graphViz.dragging);
  }
  graphViz.dragging = null;
  graphViz.panning = false;
  graphViz.canvas.style.cursor = 'grab';
}
function graphWheel(e) {
  e.preventDefault();
  const factor = e.deltaY > 0 ? 0.9 : 1.1;
  graphViz.scale = Math.max(0.1, Math.min(5, graphViz.scale * factor));
  drawGraph();
}
function graphTouchStart(e) {
  e.preventDefault();
  if (e.touches.length === 1) {
    const t = e.touches[0];
    const rect = graphViz.canvas.getBoundingClientRect();
    const node = findNodeAt(t.clientX - rect.left, t.clientY - rect.top);
    if (node) { graphViz.dragging = node; }
    else { graphViz.panning = true; graphViz.panStart = {x:t.clientX, y:t.clientY}; }
  }
}
function graphTouchMove(e) {
  e.preventDefault();
  if (e.touches.length === 1) {
    const t = e.touches[0];
    const rect = graphViz.canvas.getBoundingClientRect();
    if (graphViz.dragging) {
      const w = toWorld(t.clientX - rect.left, t.clientY - rect.top);
      graphViz.dragging.x = w.x; graphViz.dragging.y = w.y;
      drawGraph();
    } else if (graphViz.panning) {
      graphViz.offsetX += (t.clientX - graphViz.panStart.x) / graphViz.scale;
      graphViz.offsetY += (t.clientY - graphViz.panStart.y) / graphViz.scale;
      graphViz.panStart = {x:t.clientX, y:t.clientY};
      drawGraph();
    }
  }
}
function graphTouchEnd() { graphViz.dragging = null; graphViz.panning = false; }
function graphDblClick(e) {
  const rect = graphViz.canvas.getBoundingClientRect();
  const node = findNodeAt(e.clientX - rect.left, e.clientY - rect.top);
  if (node) selectNode(node);
}

function selectNode(node) {
  if (graphViz.pathMode) { handlePathClick(node); return; }
  graphViz.selected = node;
  const detail = document.getElementById('node-detail');
  if (!detail) return;
  const neighbors = graphViz.edges.filter(e => e.source === node.id || e.target === node.id);
  const commentCount = graphViz.comments[node.id] || 0;
  detail.style.display = 'block';
  detail.innerHTML = `
    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
      <div style="display:flex; align-items:center; gap:6px;">
        <div style="width:10px;height:10px;border-radius:50%;background:${getNodeColor(node)};"></div>
        <strong style="color:var(--text);">${node.label}</strong>
        <span class="badge badge-info" style="font-size:9px;">${node.type}</span>
        ${node.community ? `<span class="badge" style="font-size:9px;background:rgba(255,255,255,0.06);color:var(--text-dim);">C:${node.community.slice(0,6)}</span>` : ''}
      </div>
      <button onclick="document.getElementById('node-detail').style.display='none'" style="background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:14px;">✕</button>
    </div>
    ${node.aliases?.length ? `<div style="color:var(--text-dim);margin-bottom:4px;">Aliases: ${node.aliases.join(', ')}</div>` : ''}
    <div style="color:var(--text-dim);margin-bottom:6px;">Connections: ${neighbors.length}${commentCount ? ` · 💬 ${commentCount}` : ''}</div>
    <div style="display:flex; gap:4px; margin-bottom:6px;">
      <button class="btn" onclick="expandNode('${node.id}')" style="font-size:10px;padding:2px 6px;">Expand</button>
      <button class="btn" onclick="collapseNode('${node.id}')" style="font-size:10px;padding:2px 6px;">Collapse</button>
      <button class="btn" onclick="addComment('${node.id}')" style="font-size:10px;padding:2px 6px;">💬 Comment</button>
    </div>
    ${neighbors.length ? `<div>` + neighbors.slice(0,15).map(e => {
      const other = e.source === node.id ? e.targetLabel : e.sourceLabel;
      const dir = e.source === node.id ? '→' : '←';
      return `<div style="padding:1px 0;color:var(--text-dim);font-size:10px;">${dir} <span style="color:var(--text);">${other}</span> <span style="color:var(--text-muted);">(${e.type}, w:${e.weight})</span></div>`;
    }).join('') + (neighbors.length > 15 ? `<div style="color:var(--text-muted);font-size:10px;">...and ${neighbors.length-15} more</div>` : '') + '</div>' : ''}
  `;
  drawGraph();
}

function drawGraph() {
  const {ctx, width, height, nodes, edges, scale, offsetX, offsetY, selected, pathNodes, pathEdges} = graphViz;
  if (!ctx) return;
  ctx.clearRect(0, 0, width, height);

  const visibleNodes = nodes.filter(n => isNodeVisible(n));
  const visibleEdges = edges.filter(e => isEdgeVisible(e));

  // Edges
  for (const e of visibleEdges) {
    const src = nodes.find(n => n.id === e.source);
    const tgt = nodes.find(n => n.id === e.target);
    if (!src || !tgt) continue;
    const p1 = toScreen(src.x, src.y);
    const p2 = toScreen(tgt.x, tgt.y);

    const isPath = pathEdges.has(e);
    const isSelected = selected && (e.source === selected.id || e.target === selected.id);

    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.strokeStyle = isPath ? '#6366f1' : isSelected ? '#4a4a6a' : '#1e1e1e';
    ctx.lineWidth = isPath ? Math.max(2, 3 * scale) : Math.max(0.5, e.weight * 0.4 * scale);
    ctx.stroke();

    if (scale > 0.6) {
      const mx = (p1.x + p2.x) / 2, my = (p1.y + p2.y) / 2;
      ctx.fillStyle = isPath ? '#818cf8' : '#333';
      ctx.font = `${Math.max(7, 8 * scale)}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.fillText(e.type, mx, my - 3);
    }
  }

  // Nodes
  for (const n of visibleNodes) {
    const p = toScreen(n.x, n.y);
    const r = (n.radius || 14) * scale;
    const isSelected = selected && selected.id === n.id;
    const isPath = pathNodes.has(n.id);
    const color = getNodeColor(n);

    // Path glow
    if (isPath) {
      ctx.beginPath();
      ctx.arc(p.x, p.y, r + 6, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(99,102,241,0.25)';
      ctx.fill();
    }
    // Selected glow
    if (isSelected) {
      ctx.beginPath();
      ctx.arc(p.x, p.y, r + 4, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,255,255,0.1)';
      ctx.fill();
    }

    // Circle
    ctx.beginPath();
    ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    if (isSelected || isPath) {
      ctx.strokeStyle = isPath ? '#6366f1' : '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    // Comment badge (V8)
    const comments = graphViz.comments[n.id];
    if (comments && scale > 0.5) {
      ctx.fillStyle = '#f59e0b';
      ctx.beginPath();
      ctx.arc(p.x + r * 0.7, p.y - r * 0.7, 6 * scale, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#000';
      ctx.font = `${Math.max(6, 7 * scale)}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.fillText(comments, p.x + r * 0.7, p.y - r * 0.7 + 3 * scale);
    }

    // Label
    if (scale > 0.4) {
      ctx.fillStyle = '#d0d0d0';
      ctx.font = `${Math.max(8, 10 * scale)}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.fillText(n.label, p.x, p.y + r + 11 * scale);
    }
  }

  // Stats
  const stats = document.getElementById('graph-canvas-stats');
  if (stats) stats.textContent = `${visibleNodes.length}/${nodes.length} nodes · ${visibleEdges.length}/${edges.length} edges · ${scale.toFixed(1)}x`;
}

// Force simulation (simple spring layout)
function runForceLayout(iterations = 100) {
  const {nodes, edges} = graphViz;
  if (nodes.length === 0) return;

  for (let iter = 0; iter < iterations; iter++) {
    // Repulsion (nodes push each other)
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        let dx = nodes[j].x - nodes[i].x;
        let dy = nodes[j].y - nodes[i].y;
        let dist = Math.sqrt(dx*dx + dy*dy) || 1;
        let force = 800 / (dist * dist);
        nodes[i].x -= dx / dist * force;
        nodes[i].y -= dy / dist * force;
        nodes[j].x += dx / dist * force;
        nodes[j].y += dy / dist * force;
      }
    }
    // Attraction (edges pull connected nodes)
    for (const e of edges) {
      const src = nodes.find(n => n.id === e.source);
      const tgt = nodes.find(n => n.id === e.target);
      if (!src || !tgt) continue;
      let dx = tgt.x - src.x;
      let dy = tgt.y - src.y;
      let dist = Math.sqrt(dx*dx + dy*dy) || 1;
      let force = (dist - 80) * 0.01;
      src.x += dx / dist * force;
      src.y += dy / dist * force;
      tgt.x -= dx / dist * force;
      tgt.y -= dy / dist * force;
    }
    // Center gravity
    for (const n of nodes) {
      n.x *= 0.99;
      n.y *= 0.99;
    }
  }
  drawGraph();
}

async function loadGraphData() {
  try {
    const data = await fetch(`${API}/graphrag/stats`).then(r => r.json());
    // Load entities from analytics
    const entities = await fetch(`${API}/v1/analytics/entities`).then(r => r.json()).catch(() => []);
    const rels = await fetch(`${API}/v1/analytics/relationships`).then(r => r.json()).catch(() => []);

    graphViz.nodes = entities.map((e, i) => ({
      id: e.id, label: e.name, type: e.type || 'ENTITY',
      aliases: [], connections: e.connections || 0,
      x: (Math.random() - 0.5) * 300, y: (Math.random() - 0.5) * 300,
      radius: Math.max(10, Math.min(22, 10 + (e.connections || 0) * 2)),
    }));

    graphViz.edges = rels.map(r => ({
      source: r.source_id, target: r.target_id,
      sourceLabel: r.source_name, targetLabel: r.target_name,
      type: r.type || 'RELATED_TO', weight: r.weight || 1,
    }));

    buildFilterUI();
    if (graphViz.nodes.length > 0) {
      runForceLayout(150);
    } else {
      drawGraph();
    }
  } catch(e) { console.error('loadGraphData:', e); drawGraph(); }
}

function searchAndFocusEntity() {
  const name = document.getElementById('entity-search').value.toLowerCase();
  if (!name) return;
  const node = graphViz.nodes.find(n => n.label.toLowerCase().includes(name));
  if (node) {
    graphViz.offsetX = -node.x;
    graphViz.offsetY = -node.y;
    graphViz.scale = 1.5;
    selectNode(node);
  } else {
    showToast('Entity not found', 'error');
  }
}

async function addSampleData() {
  // Add sample entities and relationships for demo
  const samples = [
    {id:'s1', label:'OmniRAG', type:'PROJECT', x:0, y:0, radius:20},
    {id:'s2', label:'Neo4j', type:'PRODUCT', x:80, y:-60, radius:16},
    {id:'s3', label:'PostgreSQL', type:'PRODUCT', x:-80, y:-60, radius:16},
    {id:'s4', label:'Qdrant', type:'PRODUCT', x:100, y:50, radius:14},
    {id:'s5', label:'Redis', type:'PRODUCT', x:-100, y:50, radius:14},
    {id:'s6', label:'Ollama', type:'PRODUCT', x:0, y:100, radius:14},
    {id:'s7', label:'OmniGraph', type:'PROJECT', x:50, y:-120, radius:18},
    {id:'s8', label:'GraphRAG', type:'CONCEPT', x:-50, y:-120, radius:14},
    {id:'s9', label:'LangGraph', type:'PRODUCT', x:150, y:0, radius:12},
    {id:'s10', label:'AutoGen', type:'PRODUCT', x:-150, y:0, radius:12},
  ];
  const sampleEdges = [
    {source:'s1',target:'s2',sourceLabel:'OmniRAG',targetLabel:'Neo4j',type:'USES',weight:4},
    {source:'s1',target:'s3',sourceLabel:'OmniRAG',targetLabel:'PostgreSQL',type:'USES',weight:4},
    {source:'s1',target:'s4',sourceLabel:'OmniRAG',targetLabel:'Qdrant',type:'USES',weight:3},
    {source:'s1',target:'s5',sourceLabel:'OmniRAG',targetLabel:'Redis',type:'USES',weight:3},
    {source:'s1',target:'s6',sourceLabel:'OmniRAG',targetLabel:'Ollama',type:'INTEGRATES_WITH',weight:3},
    {source:'s7',target:'s2',sourceLabel:'OmniGraph',targetLabel:'Neo4j',type:'DEPENDS_ON',weight:5},
    {source:'s7',target:'s1',sourceLabel:'OmniGraph',targetLabel:'OmniRAG',type:'PART_OF',weight:5},
    {source:'s8',target:'s7',sourceLabel:'GraphRAG',targetLabel:'OmniGraph',type:'INSPIRES',weight:3},
    {source:'s1',target:'s9',sourceLabel:'OmniRAG',targetLabel:'LangGraph',type:'INTEGRATES_WITH',weight:2},
    {source:'s1',target:'s10',sourceLabel:'OmniRAG',targetLabel:'AutoGen',type:'INTEGRATES_WITH',weight:2},
    {source:'s7',target:'s8',sourceLabel:'OmniGraph',targetLabel:'GraphRAG',type:'RELATED_TO',weight:2},
  ];

  // Merge with existing
  for (const s of samples) {
    if (!graphViz.nodes.find(n => n.id === s.id)) graphViz.nodes.push(s);
  }
  for (const e of sampleEdges) {
    if (!graphViz.edges.find(x => x.source === e.source && x.target === e.target)) graphViz.edges.push(e);
  }
  buildFilterUI();
  runForceLayout(200);
  showToast(`${samples.length} nodes + ${sampleEdges.length} edges added`);
}

async function searchEntity() {
  searchAndFocusEntity();
}

// ─── V1: Layout Algorithms ───

function switchLayout(layout) {
  graphViz.layout = layout;
  if (layout === 'force') runForceLayout(150);
  else if (layout === 'hierarchy') runHierarchyLayout();
  else if (layout === 'circular') runCircularLayout();
}

function runHierarchyLayout() {
  const {nodes, edges} = graphViz;
  if (!nodes.length) return;
  // Sort by connection count (most connected at top)
  const conns = {};
  edges.forEach(e => { conns[e.source] = (conns[e.source]||0)+1; conns[e.target] = (conns[e.target]||0)+1; });
  const sorted = [...nodes].sort((a,b) => (conns[b.id]||0) - (conns[a.id]||0));
  const cols = Math.ceil(Math.sqrt(sorted.length));
  sorted.forEach((n, i) => {
    n.x = (i % cols - cols/2) * 100;
    n.y = (Math.floor(i / cols) - Math.floor(sorted.length/cols)/2) * 80;
  });
  drawGraph();
}

function runCircularLayout() {
  const {nodes} = graphViz;
  if (!nodes.length) return;
  const radius = Math.max(100, nodes.length * 15);
  nodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / nodes.length;
    n.x = Math.cos(angle) * radius;
    n.y = Math.sin(angle) * radius;
  });
  drawGraph();
}

// ─── V2: Filters ───

function buildFilterUI() {
  const types = new Set(graphViz.nodes.map(n => n.type));
  const relTypes = new Set(graphViz.edges.map(e => e.type));
  const communities = new Set(graphViz.nodes.map(n => n.community).filter(Boolean));

  const typesEl = document.getElementById('filter-types');
  if (typesEl) typesEl.innerHTML = [...types].map(t =>
    `<label style="display:flex;align-items:center;gap:4px;margin-bottom:2px;cursor:pointer;"><input type="checkbox" checked onchange="applyFilters()" data-filter-type="${t}"><div style="width:6px;height:6px;border-radius:50%;background:${TYPE_COLORS[t]||'#888'};"></div>${t}</label>`
  ).join('');

  const relsEl = document.getElementById('filter-rels');
  if (relsEl) relsEl.innerHTML = [...relTypes].map(t =>
    `<label style="display:flex;align-items:center;gap:4px;margin-bottom:2px;cursor:pointer;"><input type="checkbox" checked onchange="applyFilters()" data-filter-rel="${t}">${t}</label>`
  ).join('');

  const commEl = document.getElementById('filter-community');
  if (commEl) {
    commEl.innerHTML = '<option value="">All</option>' + [...communities].map(c =>
      `<option value="${c}">${c.slice(0,8)}</option>`
    ).join('');
  }

  updateLegend();
}

function applyFilters() {
  const activeTypes = new Set();
  document.querySelectorAll('[data-filter-type]').forEach(cb => { if (cb.checked) activeTypes.add(cb.dataset.filterType); });
  const activeRels = new Set();
  document.querySelectorAll('[data-filter-rel]').forEach(cb => { if (cb.checked) activeRels.add(cb.dataset.filterRel); });
  const weightMin = parseFloat(document.getElementById('filter-weight')?.value || '0');
  const community = document.getElementById('filter-community')?.value || '';

  graphViz.filters = { types: activeTypes, relTypes: activeRels, weightMin, community };

  const wv = document.getElementById('weight-val');
  if (wv) wv.textContent = weightMin;

  // Count visible
  const visNodes = graphViz.nodes.filter(n => isNodeVisible(n)).length;
  const fc = document.getElementById('filter-count');
  if (fc) fc.textContent = `${visNodes} of ${graphViz.nodes.length}`;

  drawGraph();
}

function resetFilters() {
  document.querySelectorAll('[data-filter-type],[data-filter-rel]').forEach(cb => cb.checked = true);
  const w = document.getElementById('filter-weight'); if (w) w.value = 0;
  const c = document.getElementById('filter-community'); if (c) c.value = '';
  graphViz.filters = { types: new Set(), relTypes: new Set(), weightMin: 0, community: '' };
  drawGraph();
}

function isNodeVisible(n) {
  const f = graphViz.filters;
  if (f.types.size > 0 && !f.types.has(n.type)) return false;
  if (f.community && n.community !== f.community) return false;
  return true;
}

function isEdgeVisible(e) {
  const f = graphViz.filters;
  if (f.relTypes.size > 0 && !f.relTypes.has(e.type)) return false;
  if (e.weight < f.weightMin) return false;
  const src = graphViz.nodes.find(n => n.id === e.source);
  const tgt = graphViz.nodes.find(n => n.id === e.target);
  if (src && !isNodeVisible(src)) return false;
  if (tgt && !isNodeVisible(tgt)) return false;
  return true;
}

// ─── V3: Path Finding ───

function togglePathMode() {
  graphViz.pathMode = !graphViz.pathMode;
  graphViz.pathSource = null;
  graphViz.pathTarget = null;
  graphViz.pathNodes.clear();
  graphViz.pathEdges.clear();
  const btn = document.getElementById('path-btn');
  if (btn) btn.style.background = graphViz.pathMode ? '#6366f1' : '';
  if (btn) btn.style.color = graphViz.pathMode ? '#fff' : '';
  const pi = document.getElementById('path-info');
  if (pi) pi.style.display = 'none';
  drawGraph();
}

function handlePathClick(node) {
  if (!graphViz.pathSource) {
    graphViz.pathSource = node.id;
    showToast(`Start: ${node.label}. Click destination.`);
  } else if (!graphViz.pathTarget) {
    graphViz.pathTarget = node.id;
    computeShortestPath();
  }
}

function computeShortestPath() {
  const {nodes, edges, pathSource, pathTarget} = graphViz;
  if (!pathSource || !pathTarget) return;

  // BFS
  const queue = [[pathSource]];
  const visited = new Set([pathSource]);
  let found = null;

  while (queue.length > 0) {
    const path = queue.shift();
    const current = path[path.length - 1];
    if (current === pathTarget) { found = path; break; }

    for (const e of edges) {
      let neighbor = null;
      if (e.source === current && !visited.has(e.target)) neighbor = e.target;
      if (e.target === current && !visited.has(e.source)) neighbor = e.source;
      if (neighbor) {
        visited.add(neighbor);
        queue.push([...path, neighbor]);
      }
    }
  }

  const pi = document.getElementById('path-info');
  if (found) {
    graphViz.pathNodes = new Set(found);
    graphViz.pathEdges.clear();
    let totalWeight = 0;
    for (let i = 0; i < found.length - 1; i++) {
      const edge = edges.find(e =>
        (e.source === found[i] && e.target === found[i+1]) ||
        (e.target === found[i] && e.source === found[i+1])
      );
      if (edge) { graphViz.pathEdges.add(edge); totalWeight += edge.weight || 1; }
    }
    const names = found.map(id => nodes.find(n => n.id === id)?.label || id.slice(0,8));
    if (pi) { pi.style.display = 'block'; pi.innerHTML = `Path: ${names.join(' → ')} (length ${found.length-1}, weight ${totalWeight.toFixed(1)}) <button onclick="togglePathMode()" style="margin-left:8px;background:none;border:none;color:var(--text-dim);cursor:pointer;">✕</button>`; }
  } else {
    if (pi) { pi.style.display = 'block'; pi.textContent = 'No path found'; }
  }
  drawGraph();
}

// ─── V4: Color Mode ───

function switchColorMode(mode) {
  graphViz.colorMode = mode;
  updateLegend();
  drawGraph();
}

function getNodeColor(n) {
  if (graphViz.colorMode === 'community' && n.community) {
    if (!graphViz.communityColors[n.community]) {
      const keys = Object.keys(graphViz.communityColors);
      const hue = (keys.length * 137.5) % 360;
      graphViz.communityColors[n.community] = `hsl(${hue}, 65%, 55%)`;
    }
    return graphViz.communityColors[n.community];
  }
  return TYPE_COLORS[n.type] || '#888';
}

function updateLegend() {
  const el = document.getElementById('graph-legend');
  if (!el) return;
  if (graphViz.colorMode === 'community') {
    const comms = [...new Set(graphViz.nodes.map(n => n.community).filter(Boolean))];
    el.innerHTML = comms.slice(0,8).map(c =>
      `<div style="display:flex;align-items:center;gap:3px;margin-bottom:2px;"><div style="width:7px;height:7px;border-radius:50%;background:${graphViz.communityColors[c]||'#888'};"></div>${c.slice(0,6)}</div>`
    ).join('');
  } else {
    el.innerHTML = Object.entries(TYPE_COLORS).slice(0,7).map(([t,c]) =>
      `<div style="display:flex;align-items:center;gap:3px;margin-bottom:2px;"><div style="width:7px;height:7px;border-radius:50%;background:${c};"></div>${t}</div>`
    ).join('');
  }
}

// ─── V5: Export to PNG ───

function exportGraphPNG() {
  const canvas = graphViz.canvas;
  if (!canvas) return;
  const link = document.createElement('a');
  link.download = `omnigraph-${Date.now()}.png`;
  link.href = canvas.toDataURL('image/png');
  link.click();
  showToast('Graph exported as PNG');
}

// ─── V6: Expand/Collapse ───

async function expandNode(nodeId) {
  try {
    const r = await fetch(`${API}/graphrag/query/local`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ query: `neighbors of entity ${nodeId}`, user_principal: 'public' }),
    });
    const data = await r.json();
    const newNodes = [];
    if (data.evidence?.entities) {
      for (const e of data.evidence.entities) {
        const id = e.resolved_id || e.id || e.canonical_name;
        if (!graphViz.nodes.find(n => n.id === id)) {
          const parent = graphViz.nodes.find(n => n.id === nodeId);
          const newNode = {
            id, label: e.canonical_name || e.name || id.slice(0,8),
            type: e.entity_type || e.type || 'ENTITY',
            x: (parent?.x || 0) + (Math.random()-0.5)*100,
            y: (parent?.y || 0) + (Math.random()-0.5)*100,
            radius: 12,
          };
          graphViz.nodes.push(newNode);
          newNodes.push(id);
          // Add edge
          graphViz.edges.push({source: nodeId, target: id, sourceLabel: parent?.label||'', targetLabel: newNode.label, type: 'RELATED_TO', weight: 1});
        }
      }
    }
    graphViz.expansions.set(nodeId, new Set(newNodes));
    if (newNodes.length) {
      runForceLayout(80);
      showToast(`Expanded: +${newNodes.length} nodes`);
    } else {
      showToast('No new neighbors found');
    }
  } catch(e) { showToast('Expand failed: ' + e.message, 'error'); }
}

function collapseNode(nodeId) {
  const expanded = graphViz.expansions.get(nodeId);
  if (!expanded || expanded.size === 0) return;
  graphViz.nodes = graphViz.nodes.filter(n => !expanded.has(n.id));
  graphViz.edges = graphViz.edges.filter(e => !expanded.has(e.source) && !expanded.has(e.target));
  graphViz.expansions.delete(nodeId);
  drawGraph();
  showToast('Collapsed');
}

// ─── V8: Comments ───

async function addComment(nodeId) {
  const text = prompt('Add comment:');
  if (!text) return;
  try {
    await fetch(`${API}/v1/graph/comments`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ target_id: nodeId, target_type: 'entity', text, author: 'user' }),
    });
    graphViz.comments[nodeId] = (graphViz.comments[nodeId] || 0) + 1;
    drawGraph();
    showToast('Comment added');
  } catch { showToast('Comment API not available yet', 'error'); graphViz.comments[nodeId] = (graphViz.comments[nodeId] || 0) + 1; drawGraph(); }
}

// ─── Chat Tab (OpenCode Chat template) ───

function renderChatWelcome() {
  const el = document.getElementById('chat-messages');
  el.innerHTML = `
    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; gap:16px; padding:40px 20px; text-align:center;">
      <div style="font-size:24px; font-weight:700; color:var(--text); opacity:0.12;">OmniRAG Chat</div>
      <p style="color:var(--text-dim); font-size:14px; max-width:400px;">
        Ask questions about your ingested documents. Uses hybrid RAG + OmniGraph for answers with citations.
      </p>
    </div>
  `;
}

function chatAddMessage(role, content) {
  chatMessages.push({ role, content, time: Date.now() });
  renderChatMessages();
}

function renderChatMessages() {
  const el = document.getElementById('chat-messages');
  el.innerHTML = chatMessages.map(msg => {
    if (msg.role === 'user') {
      return `<div class="chat-msg-user"><div class="chat-msg-user-body"><div class="chat-msg-user-text">${escapeHtml(msg.content)}</div></div></div>`;
    }
    return `<div class="chat-msg-assistant"><div class="chat-msg-assistant-text">${msg.content}</div></div>`;
  }).join('');
  el.scrollTop = el.scrollHeight;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function chatHandleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    chatSend();
  }
}

async function chatSend() {
  const input = document.getElementById('chat-input');
  const query = input.value.trim();
  if (!query) return;
  input.value = '';
  input.style.height = 'auto';

  // Add user message
  chatAddMessage('user', query);

  // Add thinking indicator
  const el = document.getElementById('chat-messages');
  const thinkingId = 'thinking-' + Date.now();
  el.innerHTML += `<div class="chat-msg-assistant" id="${thinkingId}"><div class="chat-thinking"><div class="spinner"></div> Searching & generating...</div></div>`;
  el.scrollTop = el.scrollHeight;

  try {
    // Try hybrid search first
    const r = await fetch(`${API}/v1/search`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ query, top_k: 5 }),
    });
    const data = await r.json();

    // Remove thinking indicator
    const thinking = document.getElementById(thinkingId);
    if (thinking) thinking.remove();

    // Build assistant response
    let response = data.answer || 'No answer found.';
    if (data.citations?.length) {
      response += '<br><br><strong>Citations:</strong><br>';
      response += data.citations.map(c =>
        `<code>${c.doc_id?.slice(0,8)}:${c.chunk_id?.slice(0,8)}</code> ${c.snippet || ''}`
      ).join('<br>');
    }
    if (data.metadata) {
      response += `<br><br><span style="font-size:11px; color:var(--text-muted);">Mode: ${data.metadata.mode} · Retrieval: ${data.metadata.retrieval_latency_ms}ms · Generation: ${data.metadata.generation_latency_ms}ms</span>`;
    }

    chatAddMessage('assistant', response);
  } catch(e) {
    const thinking = document.getElementById(thinkingId);
    if (thinking) thinking.remove();
    chatAddMessage('assistant', `<span style="color:var(--error);">Error: ${e.message}</span>`);
  }
}

// ─── Adapters (interactive) ───

const ADAPTERS = [
  { id: 'file_loader', name: 'File Loader', category: 'Ingestion', icon: '📂', dep: null, test: null,
    desc: 'Load files from local filesystem (txt, pdf, docx, etc.)',
    params: [{ key: 'path', type: 'text', placeholder: './data', label: 'File path or glob' },
             { key: 'glob', type: 'text', placeholder: '*.pdf', label: 'File pattern' }] },
  { id: 'recursive_splitter', name: 'Recursive Splitter', category: 'Chunking', icon: '✂️', dep: null, test: null,
    desc: 'Split text by headings, paragraphs, or fixed size with overlap.',
    params: [{ key: 'chunk_size', type: 'number', placeholder: '512', label: 'Chunk size (tokens)' },
             { key: 'overlap', type: 'number', placeholder: '50', label: 'Overlap (tokens)' }] },
  { id: 'memory', name: 'In-Memory Store', category: 'Retrieval', icon: '💾', dep: null, test: 'memory',
    desc: 'In-memory vector store for development and testing.',
    params: [{ key: 'top_k', type: 'number', placeholder: '5', label: 'Top K results' }] },
  { id: 'huggingface', name: 'HuggingFace', category: 'Embedding', icon: '🤗', dep: 'sentence-transformers', test: 'huggingface',
    desc: 'Generate embeddings using sentence-transformers models.',
    params: [{ key: 'model', type: 'text', placeholder: 'BAAI/bge-large-en', label: 'Model name' }] },
  { id: 'qdrant', name: 'Qdrant', category: 'Vector DB', icon: '🔷', dep: 'qdrant-client', test: 'qdrant',
    desc: 'Production vector database for similarity search.',
    params: [{ key: 'collection', type: 'text', placeholder: 'chunks', label: 'Collection name' },
             { key: 'url', type: 'text', placeholder: 'http://localhost:6333', label: 'Qdrant URL' }] },
  { id: 'cross_encoder', name: 'Cross Encoder', category: 'Reranking', icon: '🎯', dep: 'sentence-transformers', test: null,
    desc: 'Rerank results using cross-encoder model for better relevance.',
    params: [{ key: 'model', type: 'text', placeholder: 'cross-encoder/ms-marco-MiniLM-L-6-v2', label: 'Model' }] },
  { id: 'openai_gen', name: 'OpenAI', category: 'Generation', icon: '🧠', dep: 'openai', test: 'openai',
    desc: 'Generate answers using OpenAI API (GPT-4, etc.).',
    params: [{ key: 'model', type: 'text', placeholder: 'gpt-4', label: 'Model' },
             { key: 'api_key', type: 'password', placeholder: 'sk-...', label: 'API Key' }] },
  { id: 'ollama_gen', name: 'Ollama', category: 'Generation', icon: '🦙', dep: null, test: 'ollama',
    desc: 'Generate answers using local Ollama server.',
    params: [{ key: 'model', type: 'text', placeholder: 'llama3', label: 'Model name' },
             { key: 'base_url', type: 'text', placeholder: 'http://localhost:11434', label: 'Ollama URL' }] },
];

const adapterStatus = {};

function getAdapterCards() {
  return ADAPTERS.map(a => {
    const status = adapterStatus[a.id] || 'unknown';
    const dotColor = status === 'ok' ? 'var(--success)' : status === 'error' ? 'var(--error)' : 'var(--text-muted)';
    return `
      <div class="card" style="padding:10px; margin:0; cursor:pointer; transition:border-color 150ms;"
           onclick="openAdapter('${a.id}')"
           onmouseover="this.style.borderColor='var(--accent)'"
           onmouseout="this.style.borderColor='var(--border)'">
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
          <span style="font-size:14px;">${a.icon}</span>
          <span style="font-size:12px; font-weight:500; color:var(--text);">${a.name}</span>
          <div style="width:6px; height:6px; border-radius:50%; background:${dotColor}; margin-left:auto;"></div>
        </div>
        <div style="font-size:10px; color:var(--text-dim);">${a.category}</div>
      </div>
    `;
  }).join('');
}

function openAdapter(id) {
  const a = ADAPTERS.find(x => x.id === id);
  if (!a) return;
  const body = document.getElementById('main-body');
  const status = adapterStatus[a.id] || 'unknown';

  body.innerHTML = `
    <div style="padding:0 0 12px;">
      <button onclick="renderHome()" style="display:flex; align-items:center; justify-content:center; width:24px; height:24px; background:none; border:none; color:var(--text-dim); cursor:pointer;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
      </button>
    </div>
    <div style="max-width:600px;">
      <div style="display:flex; align-items:center; gap:10px; margin-bottom:16px;">
        <span style="font-size:24px;">${a.icon}</span>
        <div>
          <h2 style="font-size:18px; font-weight:600; color:var(--text);">${a.name}</h2>
          <span style="font-size:12px; color:var(--text-dim);">${a.category}${a.dep ? ' · requires: ' + a.dep : ' · no dependencies'}</span>
        </div>
      </div>
      <p style="color:var(--text-dim); margin-bottom:16px;">${a.desc}</p>

      <div class="card">
        <div class="card-title">Configuration</div>
        <div class="card-body">
          <div style="display:flex; flex-direction:column; gap:10px;">
            ${a.params.map(p => `
              <div>
                <label style="font-size:11px; color:var(--text-dim); display:block; margin-bottom:3px;">${p.label}</label>
                <input class="input" type="${p.type}" id="adapter-${a.id}-${p.key}" placeholder="${p.placeholder}" />
              </div>
            `).join('')}
          </div>
          <div style="display:flex; gap:8px; margin-top:12px;">
            <button class="btn btn-primary" onclick="saveAdapterConfig('${a.id}')">Save</button>
            ${a.test ? `<button class="btn" onclick="testAdapter('${a.id}')">Test Connection</button>` : ''}
          </div>
        </div>
      </div>

      <div class="card" style="margin-top:12px;">
        <div class="card-title">Status</div>
        <div class="card-body" id="adapter-status-${a.id}">
          <span style="color:var(--text-dim);">Not tested yet</span>
        </div>
      </div>
    </div>
  `;
}

function saveAdapterConfig(id) {
  const a = ADAPTERS.find(x => x.id === id);
  if (!a) return;
  const config = {};
  a.params.forEach(p => {
    const el = document.getElementById(`adapter-${id}-${p.key}`);
    if (el && el.value) config[p.key] = el.value;
  });
  localStorage.setItem(`adapter_config_${id}`, JSON.stringify(config));
  showToast(`${a.name} config saved`);
}

async function testAdapter(id) {
  const a = ADAPTERS.find(x => x.id === id);
  if (!a) return;
  const statusEl = document.getElementById(`adapter-status-${id}`);
  statusEl.innerHTML = '<div style="display:flex;align-items:center;gap:6px;"><div class="spinner"></div> Testing...</div>';

  const config = {};
  a.params.forEach(p => {
    const el = document.getElementById(`adapter-${id}-${p.key}`);
    if (el && el.value) config[p.key] = el.value;
  });

  try {
    let ok = false;
    let msg = '';

    if (id === 'qdrant') {
      const url = config.url || 'http://localhost:6333';
      const r = await fetch(`${url}/healthz`).catch(() => null);
      ok = r && r.ok;
      msg = ok ? `Qdrant reachable at ${url}` : `Cannot reach ${url}`;
    } else if (id === 'ollama') {
      const url = config.base_url || 'http://localhost:11434';
      const r = await fetch(`${url}/api/tags`).catch(() => null);
      ok = r && r.ok;
      if (ok) {
        const data = await r.json();
        const models = data.models?.map(m => m.name) || [];
        msg = `Ollama running. Models: ${models.join(', ') || 'none'}`;
      } else {
        msg = `Cannot reach ${url}`;
      }
    } else if (id === 'openai') {
      const key = config.api_key || '';
      ok = key.startsWith('sk-') && key.length > 20;
      msg = ok ? 'API key format valid' : 'Invalid API key format (should start with sk-)';
    } else if (id === 'huggingface') {
      msg = 'HuggingFace model will be downloaded on first use';
      ok = true;
    } else if (id === 'memory') {
      msg = 'In-memory store is always available';
      ok = true;
    } else {
      msg = 'No test available for this adapter';
      ok = true;
    }

    adapterStatus[id] = ok ? 'ok' : 'error';
    statusEl.innerHTML = `
      <div style="display:flex; align-items:center; gap:6px;">
        <div style="width:8px; height:8px; border-radius:50%; background:${ok ? 'var(--success)' : 'var(--error)'};"></div>
        <span style="color:${ok ? 'var(--success)' : 'var(--error)'};">${ok ? 'Connected' : 'Failed'}</span>
      </div>
      <p style="font-size:12px; color:var(--text-dim); margin-top:4px;">${msg}</p>
    `;
  } catch(e) {
    adapterStatus[id] = 'error';
    statusEl.innerHTML = `<span style="color:var(--error);">Error: ${e.message}</span>`;
  }
}

// ─── Fetch URL via Browser (bypasses CDN blocks) ───

async function fetchUrlViaBrowser() {
  const sourceInput = document.getElementById('intake-source');
  let url = sourceInput.value.trim();

  if (!url) {
    url = prompt('Enter URL to fetch (PDF, HTML, etc.):');
    if (!url) return;
    sourceInput.value = url;
  }

  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    showToast('Enter a valid URL starting with http:// or https://', 'error');
    return;
  }

  const result = document.getElementById('intake-result');
  result.innerHTML = '<div style="display:flex;align-items:center;gap:8px;"><div class="spinner"></div> Fetching via browser...</div>';

  try {
    // Download via browser fetch (has full TLS + cookies — bypasses CDN blocks)
    const response = await fetch(url, { mode: 'cors' }).catch(() => null);

    // If CORS fails, try no-cors (opaque response — won't give us content)
    // Fall back to server-side fetch
    if (!response || !response.ok) {
      result.innerHTML = '<div style="display:flex;align-items:center;gap:8px;"><div class="spinner"></div> Browser fetch blocked by CORS. Trying server-side...</div>';
      // Fall back to server intake
      const r = await fetch(`${API}/intake`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ source: url, config: {} }),
      });
      const data = await r.json();
      renderIntakeResult(data);
      return;
    }

    const blob = await response.blob();
    const filename = url.split('/').pop().split('?')[0] || 'download';

    // Upload the blob to server
    const formData = new FormData();
    formData.append('file', blob, filename);

    const uploadResp = await fetch(`${API}/intake/upload`, { method: 'POST', body: formData });
    const data = await uploadResp.json();
    renderIntakeResult(data);

  } catch(e) {
    // Final fallback: server-side fetch
    try {
      result.innerHTML = '<div style="display:flex;align-items:center;gap:8px;"><div class="spinner"></div> Trying server-side fetch...</div>';
      const r = await fetch(`${API}/intake`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ source: url, config: {} }),
      });
      const data = await r.json();
      renderIntakeResult(data);
    } catch(e2) {
      result.innerHTML = `<div style="color:var(--error); font-size:13px;">Failed: ${e2.message}. Try downloading the file manually and use Browse files.</div>`;
    }
  }
}

function renderIntakeResult(data) {
  const result = document.getElementById('intake-result');
  const stateColor = data.state === 'active' ? 'var(--success)' : data.state === 'failed' ? 'var(--error)' : 'var(--accent)';
  result.innerHTML = `
    <div class="card" style="margin:8px 0 0; padding:12px;">
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
        <span style="font-size:13px; font-weight:500; color:var(--text);">Job ${data.id}</span>
        <span class="badge" style="background:${stateColor}20; color:${stateColor};">${data.state}</span>
      </div>
      <div style="font-size:12px; color:var(--text-dim); display:flex; gap:16px; flex-wrap:wrap;">
        <span>Files: ${data.files_found || 0}</span>
        <span>Loaded: ${data.files_loaded || 0}</span>
        <span>Docs: ${data.documents_created || 0}</span>
        <span>Chunks: ${data.chunks_created || 0}</span>
      </div>
      ${data.errors?.length ? `<div style="font-size:11px; color:var(--error); margin-top:6px;">${data.errors.slice(0,3).join('<br>')}</div>` : ''}
    </div>
  `;
  if (data.state === 'active') showToast(`Ingested: ${data.documents_created} docs, ${data.chunks_created} chunks`);
}

// ─── File Upload ───

async function handleFilePick(input) {
  const files = input.files;
  if (!files || files.length === 0) return;

  const result = document.getElementById('intake-result');
  result.innerHTML = `<div style="display:flex;align-items:center;gap:8px;"><div class="spinner"></div> Uploading ${files.length} file(s)...</div>`;

  let totalDocs = 0;
  let totalChunks = 0;
  let errors = [];

  for (const file of files) {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const r = await fetch(`${API}/intake/upload`, { method: 'POST', body: formData });
      const data = await r.json();

      if (data.state === 'active') {
        totalDocs += data.documents_created || 0;
        totalChunks += data.chunks_created || 0;
      } else {
        errors.push(`${file.name}: ${data.errors?.[0] || data.state}`);
      }
    } catch(e) {
      errors.push(`${file.name}: ${e.message}`);
    }
  }

  result.innerHTML = `
    <div class="card" style="margin:8px 0 0; padding:12px;">
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
        <span style="font-size:13px; font-weight:500; color:var(--text);">${files.length} file(s) uploaded</span>
        <span class="badge badge-${errors.length ? 'warning' : 'success'}">${errors.length ? 'partial' : 'success'}</span>
      </div>
      <div style="font-size:12px; color:var(--text-dim); display:flex; gap:16px;">
        <span>Docs: ${totalDocs}</span>
        <span>Chunks: ${totalChunks}</span>
      </div>
      ${errors.length ? `<div style="font-size:11px; color:var(--error); margin-top:6px;">${errors.join('<br>')}</div>` : ''}
    </div>
  `;

  if (totalDocs > 0) showToast(`Ingested: ${totalDocs} docs, ${totalChunks} chunks`);
  input.value = '';
}

// ─── Intake Gate UI ───

async function runIntake() {
  const source = document.getElementById('intake-source').value.trim();
  if (!source) { showToast('Source URI required', 'error'); return; }
  const result = document.getElementById('intake-result');
  result.innerHTML = '<div style="display:flex;align-items:center;gap:8px;"><div class="spinner"></div> Ingesting...</div>';
  try {
    const r = await fetch(`${API}/intake`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ source, config: {} }),
    });
    const data = await r.json();
    const stateColor = data.state === 'active' ? 'var(--success)' : data.state === 'failed' ? 'var(--error)' : 'var(--accent)';
    result.innerHTML = `
      <div class="card" style="margin:8px 0 0; padding:12px;">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
          <span style="font-size:13px; font-weight:500; color:var(--text);">Job ${data.id}</span>
          <span class="badge" style="background:${stateColor}20; color:${stateColor};">${data.state}</span>
        </div>
        <div style="font-size:12px; color:var(--text-dim); display:flex; gap:16px; flex-wrap:wrap;">
          <span>Files: ${data.files_found || 0}</span>
          <span>Loaded: ${data.files_loaded || 0}</span>
          <span>Docs: ${data.documents_created || 0}</span>
          <span>Chunks: ${data.chunks_created || 0}</span>
        </div>
        ${data.errors?.length ? `<div style="font-size:11px; color:var(--error); margin-top:6px;">${data.errors.slice(0,3).join('<br>')}</div>` : ''}
      </div>
    `;
    if (data.state === 'active') showToast(`Ingested: ${data.documents_created} docs, ${data.chunks_created} chunks`);
  } catch(e) {
    result.innerHTML = `<div style="color:var(--error); font-size:13px; margin-top:4px;">${e.message}</div>`;
  }
}

async function showIntakeJobs() {
  const body = document.getElementById('main-body');
  body.innerHTML = '<div style="display:flex;align-items:center;gap:8px;"><div class="spinner"></div> Loading jobs...</div>';
  try {
    const jobs = await fetch(`${API}/intake`).then(r => r.json());
    const backBar = `
      <div style="padding:0 0 12px;">
        <button onclick="renderHome()" style="display:flex; align-items:center; justify-content:center; width:24px; height:24px; background:none; border:none; color:var(--text-dim); cursor:pointer;">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
        </button>
      </div>`;
    if (!jobs.length) {
      body.innerHTML = backBar + '<div class="empty-state"><p>No intake jobs yet. Ingest a source to get started.</p></div>';
      return;
    }
    body.innerHTML = backBar + `
      <div style="max-width:700px;">
        <div class="table-wrap">
          <table>
            <thead><tr><th>Job ID</th><th>State</th><th>Source</th><th>Docs</th><th>Chunks</th></tr></thead>
            <tbody>
              ${jobs.map(j => `
                <tr onclick="viewIntakeJob('${j.id}')" style="cursor:pointer;">
                  <td><code>${j.id}</code></td>
                  <td><span class="badge badge-${j.state === 'active' ? 'success' : j.state === 'failed' ? 'error' : 'info'}">${j.state}</span></td>
                  <td style="max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${j.source || '—'}</td>
                  <td>${j.documents_created || 0}</td>
                  <td>${j.chunks_created || 0}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } catch(e) {
    body.innerHTML = `<div class="card"><div class="card-title" style="color:var(--error)">Error</div><div class="card-body"><code>${e.message}</code></div></div>`;
  }
}

async function viewIntakeJob(jobId) {
  const body = document.getElementById('main-body');
  body.innerHTML = '<div style="display:flex;align-items:center;gap:8px;"><div class="spinner"></div> Loading...</div>';
  try {
    const data = await fetch(`${API}/intake/${jobId}`).then(r => r.json());
    body.innerHTML = `
      <div style="padding:0 0 12px;">
        <button onclick="showIntakeJobs()" style="display:flex; align-items:center; justify-content:center; width:24px; height:24px; background:none; border:none; color:var(--text-dim); cursor:pointer;">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
        </button>
      </div>
      <div style="max-width:700px;">
        </div>
        <div class="card">
          <div class="card-title">Status: <span class="badge badge-${data.state === 'active' ? 'success' : 'info'}">${data.state}</span></div>
          <div class="card-body">
            <p>Source: <code>${data.source || '—'}</code></p>
            <p>Files found: ${data.files_found} · Loaded: ${data.files_loaded} · Docs: ${data.documents_created} · Chunks: ${data.chunks_created}</p>
            ${data.errors?.length ? `<p style="color:var(--error);">Errors: ${data.errors.join(', ')}</p>` : ''}
          </div>
        </div>
        ${data.documents?.length ? `
          <div class="card">
            <div class="card-title">Documents (${data.documents.length})</div>
            <div class="card-body">
              ${data.documents.map(d => `
                <div style="padding:6px 0; border-bottom:1px solid var(--border-weak);">
                  <span class="badge badge-info">${d.semantic_type}</span>
                  <span style="margin-left:8px; color:var(--text);">${d.title || d.source_object_ref?.slice(0,12) || '—'}</span>
                  <span style="color:var(--text-muted); font-size:11px; margin-left:8px;">${d.body_length || 0} chars</span>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}
        ${data.chunks_sample?.length ? `
          <div class="card">
            <div class="card-title">Chunks (showing ${data.chunks_sample.length} of ${data.chunks_total})</div>
            <div class="card-body">
              ${data.chunks_sample.map(c => `
                <div style="padding:6px 0; border-bottom:1px solid var(--border-weak); font-size:12px;">
                  <code style="font-size:10px;">${c.chunk_type || 'chunk'}</code>
                  <span style="color:var(--text-dim); margin-left:6px;">${c.text_preview}</span>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}
      </div>
    `;
  } catch(e) {
    body.innerHTML = `<div class="card"><div class="card-title" style="color:var(--error)">Error</div><div class="card-body"><code>${e.message}</code></div></div>`;
  }
}

// ─── Init ───
checkHealth();
setInterval(checkHealth, 15000);
loadPipelines();
