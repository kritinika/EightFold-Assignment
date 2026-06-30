"""
Minimal Flask web UI for the Multi-Source Candidate Data Transformer.
Run: python3 app.py
Open: http://localhost:5000
"""
import json
import os
import tempfile
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

from transformer.pipeline import Pipeline

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload limit

SAMPLE_DIR = Path(__file__).parent / "sample_inputs"

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Candidate Data Transformer</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #0F1117;
  --surface: #1A1D27;
  --surface2: #22263A;
  --border: #2E3348;
  --accent: #3B82F6;
  --accent-dim: #1D3461;
  --text: #E2E8F0;
  --text2: #94A3B8;
  --text3: #64748B;
  --green: #10B981;
  --amber: #F59E0B;
  --red: #EF4444;
  --mono: 'JetBrains Mono', 'Fira Mono', 'SF Mono', Consolas, monospace;
  --sans: Inter, -apple-system, BlinkMacSystemFont, sans-serif;
}
html { font-size: 14px; background: var(--bg); color: var(--text); }
body { font-family: var(--sans); min-height: 100vh; display: flex; flex-direction: column; }

/* ── Header ── */
header {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 28px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 10;
}
.logo {
  width: 32px; height: 32px; border-radius: 8px;
  background: var(--accent); display: flex; align-items: center; justify-content: center;
  font-size: 16px; flex-shrink: 0;
}
header h1 { font-size: 0.95rem; font-weight: 700; letter-spacing: -0.02em; }
header span { font-size: 0.75rem; color: var(--text3); margin-left: 8px; }
.header-tag {
  margin-left: auto;
  background: var(--accent-dim); color: var(--accent);
  font-size: 0.65rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
  padding: 3px 10px; border-radius: 20px;
}

/* ── Layout ── */
.layout { display: flex; flex: 1; height: calc(100vh - 57px); overflow: hidden; }

/* ── Left panel ── */
.panel-left {
  width: 340px; flex-shrink: 0;
  background: var(--surface);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  display: flex; flex-direction: column;
}
.panel-section { padding: 18px 20px; border-bottom: 1px solid var(--border); }
.panel-section:last-child { border-bottom: none; }
.section-label {
  font-size: 0.62rem; font-weight: 700; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--text3); margin-bottom: 12px;
}

/* ── File inputs ── */
.file-row { margin-bottom: 10px; }
.file-row label {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 0.78rem; color: var(--text2); margin-bottom: 5px;
}
.source-badge {
  font-size: 0.58rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
  padding: 2px 6px; border-radius: 3px;
}
.sb-struct { background: #1C3B2E; color: var(--green); }
.sb-unstruct { background: #2D1F0A; color: var(--amber); }

input[type="file"], input[type="text"] {
  width: 100%;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-family: var(--sans);
  font-size: 0.78rem;
  padding: 7px 10px;
  outline: none;
  transition: border-color 0.15s;
}
input[type="file"]:hover, input[type="text"]:focus { border-color: var(--accent); }
input[type="file"] { cursor: pointer; }

/* GitHub URL add button */
.url-row { display: flex; gap: 6px; }
.url-row input { flex: 1; }
.btn-sm {
  background: var(--surface2); border: 1px solid var(--border);
  color: var(--text); font-size: 0.75rem; font-weight: 600;
  padding: 6px 12px; border-radius: 6px; cursor: pointer;
  transition: background 0.15s, border-color 0.15s; white-space: nowrap;
}
.btn-sm:hover { background: var(--accent-dim); border-color: var(--accent); color: var(--accent); }
#github-list { margin-top: 6px; display: flex; flex-direction: column; gap: 4px; }
.github-tag {
  display: flex; align-items: center; justify-content: space-between;
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 5px; padding: 5px 10px;
  font-size: 0.72rem; color: var(--text2); font-family: var(--mono);
}
.github-tag button {
  background: none; border: none; color: var(--text3); cursor: pointer; font-size: 0.9rem; padding: 0 2px;
}
.github-tag button:hover { color: var(--red); }

/* Config textarea */
textarea {
  width: 100%; resize: vertical;
  background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
  color: var(--text); font-family: var(--mono); font-size: 0.72rem;
  padding: 8px 10px; line-height: 1.6; outline: none; min-height: 130px;
  transition: border-color 0.15s;
}
textarea:focus { border-color: var(--accent); }

/* Run button */
.btn-run {
  width: 100%; padding: 11px;
  background: var(--accent); color: white;
  font-family: var(--sans); font-size: 0.85rem; font-weight: 700;
  border: none; border-radius: 8px; cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
  letter-spacing: -0.01em;
}
.btn-run:hover { opacity: 0.9; }
.btn-run:active { transform: scale(0.99); }
.btn-run:disabled { opacity: 0.4; cursor: not-allowed; }

/* Sample load */
.sample-link {
  display: inline-block; margin-top: 8px;
  font-size: 0.72rem; color: var(--accent); cursor: pointer;
  text-decoration: underline; text-underline-offset: 2px;
}
.sample-link:hover { opacity: 0.8; }

/* ── Right panel ── */
.panel-right {
  flex: 1; overflow-y: auto; display: flex; flex-direction: column;
}

/* Stats bar */
.stats-bar {
  display: flex; align-items: center; gap: 20px;
  padding: 12px 24px;
  background: var(--surface); border-bottom: 1px solid var(--border);
  font-size: 0.75rem; color: var(--text2); flex-shrink: 0;
}
.stat { display: flex; align-items: center; gap: 6px; }
.stat-num { font-weight: 700; color: var(--text); font-variant-numeric: tabular-nums; }
.stat-dot { width: 6px; height: 6px; border-radius: 50%; }
.dot-green { background: var(--green); }
.dot-amber { background: var(--amber); }

/* Empty state */
.empty {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 12px; color: var(--text3); padding: 40px;
}
.empty-icon { font-size: 3rem; opacity: 0.3; }
.empty h2 { font-size: 0.95rem; font-weight: 600; color: var(--text2); }
.empty p { font-size: 0.78rem; text-align: center; max-width: 320px; line-height: 1.6; }

/* Spinner */
.spinner-wrap {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 12px;
  color: var(--text2); font-size: 0.85rem;
}
@keyframes spin { to { transform: rotate(360deg); } }
.spinner {
  width: 20px; height: 20px; border-radius: 50%;
  border: 2px solid var(--border); border-top-color: var(--accent);
  animation: spin 0.8s linear infinite;
}

/* Profiles grid */
.profiles { padding: 20px 24px; display: flex; flex-direction: column; gap: 16px; }

/* Profile card */
.profile-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; overflow: hidden;
}
.profile-head {
  display: flex; align-items: flex-start; gap: 14px;
  padding: 16px 18px; border-bottom: 1px solid var(--border);
  cursor: pointer; user-select: none;
}
.avatar {
  width: 38px; height: 38px; border-radius: 50%; flex-shrink: 0;
  background: var(--accent-dim); display: flex; align-items: center; justify-content: center;
  font-size: 0.85rem; font-weight: 700; color: var(--accent);
}
.profile-main { flex: 1; min-width: 0; }
.profile-name { font-size: 0.95rem; font-weight: 700; letter-spacing: -0.02em; }
.profile-sub { font-size: 0.75rem; color: var(--text2); margin-top: 2px; }
.profile-meta { display: flex; align-items: center; gap: 8px; margin-top: 6px; flex-wrap: wrap; }
.meta-chip {
  font-size: 0.65rem; font-weight: 600; letter-spacing: 0.04em;
  padding: 2px 8px; border-radius: 20px; border: 1px solid var(--border);
  color: var(--text2);
}

/* Confidence bar */
.conf-wrap { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.conf-label { font-size: 0.65rem; color: var(--text3); text-align: right; }
.conf-num { font-size: 1.1rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.conf-high { color: var(--green); }
.conf-mid { color: var(--amber); }
.conf-low { color: var(--red); }
.conf-bar-track { width: 64px; height: 4px; background: var(--border); border-radius: 2px; }
.conf-bar-fill { height: 100%; border-radius: 2px; transition: width 0.4s ease; }
.fill-high { background: var(--green); }
.fill-mid { background: var(--amber); }
.fill-low { background: var(--red); }

/* Profile body (expandable) */
.profile-body { padding: 16px 18px; display: none; }
.profile-body.open { display: block; }

.field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px; }
.field-item {}
.field-label { font-size: 0.62rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text3); margin-bottom: 3px; }
.field-value { font-size: 0.8rem; color: var(--text); word-break: break-word; }
.field-value.mono { font-family: var(--mono); font-size: 0.73rem; color: var(--text2); }
.field-null { color: var(--text3); font-style: italic; font-size: 0.75rem; }

/* Skills pills */
.skills-wrap { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 2px; }
.skill-pill {
  font-size: 0.68rem; font-weight: 600;
  padding: 3px 9px; border-radius: 20px;
  background: var(--surface2); border: 1px solid var(--border); color: var(--text2);
}

/* Experience list */
.exp-list { display: flex; flex-direction: column; gap: 8px; margin-top: 2px; }
.exp-item {
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 6px; padding: 9px 12px;
}
.exp-title { font-size: 0.8rem; font-weight: 600; }
.exp-company { font-size: 0.73rem; color: var(--text2); }
.exp-dates { font-size: 0.65rem; color: var(--text3); margin-top: 2px; font-family: var(--mono); }

/* Provenance section */
.prov-toggle {
  font-size: 0.7rem; color: var(--accent); cursor: pointer;
  display: inline-flex; align-items: center; gap: 4px; margin-bottom: 8px;
}
.prov-table { font-size: 0.72rem; font-family: var(--mono); }
.prov-row {
  display: grid; grid-template-columns: 120px 80px 1fr;
  gap: 8px; padding: 5px 0; border-bottom: 1px solid var(--border);
  color: var(--text2);
}
.prov-row:last-child { border-bottom: none; }
.prov-field { color: var(--text); font-weight: 600; }
.src-tag {
  font-size: 0.6rem; font-weight: 700; letter-spacing: 0.04em;
  padding: 1px 6px; border-radius: 3px; text-transform: uppercase;
}
.src-csv { background: #1C3B2E; color: var(--green); }
.src-ats_json { background: #1D3461; color: #93C5FD; }
.src-github { background: #2D1F0A; color: var(--amber); }
.src-notes { background: #2D1A1A; color: #FCA5A5; }

/* Raw JSON toggle */
.json-toggle {
  font-size: 0.7rem; color: var(--text3); cursor: pointer;
  display: inline-flex; align-items: center; gap: 4px; margin-top: 12px;
}
.json-toggle:hover { color: var(--text2); }
.raw-json {
  margin-top: 8px; background: #0B0D14;
  border: 1px solid var(--border); border-radius: 6px;
  padding: 12px; font-family: var(--mono); font-size: 0.7rem;
  line-height: 1.6; color: var(--text2); overflow-x: auto; display: none;
  max-height: 320px; overflow-y: auto;
}
.raw-json.open { display: block; }

/* Error banner */
.error-banner {
  margin: 20px 24px;
  background: #2D1A1A; border: 1px solid #7F1D1D;
  border-radius: 8px; padding: 14px 18px;
  font-size: 0.8rem; color: #FCA5A5;
}
</style>
</head>
<body>

<header>
  <div class="logo">⚡</div>
  <h1>Candidate Data Transformer</h1>
  <span>multi-source pipeline</span>
  <div class="header-tag">localhost</div>
</header>

<div class="layout">
  <!-- Left: inputs -->
  <div class="panel-left">

    <div class="panel-section">
      <div class="section-label">Structured Sources</div>

      <div class="file-row">
        <label>
          Recruiter CSV
          <span class="source-badge sb-struct">structured</span>
        </label>
        <input type="file" id="csv-file" accept=".csv">
      </div>

      <div class="file-row">
        <label>
          ATS JSON Blob
          <span class="source-badge sb-struct">structured</span>
        </label>
        <input type="file" id="ats-file" accept=".json">
      </div>
    </div>

    <div class="panel-section">
      <div class="section-label">Unstructured Sources</div>

      <div class="file-row">
        <label>
          Recruiter Notes (.txt)
          <span class="source-badge sb-unstruct">unstructured</span>
        </label>
        <input type="file" id="notes-file" accept=".txt" multiple>
      </div>

      <div class="file-row" style="margin-top:12px">
        <label>GitHub Profile URLs <span class="source-badge sb-unstruct">unstructured</span></label>
        <div class="url-row">
          <input type="text" id="github-input" placeholder="https://github.com/username">
          <button class="btn-sm" onclick="addGithub()">Add</button>
        </div>
        <div id="github-list"></div>
      </div>
    </div>

    <div class="panel-section">
      <div class="section-label">Output Config <span style="font-weight:400;text-transform:none;letter-spacing:0;color:var(--text3)">(optional)</span></div>
      <textarea id="config-input" placeholder='{
  "fields": [...],
  "include_confidence": true,
  "on_missing": "null"
}'></textarea>
      <span class="sample-link" onclick="loadSampleConfig()">← load example config</span>
    </div>

    <div class="panel-section">
      <button class="btn-run" id="run-btn" onclick="runPipeline()">▶ Run Pipeline</button>
      <span class="sample-link" onclick="loadSampleInputs()">← load sample inputs</span>
    </div>

  </div>

  <!-- Right: output -->
  <div class="panel-right" id="right-panel">
    <div class="empty" id="empty-state">
      <div class="empty-icon">🗂</div>
      <h2>No profiles yet</h2>
      <p>Upload at least one structured source (CSV or ATS JSON) and one unstructured source (notes or GitHub URL), then click Run.</p>
    </div>
  </div>
</div>

<script>
const githubUrls = [];

function addGithub() {
  const inp = document.getElementById('github-input');
  const url = inp.value.trim();
  if (!url || githubUrls.includes(url)) return;
  githubUrls.push(url);
  renderGithubList();
  inp.value = '';
}

document.getElementById('github-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') addGithub();
});

function renderGithubList() {
  const list = document.getElementById('github-list');
  list.innerHTML = githubUrls.map((u, i) => `
    <div class="github-tag">
      <span>${u}</span>
      <button onclick="removeGithub(${i})" title="Remove">×</button>
    </div>`).join('');
}

function removeGithub(i) {
  githubUrls.splice(i, 1);
  renderGithubList();
}

function loadSampleConfig() {
  document.getElementById('config-input').value = JSON.stringify({
    fields: [
      { path: "full_name", type: "string", required: true },
      { path: "primary_email", from: "emails[0]", type: "string", required: true },
      { path: "phone", from: "phones[0]", normalize: "E164" },
      { path: "linkedin", from: "links.linkedin" },
      { path: "headline", type: "string" },
      { path: "years_experience", type: "number" },
      { path: "skills", from: "skills[].name", type: "string[]" },
      { path: "location_country", from: "location.country" }
    ],
    include_confidence: true,
    include_provenance: true,
    on_missing: "null"
  }, null, 2);
}

function loadSampleInputs() {
  fetch('/load_samples').then(r => r.json()).then(data => {
    if (data.ok) {
      document.getElementById('run-btn').textContent = '▶ Run Pipeline (sample inputs loaded)';
      runPipeline(true);
    }
  });
}

async function runPipeline(useSamples = false) {
  const right = document.getElementById('right-panel');
  right.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div><span>Running pipeline…</span></div>';

  const btn = document.getElementById('run-btn');
  btn.disabled = true;
  btn.textContent = 'Running…';

  try {
    const fd = new FormData();

    if (!useSamples) {
      const csv = document.getElementById('csv-file').files[0];
      const ats = document.getElementById('ats-file').files[0];
      const notes = document.getElementById('notes-file').files;
      if (csv) fd.append('csv', csv);
      if (ats) fd.append('ats_json', ats);
      for (const f of notes) fd.append('notes', f);
    } else {
      fd.append('use_samples', '1');
    }

    githubUrls.forEach(u => fd.append('github', u));

    const configText = document.getElementById('config-input').value.trim();
    if (configText) fd.append('config', configText);

    const resp = await fetch('/run', { method: 'POST', body: fd });
    const data = await resp.json();

    if (data.error) {
      right.innerHTML = `<div class="error-banner">⚠ ${data.error}</div>`;
      return;
    }

    renderProfiles(data.profiles, data.sources_used);
  } catch (e) {
    right.innerHTML = `<div class="error-banner">⚠ ${e.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '▶ Run Pipeline';
  }
}

function renderProfiles(profiles, sourcesUsed) {
  const right = document.getElementById('right-panel');

  if (!profiles || profiles.length === 0) {
    right.innerHTML = '<div class="error-banner">No profiles found. Check your inputs.</div>';
    return;
  }

  const avgConf = (profiles.reduce((s, p) => s + (p.overall_confidence || 0), 0) / profiles.length).toFixed(2);
  const sources = (sourcesUsed || []).join(', ') || '—';

  let html = `
    <div class="stats-bar">
      <div class="stat"><span class="stat-dot dot-green"></span><span class="stat-num">${profiles.length}</span> candidate${profiles.length !== 1 ? 's' : ''}</div>
      <div class="stat"><span class="stat-dot dot-amber"></span>avg confidence <span class="stat-num">${avgConf}</span></div>
      <div class="stat" style="margin-left:auto; color: var(--text3)">sources: ${sources}</div>
    </div>
    <div class="profiles">`;

  profiles.forEach((p, i) => {
    const name = p.full_name || p.candidate_id || 'Unknown';
    const initials = name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
    const email = (p.emails || [])[0] || p.primary_email || '—';
    const headline = p.headline || '—';
    const conf = p.overall_confidence;
    const confPct = conf != null ? Math.round(conf * 100) : null;
    const confClass = confPct >= 80 ? 'conf-high' : confPct >= 60 ? 'conf-mid' : 'conf-low';
    const fillClass = confPct >= 80 ? 'fill-high' : confPct >= 60 ? 'fill-mid' : 'fill-low';

    // Source chips
    const sourcesUsedHere = (p._sources_used || []).map(s =>
      `<span class="meta-chip">${s}</span>`).join('');

    html += `
    <div class="profile-card">
      <div class="profile-head" onclick="toggleCard(${i})">
        <div class="avatar">${initials}</div>
        <div class="profile-main">
          <div class="profile-name">${name}</div>
          <div class="profile-sub">${email}</div>
          <div class="profile-meta">${sourcesUsedHere}</div>
        </div>
        ${confPct != null ? `
        <div class="conf-wrap">
          <div>
            <div class="conf-label">confidence</div>
            <div class="conf-bar-track"><div class="conf-bar-fill ${fillClass}" style="width:${confPct}%"></div></div>
          </div>
          <div class="conf-num ${confClass}">${(conf).toFixed(2)}</div>
        </div>` : ''}
      </div>
      <div class="profile-body" id="body-${i}">
        ${renderProfileBody(p)}
      </div>
    </div>`;
  });

  html += '</div>';
  right.innerHTML = html;
}

function renderProfileBody(p) {
  let html = '<div class="field-grid">';

  // Resolve a field from multiple possible key names (canonical + projected aliases)
  function pick(...keys) {
    for (const k of keys) {
      const v = k.split('.').reduce((o, part) => (o && o[part] != null ? o[part] : null), p);
      if (v != null && v !== '' && !(Array.isArray(v) && v.length === 0)) return v;
    }
    return null;
  }

  // Emails: canonical p.emails[] OR projected p.primary_email / p.email
  const emailsRaw = pick('emails');
  const emailStr = Array.isArray(emailsRaw)
    ? emailsRaw.join(', ')
    : (pick('primary_email', 'email') || null);

  // Phones: canonical p.phones[] OR projected p.phone
  const phonesRaw = pick('phones');
  const phoneStr = Array.isArray(phonesRaw)
    ? phonesRaw.join(', ')
    : (pick('phone') || null);

  // Location: canonical p.location object OR projected p.location_country / p.location_city
  const locObj = pick('location');
  const locStr = locObj && typeof locObj === 'object'
    ? [locObj.city, locObj.region, locObj.country].filter(Boolean).join(', ') || null
    : (pick('location_country', 'location_city') || null);

  // Links: canonical p.links.linkedin OR projected p.linkedin
  const linkedin = pick('links.linkedin', 'linkedin');
  const github   = pick('links.github',   'github');

  // Years exp
  const yoe = pick('years_experience');

  // Candidate ID
  const cid = pick('candidate_id');

  const fields = [
    ['Emails',       emailStr],
    ['Phone',        phoneStr],
    ['Location',     locStr],
    ['LinkedIn',     linkedin],
    ['GitHub',       github],
    ['Years Exp.',   yoe != null ? `${yoe} yrs` : null],
    ['Candidate ID', cid],
  ];

  fields.forEach(([label, val]) => {
    html += `<div class="field-item">
      <div class="field-label">${label}</div>
      <div class="field-value ${label === 'Candidate ID' ? 'mono' : ''}">${val != null ? val : '<span class="field-null">null</span>'}</div>
    </div>`;
  });
  html += '</div>';

  // Skills
  const skills = p.skills || [];
  const skillNames = Array.isArray(skills)
    ? skills.map(s => typeof s === 'object' ? s.name : s).filter(Boolean)
    : [];
  if (skillNames.length) {
    html += `<div class="field-label" style="margin-bottom:6px">Skills</div>
    <div class="skills-wrap">${skillNames.map(s => `<span class="skill-pill">${s}</span>`).join('')}</div>`;
  }

  // Experience
  const exp = p.experience || [];
  if (exp.length) {
    html += `<div class="field-label" style="margin: 14px 0 6px">Experience</div>
    <div class="exp-list">`;
    exp.forEach(e => {
      const dates = [e.start, e.end || 'Present'].filter(Boolean).join(' → ');
      const duration = e.years != null ? `${e.years} yr${e.years !== 1 ? 's' : ''}` : null;
      const dateStr = dates || duration || '—';
      html += `<div class="exp-item">
        <div class="exp-title">${e.title || '—'}</div>
        <div class="exp-company">${e.company || '—'}</div>
        <div class="exp-dates">${dateStr}</div>
      </div>`;
    });
    html += '</div>';
  }

  // Provenance
  const prov = p.provenance || [];
  if (prov.length) {
    const pid = Math.random().toString(36).slice(2);
    html += `<div style="margin-top:16px">
      <div class="prov-toggle" onclick="toggleProv('${pid}')">▸ provenance (${prov.length} fields)</div>
      <div id="prov-${pid}" style="display:none">
        <div class="prov-table">`;
    prov.forEach(r => {
      html += `<div class="prov-row">
        <span class="prov-field">${r.field}</span>
        <span><span class="src-tag src-${r.source}">${r.source}</span></span>
        <span>${r.method}</span>
      </div>`;
    });
    html += '</div></div></div>';
  }

  // Raw JSON
  const jid = Math.random().toString(36).slice(2);
  html += `<div class="json-toggle" onclick="toggleJson('${jid}')">{ } view raw JSON</div>
  <pre class="raw-json" id="json-${jid}">${JSON.stringify(p, null, 2)}</pre>`;

  return html;
}

function toggleCard(i) {
  const body = document.getElementById(`body-${i}`);
  body.classList.toggle('open');
}

function toggleProv(id) {
  const el = document.getElementById(`prov-${id}`);
  const toggle = el.previousElementSibling;
  const open = el.style.display === 'none';
  el.style.display = open ? 'block' : 'none';
  toggle.textContent = (open ? '▾' : '▸') + toggle.textContent.slice(1);
}

function toggleJson(id) {
  document.getElementById(`json-${id}`).classList.toggle('open');
}
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/load_samples")
def load_samples():
    return jsonify({"ok": True})


@app.route("/run", methods=["POST"])
def run():
    tmp_files = []
    try:
        csv_path = None
        ats_json_path = None
        notes_paths = []
        github_urls = request.form.getlist("github")

        def save_upload(file_storage):
            suffix = Path(file_storage.filename).suffix
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            file_storage.save(tmp.name)
            tmp_files.append(tmp.name)
            return tmp.name

        if request.form.get("use_samples"):
            csv_path = str(SAMPLE_DIR / "candidates.csv")
            ats_json_path = str(SAMPLE_DIR / "ats_data.json")
            notes_paths = [
                str(SAMPLE_DIR / "notes_jane.txt"),
                str(SAMPLE_DIR / "notes_bob.txt"),
            ]
        else:
            if "csv" in request.files and request.files["csv"].filename:
                csv_path = save_upload(request.files["csv"])
            if "ats_json" in request.files and request.files["ats_json"].filename:
                ats_json_path = save_upload(request.files["ats_json"])
            for f in request.files.getlist("notes"):
                if f.filename:
                    notes_paths.append(save_upload(f))

        if not any([csv_path, ats_json_path, github_urls, notes_paths]):
            return jsonify({"error": "No sources provided. Upload at least one file."}), 400

        config_text = request.form.get("config", "").strip()
        config = {}
        if config_text:
            try:
                config = json.loads(config_text)
            except json.JSONDecodeError as e:
                return jsonify({"error": f"Invalid config JSON: {e}"}), 400

        pipeline = Pipeline(config=config)
        profiles = pipeline.run(
            csv_path=csv_path,
            ats_json_path=ats_json_path,
            github_urls=github_urls,
            notes_paths=notes_paths,
        )

        all_sources = set()
        for p in profiles:
            all_sources.update(p.get("_sources_used", []))

        return jsonify({"profiles": profiles, "sources_used": sorted(all_sources)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        for f in tmp_files:
            try:
                os.unlink(f)
            except OSError:
                pass


if __name__ == "__main__":
    app.run(debug=True, port=8080)
