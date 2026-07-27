from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.db.session import get_db
from core.models.document import Document
from core.models.job import Job
from core.models.job_phase import JobPhaseEntry

router = APIRouter(tags=["dashboard"])


DASHBOARD_HTML = """<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>eZEUS-AI-2</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b1020;
      --panel: #141b2d;
      --panel-soft: #1a2338;
      --text: #f4f7ff;
      --muted: #9ca9c4;
      --accent: #65d6ad;
      --border: #2a3550;
      --ok: #6ee7a8;
      --warn: #ffd166;
      --error: #ff7b86;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at top left, rgba(69, 104, 220, .18), transparent 32rem),
        var(--bg);
      color: var(--text);
      font: 15px/1.5 Inter, ui-sans-serif, system-ui, sans-serif;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 2rem;
      padding: 1.1rem clamp(1rem, 4vw, 3rem);
      border-bottom: 1px solid var(--border);
      background: rgba(11, 16, 32, .82);
      backdrop-filter: blur(12px);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .brand { display: flex; align-items: center; gap: .8rem; }
    .mark {
      width: 2.2rem;
      height: 2.2rem;
      display: grid;
      place-items: center;
      border-radius: .7rem;
      background: linear-gradient(135deg, #65d6ad, #4b7bec);
      color: #08111b;
      font-weight: 900;
    }
    .brand strong { display: block; letter-spacing: .02em; }
    .brand small { color: var(--muted); }
    nav { display: flex; gap: .4rem; }
    nav button, nav a {
      appearance: none;
      border: 1px solid transparent;
      border-radius: .65rem;
      background: transparent;
      color: var(--muted);
      cursor: pointer;
      padding: .65rem .9rem;
      text-decoration: none;
      font: inherit;
    }
    nav button:hover, nav a:hover, nav button.active {
      color: var(--text);
      border-color: var(--border);
      background: var(--panel-soft);
    }
    main {
      width: min(1180px, calc(100% - 2rem));
      margin: 2rem auto 4rem;
    }
    .tab { display: none; }
    .tab.active { display: block; }
    h1 { margin: 0 0 .35rem; font-size: clamp(1.7rem, 4vw, 2.5rem); }
    .lead { color: var(--muted); margin: 0 0 1.8rem; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 1rem;
    }
    .card {
      border: 1px solid var(--border);
      border-radius: 1rem;
      background: linear-gradient(145deg, rgba(26, 35, 56, .95), rgba(20, 27, 45, .95));
      padding: 1.15rem;
      box-shadow: 0 18px 45px rgba(0, 0, 0, .14);
    }
    .card .label { color: var(--muted); font-size: .82rem; text-transform: uppercase; }
    .card .value { margin-top: .45rem; font-size: 1.15rem; font-weight: 700; }
    .status-dot {
      display: inline-block;
      width: .65rem;
      height: .65rem;
      border-radius: 50%;
      background: var(--muted);
      margin-right: .5rem;
    }
    .status-dot.ok { background: var(--ok); box-shadow: 0 0 12px rgba(110, 231, 168, .7); }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: .8rem;
      margin: 1.2rem 0;
    }
    .toolbar select, .toolbar button {
      border: 1px solid var(--border);
      border-radius: .6rem;
      background: var(--panel-soft);
      color: var(--text);
      padding: .55rem .75rem;
      font: inherit;
    }
    .toolbar button { cursor: pointer; }
    .table-wrap {
      overflow: auto;
      border: 1px solid var(--border);
      border-radius: 1rem;
      background: var(--panel);
    }
    table { width: 100%; border-collapse: collapse; min-width: 840px; }
    th, td {
      padding: .78rem .9rem;
      text-align: left;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }
    th {
      color: var(--muted);
      background: var(--panel-soft);
      font-size: .78rem;
      text-transform: uppercase;
      position: sticky;
      top: 0;
    }
    tr:last-child td { border-bottom: 0; }
    .badge {
      display: inline-block;
      border-radius: 999px;
      padding: .2rem .55rem;
      background: rgba(156, 169, 196, .14);
      color: var(--muted);
      font-size: .78rem;
      font-weight: 700;
    }
    .badge.completed { color: var(--ok); background: rgba(110, 231, 168, .12); }
    .badge.running { color: var(--warn); background: rgba(255, 209, 102, .12); }
    .badge.failed { color: var(--error); background: rgba(255, 123, 134, .12); }
    .muted { color: var(--muted); }
    .empty { padding: 2rem; text-align: center; color: var(--muted); }
    @media (max-width: 680px) {
      header { align-items: flex-start; flex-direction: column; gap: .8rem; }
      nav { width: 100%; overflow-x: auto; }
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="mark">eZ</div>
      <div><strong>eZEUS-AI-2</strong><small>Dokumentenverarbeitung</small></div>
    </div>
    <nav aria-label="Hauptnavigation">
      <button class="active" data-tab="overview">Übersicht</button>
      <button data-tab="logs">Logs</button>
      <a href="/docs">API</a>
    </nav>
  </header>
  <main>
    <section class="tab active" id="overview">
      <h1>Betriebsübersicht</h1>
      <p class="lead">Status der lokalen Verarbeitungskette für Paperless-ngx.</p>
      <div class="grid">
        <article class="card">
          <div class="label">eZEUS API</div>
          <div class="value">
            <span class="status-dot" id="api-dot"></span>
            <span id="api-status">Prüfung …</span>
          </div>
        </article>
        <article class="card">
          <div class="label">Lokale KI</div>
          <div class="value">Qwen3:4b</div>
        </article>
        <article class="card">
          <div class="label">OCR</div>
          <div class="value">PaddleOCR</div>
        </article>
        <article class="card">
          <div class="label">Dokumentenquelle</div>
          <div class="value">Paperless-ngx</div>
        </article>
      </div>
    </section>
    <section class="tab" id="logs">
      <h1>Logs</h1>
      <p class="lead">
        Bereinigtes Verarbeitungsprotokoll ohne Dokumentinhalte, Tokens oder Passwörter.
      </p>
      <div class="toolbar">
        <span class="muted" id="refresh-info">Noch nicht geladen</span>
        <div>
          <select id="log-limit" aria-label="Anzahl Einträge">
            <option value="50">50 Einträge</option>
            <option value="100" selected>100 Einträge</option>
            <option value="250">250 Einträge</option>
          </select>
          <button id="refresh-logs">Aktualisieren</button>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Zeit</th>
              <th>Dokument</th>
              <th>Phase</th>
              <th>Status</th>
              <th>Dauer</th>
              <th>Job</th>
            </tr>
          </thead>
          <tbody id="log-body"></tbody>
        </table>
        <div class="empty" id="log-empty">Logs werden geladen …</div>
      </div>
    </section>
  </main>
  <script>
    const tabs = document.querySelectorAll("[data-tab]");
    const sections = document.querySelectorAll(".tab");
    let refreshTimer;

    function activateTab(id) {
      tabs.forEach((button) => button.classList.toggle("active", button.dataset.tab === id));
      sections.forEach((section) => section.classList.toggle("active", section.id === id));
      if (id === "logs") {
        loadLogs();
        clearInterval(refreshTimer);
        refreshTimer = setInterval(loadLogs, 10000);
      } else {
        clearInterval(refreshTimer);
      }
    }

    tabs.forEach(
      (button) => button.addEventListener("click", () => activateTab(button.dataset.tab))
    );

    function setText(cell, value) {
      cell.textContent = value ?? "–";
    }

    function formatTime(value) {
      return value ? new Date(value).toLocaleString("de-DE") : "–";
    }

    function formatDuration(value) {
      if (value === null || value === undefined) return "läuft";
      if (value < 1) return "< 1 s";
      if (value < 60) return `${Math.round(value)} s`;
      return `${Math.floor(value / 60)} min ${Math.round(value % 60)} s`;
    }

    async function loadLogs() {
      const body = document.getElementById("log-body");
      const empty = document.getElementById("log-empty");
      const limit = document.getElementById("log-limit").value;
      try {
        const response = await fetch(`/api/logs?limit=${encodeURIComponent(limit)}`, {
          headers: { "Accept": "application/json" },
          cache: "no-store"
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = await response.json();
        body.replaceChildren();
        payload.entries.forEach((entry) => {
          const row = document.createElement("tr");
          const values = [
            formatTime(entry.started_at),
            `${entry.filename || "Unbekannt"} (Paperless ${entry.document_id})`,
            entry.phase,
            entry.status,
            formatDuration(entry.duration_seconds),
            entry.job_id.slice(0, 8)
          ];
          values.forEach((value, index) => {
            const cell = document.createElement("td");
            if (index === 3) {
              const badge = document.createElement("span");
              badge.className = `badge ${String(value).toLowerCase()}`;
              setText(badge, value);
              cell.appendChild(badge);
            } else {
              setText(cell, value);
            }
            row.appendChild(cell);
          });
          body.appendChild(row);
        });
        empty.style.display = payload.entries.length ? "none" : "block";
        empty.textContent = "Noch keine Verarbeitungseinträge vorhanden.";
        document.getElementById("refresh-info").textContent =
          `Zuletzt aktualisiert: ${new Date().toLocaleTimeString("de-DE")}`;
      } catch (error) {
        empty.style.display = "block";
        empty.textContent = `Logs konnten nicht geladen werden: ${error.message}`;
      }
    }

    document.getElementById("refresh-logs").addEventListener("click", loadLogs);
    document.getElementById("log-limit").addEventListener("change", loadLogs);

    fetch("/ready", { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error();
        document.getElementById("api-dot").classList.add("ok");
        document.getElementById("api-status").textContent = "Bereit";
      })
      .catch(() => {
        document.getElementById("api-status").textContent = "Nicht bereit";
      });
  </script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> str:
    return DASHBOARD_HTML


@router.get("/api/logs")
def processing_logs(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=250)] = 100,
) -> dict[str, object]:
    rows = db.execute(
        select(JobPhaseEntry, Job, Document)
        .join(Job, JobPhaseEntry.job_id == Job.id)
        .join(Document, Job.document_id == Document.id)
        .order_by(JobPhaseEntry.started_at.desc())
        .limit(limit)
    ).all()
    now = datetime.now(UTC)
    entries: list[dict[str, object]] = []
    for phase_entry, job, document in rows:
        finished_at = phase_entry.finished_at
        duration = (finished_at or now) - phase_entry.started_at
        entries.append(
            {
                "job_id": str(job.id),
                "document_id": document.external_document_id,
                "filename": document.filename,
                "phase": phase_entry.phase.value,
                "status": phase_entry.status.value,
                "started_at": phase_entry.started_at.isoformat(),
                "finished_at": finished_at.isoformat() if finished_at else None,
                "duration_seconds": round(max(duration.total_seconds(), 0), 1),
                "error_type": job.error_type if phase_entry.error else None,
            }
        )
    return {"entries": entries, "generated_at": now.isoformat()}
