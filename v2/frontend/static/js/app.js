const API = "";      
let currentJobId = null;
let pollTimer = null;
let lastExportPath = null;

// DOM references
const $ = id => document.getElementById(id);

const keywordInput    = $("keywordInput");
const addKeywordBtn   = $("addKeywordBtn");
const keywordTags     = $("keywordTags");
const cityInput       = $("cityInput");
const stateInput      = $("stateInput");
const maxResults      = $("maxResults");
const exportFormat    = $("exportFormat");
const minRating       = $("minRating");
const requirePhone    = $("requirePhone");
const requireWebsite  = $("requireWebsite");
const startBtn        = $("startBtn");
const stopBtn         = $("stopBtn");
const statsRow        = $("statsRow");
const progressBarWrap = $("progressBarWrap");
const progressBar     = $("progressBar");
const statusCard      = $("statusCard");
const logBody         = $("logBody");
const exportReady     = $("exportReady");
const downloadBtn     = $("downloadBtn");
const statLeads       = $("statLeads");
const statQueries     = $("statQueries");
const statStatus      = $("statStatus");

//  Keyword tags

let keywords = [];

function renderTags() {
  keywordTags.innerHTML = "";
  keywords.forEach((kw, i) => {
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.innerHTML = `${escHtml(kw)} <button class="tag-remove" data-idx="${i}">×</button>`;
    keywordTags.appendChild(tag);
  });
}

function addKeyword(kw) {
  kw = kw.trim();
  if (!kw || keywords.includes(kw)) return;
  keywords.push(kw);
  renderTags();
  keywordInput.value = "";
}

addKeywordBtn.addEventListener("click", () => addKeyword(keywordInput.value));
keywordInput.addEventListener("keydown", e => {
  if (e.key === "Enter") addKeyword(keywordInput.value);
});
keywordTags.addEventListener("click", e => {
  const btn = e.target.closest(".tag-remove");
  if (!btn) return;
  keywords.splice(+btn.dataset.idx, 1);
  renderTags();
});

// Quick-fill keyword chips
document.querySelectorAll(".chip[data-kw]").forEach(chip => {
  chip.addEventListener("click", () => addKeyword(chip.dataset.kw));
});

// Quick-fill location chips
document.querySelectorAll(".chip[data-city]").forEach(chip => {
  chip.addEventListener("click", () => {
    cityInput.value  = chip.dataset.city  || "";
    stateInput.value = chip.dataset.state || "";
  });
});

// Panel navigation

document.querySelectorAll(".nav-btn[data-panel]").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    $(`panel-${btn.dataset.panel}`).classList.add("active");

    if (btn.dataset.panel === "exports") loadExports();
    if (btn.dataset.panel === "jobs")    loadJobs();
  });
});

// Theme toggle

$("themeToggle").addEventListener("click", () => {
  const html = document.documentElement;
  html.dataset.theme = html.dataset.theme === "dark" ? "light" : "dark";
});

// Log helpers

function appendLog(text, cls = "") {
  const ts = new Date().toLocaleTimeString("en-GB", { hour12: false });
  const line = document.createElement("div");
  line.className = `log-line ${cls}`;
  line.innerHTML = `<span class="log-ts">${ts}</span>${escHtml(text)}`;
  logBody.appendChild(line);
  logBody.scrollTop = logBody.scrollHeight;
}

function clearLog() {
  logBody.innerHTML = "";
}

$("clearLogBtn").addEventListener("click", clearLog);

function setStatusRunning(query) {
  statusCard.innerHTML = `
    <div style="text-align:center">
      <div class="idle-icon pulsing">⬡</div>
      <div style="font-family:var(--font-mono);font-size:13px;color:var(--accent)">
        Scraping: ${escHtml(query)}
      </div>
    </div>
  `;
}

function setStatusIdle(text = "Waiting…") {
  statusCard.innerHTML = `
    <div class="status-idle">
      <div class="idle-icon">⬡</div>
      <div class="idle-text">${text}</div>
    </div>
  `;
}

// Start scraping

startBtn.addEventListener("click", async () => {
  if (!keywords.length) {
    alert("Add at least one keyword.");
    return;
  }

  clearLog();
  exportReady.classList.add("hidden");
  statsRow.classList.remove("hidden");
  progressBarWrap.classList.remove("hidden");
  startBtn.classList.add("hidden");
  stopBtn.classList.remove("hidden");
  statLeads.textContent   = "0";
  statQueries.textContent = "0/0";
  statStatus.textContent  = "running";
  progressBar.style.width = "0%";
  lastExportPath = null;

  const payload = {
    keywords,
    city:            cityInput.value.trim(),
    state:           stateInput.value.trim(),
    max_results:     +maxResults.value || 60,
    export_format:   exportFormat.value,
    min_rating:      +minRating.value || 0,
    require_phone:   requirePhone.checked,
    require_website: requireWebsite.checked,
    categories:      [],
  };

  try {
    const res = await fetch(`${API}/api/scraper/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    currentJobId = data.job_id;
    appendLog(`Job started: ${currentJobId}`, "");
    setStatusRunning(keywords.join(", "));
    startPolling();
  } catch (err) {
    appendLog(`Failed to start: ${err.message}`, "error");
    resetUI();
  }
});

stopBtn.addEventListener("click", async () => {
  if (!currentJobId) return;
  await fetch(`${API}/api/scraper/cancel/${currentJobId}`, { method: "POST" });
  appendLog("Stop requested…", "warn");
  stopPolling();
  resetUI();
  setStatusIdle("Scraping cancelled.");
});

// Polling

let lastLogCount = 0;

function startPolling() {
  lastLogCount = 0;
  pollTimer = setInterval(pollJob, 1800);
}

function stopPolling() {
  clearInterval(pollTimer);
  pollTimer = null;
}

async function pollJob() {
  if (!currentJobId) return;
  try {
    const res  = await fetch(`${API}/api/jobs/${currentJobId}`);
    const job  = await res.json();
    applyJobUpdate(job);
  } catch {
  }
}

function applyJobUpdate(job) {
  const newLogs = job.logs.slice(lastLogCount);
  lastLogCount = job.logs.length;
  newLogs.forEach(ev => {
    const ev_name = ev.event || "";
    if (ev_name === "lead_found") {
      appendLog(`✓ ${ev.name} | ${ev.phone || "no phone"}`, "lead");
    } else if (ev_name === "query_start") {
      appendLog(`→ Searching: ${ev.query}`, "");
      setStatusRunning(ev.query);
    } else if (ev_name === "query_done") {
      appendLog(`✓ Done: ${ev.query} (${ev.count} leads)`, "success");
    } else if (ev_name === "query_error") {
      appendLog(`✗ Error on ${ev.query}: ${ev.error}`, "error");
    } else if (ev_name === "exported") {
      appendLog(`📁 Saved: ${ev.path}`, "success");
    }
  });

  // Stats
  statLeads.textContent   = job.leads_found;
  statQueries.textContent = `${job.queries_done}/${job.total_queries || "?"}`;
  statStatus.textContent  = job.status;

  // Progress bar
  if (job.total_queries > 0) {
    progressBar.style.width =
      `${Math.min(100, Math.round((job.queries_done / job.total_queries) * 100))}%`;
  }

  // Terminal states
  if (["done", "cancelled", "error"].includes(job.status)) {
    stopPolling();
    resetUI();

    if (job.status === "done") {
      progressBar.style.width = "100%";
      setStatusIdle("✓ Scraping complete!");
      lastExportPath = job.export_path;
      exportReady.classList.remove("hidden");
      appendLog(`Done! ${job.leads_found} leads found.`, "success");
    } else if (job.status === "error") {
      setStatusIdle(`✗ Error: ${job.error || "unknown"}`);
      appendLog(`Job failed: ${job.error}`, "error");
    }
  }
}

function resetUI() {
  startBtn.classList.remove("hidden");
  stopBtn.classList.add("hidden");
  startBtn.disabled = false;
}

// Download

downloadBtn.addEventListener("click", () => {
  if (!lastExportPath) return;
  const filename = lastExportPath.split("/").pop().split("\\").pop();
  window.open(`${API}/api/exports/download/${encodeURIComponent(filename)}`, "_blank");
});

// Exports panel

async function loadExports() {
  const tbody = $("exportsBody");
  tbody.innerHTML = `<tr><td colspan="5" class="empty-row">Loading…</td></tr>`;
  try {
    const res   = await fetch(`${API}/api/exports/`);
    const files = await res.json();
    if (!files.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty-row">No exports yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = files.map(f => `
      <tr>
        <td>${escHtml(f.name)}</td>
        <td><span class="job-badge badge-done">${f.format.toUpperCase()}</span></td>
        <td>${f.size_kb} KB</td>
        <td>${new Date(f.modified).toLocaleString()}</td>
        <td>
          <a class="btn-outline" style="padding:4px 10px;font-size:11px;text-decoration:none"
             href="${API}/api/exports/download/${encodeURIComponent(f.name)}" target="_blank">
            ⬇ Download
          </a>
        </td>
      </tr>
    `).join("");
  } catch {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-row">Failed to load exports.</td></tr>`;
  }
}

$("refreshExportsBtn").addEventListener("click", loadExports);

// Jobs panel

async function loadJobs() {
  const list = $("jobsList");
  list.innerHTML = `<div class="empty-row">Loading…</div>`;
  try {
    const res  = await fetch(`${API}/api/jobs/`);
    const jobs = await res.json();
    if (!jobs.length) {
      list.innerHTML = `<div class="empty-row">No jobs yet.</div>`;
      return;
    }
    list.innerHTML = jobs.map(j => `
      <div class="job-card">
        <div class="job-info">
          <div class="job-keywords">${escHtml(j.keywords.join(", "))}</div>
          <div class="job-meta">
            ${j.city ? j.city + ", " : ""}${j.state || ""}
            &nbsp;·&nbsp; ${j.leads_found} leads
            &nbsp;·&nbsp; ${new Date(j.created_at).toLocaleString()}
          </div>
        </div>
        <span class="job-badge badge-${j.status}">${j.status.toUpperCase()}</span>
      </div>
    `).join("");
  } catch {
    list.innerHTML = `<div class="empty-row">Failed to load jobs.</div>`;
  }
}

$("refreshJobsBtn").addEventListener("click", loadJobs);

// Utility

function escHtml(str = "") {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
