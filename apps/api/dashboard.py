from datetime import UTC, datetime
from html import escape
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.ui import page_shell
from core.config.settings import get_settings
from core.db.session import get_db
from core.models.job import Job
from core.models.job_phase import JobPhaseEntry
from core.models.paperless_instance import PaperlessInstance
from core.paperless.service import instance_slug_from_connector

router = APIRouter(tags=["dashboard"])

PHASE_DESCRIPTIONS = {
    "RECEIVE_EVENT": "Webhook empfangen, geprüft und als Verarbeitungsauftrag gespeichert.",
    "LOAD_DOCUMENT": "Dokumentmetadaten über die API der zugeordneten Paperless-Instanz geladen.",
    "DOWNLOAD_DOCUMENT": (
        "Originaldokument von Paperless in ein temporäres Arbeitsverzeichnis geladen."
    ),
    "RUN_OCR": "Texterkennung für das Originaldokument ausgeführt.",
    "WRITE_OCR": "Erkannten Text in Paperless zurückgeschrieben.",
    "SELECT_TEMPLATE": "Passende Verarbeitungsvorlage anhand des Dokumenttyps gesucht.",
    "EXTRACT_FIELDS": "Konfigurierte Felder mit den vorgesehenen Extraktionsverfahren ermittelt.",
    "VALIDATE_RESULTS": "Extrahierte Werte validiert und eindeutige Ergebnisse ausgewählt.",
    "RELOAD_METADATA": "Aktuelle Paperless-Metadaten vor dem Schreiben erneut geladen.",
    "WRITE_METADATA": "Leere Paperless-Felder mit validierten Ergebnissen befüllt.",
    "CLEANUP": "Temporäre Verarbeitungsdaten bereinigt.",
    "COMPLETE": "Verarbeitung abgeschlossen.",
}


DASHBOARD_CONTENT = """
<section class="metric-grid" aria-label="Systemstatus">
  <article class="metric-card">
    <div class="metric-label">eZEUS API</div>
    <div class="metric-value"><span class="status-dot" id="api-dot"></span>
      <span id="api-status">Prüfung läuft</span></div>
    <div class="metric-note" id="api-note">Bereitschaft der Verarbeitungskette</div>
  </article>
  <article class="metric-card">
    <div class="metric-label">Lokale KI</div>
    <div class="metric-value">{{OLLAMA_MODEL}}</div>
    <div class="metric-note">Lokale, mandantenbezogene Extraktion</div>
  </article>
  <article class="metric-card">
    <div class="metric-label">Texterkennung</div>
    <div class="metric-value">PaddleOCR</div>
    <div class="metric-note">OCR-Verarbeitung auf eigener Infrastruktur</div>
  </article>
  <article class="metric-card">
    <div class="metric-label">Dokumentenquelle</div>
    <div class="metric-value">Paperless</div>
    <div class="metric-note">Getrennte Kundeninstanzen</div>
  </article>
</section>
<section class="panel" aria-labelledby="processing-title">
  <div class="section-heading">
    <div>
      <h2 id="processing-title">Verarbeitungsprotokoll</h2>
      <p class="section-copy">Bereinigte technische Abläufe ohne Dokumentinhalte,
        Zugangsdaten oder Tokens. Einträge lassen sich für Details aufklappen.</p>
    </div>
    <span class="status-badge success">Automatische Aktualisierung</span>
  </div>
  <div class="log-toolbar">
    <div>
      <label for="log-search">Einträge durchsuchen</label>
      <input id="log-search" type="search" placeholder="Dateiname, Dokument-ID oder Status">
    </div>
    <div>
      <label for="log-limit">Anzahl</label>
      <select id="log-limit">
        <option value="50">50</option>
        <option value="100" selected>100</option>
        <option value="250">250</option>
      </select>
    </div>
    <button id="refresh-logs" class="primary" type="button">Aktualisieren</button>
    <span class="help-text" id="refresh-info" role="status">Wird geladen</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th aria-label="Details"></th><th>Zeit</th><th>Dokument</th>
        <th>Status</th><th>Dauer</th><th>Job</th>
      </tr></thead>
      <tbody id="log-body"></tbody>
    </table>
    <div class="loading-state" id="log-empty" role="status">Logs werden geladen</div>
  </div>
</section>
"""

DASHBOARD_SCRIPT = """
<script>
  const expandedJobIds = new Set();
  let logEntries = [];

  function setText(element, value) { element.textContent = value ?? "–"; }
  function formatTime(value) {
    return value ? new Date(value).toLocaleString("de-DE") : "–";
  }
  function formatDuration(value) {
    if (value === null || value === undefined) return "Läuft";
    if (value < 1) return "< 1 s";
    if (value < 60) return `${Math.round(value)} s`;
    return `${Math.floor(value / 60)} min ${Math.round(value % 60)} s`;
  }
  function appendText(parent, label, value, className = "detail-item") {
    const item = document.createElement("div"); item.className = className;
    const heading = document.createElement("strong"); heading.textContent = label;
    const content = document.createElement("span"); content.textContent = value ?? "–";
    item.append(heading, content); parent.appendChild(item);
  }
  function statusTone(status) {
    const value = String(status).toLowerCase();
    if (value === "completed") return "success";
    if (value === "failed") return "danger";
    return "warning";
  }
  function buildDetails(entry) {
    const detailRow = document.createElement("tr"); detailRow.className = "detail-row";
    const cell = document.createElement("td"); cell.colSpan = 6;
    const details = document.createElement("div"); details.className = "job-details";
    const summary = document.createElement("div"); summary.className = "detail-summary";
    appendText(summary, "Job-ID", entry.job_id);
    appendText(summary, "Paperless-Instanz", entry.instance_name || entry.connector);
    appendText(summary, "Dokument-ID", entry.document_id);
    appendText(summary, "Worker", entry.worker_id);
    appendText(summary, "Versuche", String(entry.retry_count + 1));
    appendText(summary, "Gesamtstatus", entry.status);
    details.appendChild(summary);
    const steps = document.createElement("div"); steps.className = "steps";
    entry.steps.forEach((step, index) => {
      const element = document.createElement("div");
      element.className = `step ${step.status.toLowerCase()}`;
      const timing = document.createElement("div");
      appendText(timing, `Schritt ${index + 1}`, step.label, "step-label");
      appendText(timing, "Status", step.status, "step-label");
      appendText(timing, "Start", formatTime(step.started_at), "step-label");
      appendText(timing, "Dauer", formatDuration(step.duration_seconds), "step-label");
      const explanation = document.createElement("div");
      appendText(explanation, "Was ist passiert?", step.description, "step-label");
      if (step.metadata && Object.keys(step.metadata).length) {
        appendText(explanation, "Details",
          Object.entries(step.metadata).map(([key,value]) => `${key}: ${value ?? "–"}`).join(" | "),
          "step-meta");
      }
      if (step.error) appendText(explanation, "Fehler", step.error, "error-box");
      element.append(timing, explanation); steps.appendChild(element);
    });
    if (entry.error_message) {
      appendText(details, "Vollständiger Jobfehler", entry.error_message, "error-box");
    }
    details.appendChild(steps); cell.appendChild(details); detailRow.appendChild(cell);
    return detailRow;
  }
  function renderLogs() {
    const body = document.getElementById("log-body");
    const empty = document.getElementById("log-empty");
    const query = document.getElementById("log-search").value.trim().toLocaleLowerCase("de");
    const filtered = logEntries.filter((entry) =>
      !query || [entry.filename, entry.document_id, entry.status, entry.job_id,
        entry.instance_name].some((value) =>
          String(value ?? "").toLocaleLowerCase("de").includes(query)));
    body.replaceChildren();
    filtered.forEach((entry) => {
      const row = document.createElement("tr"); row.className = "job-row";
      row.tabIndex = 0; row.setAttribute("role", "button");
      const isExpanded = expandedJobIds.has(entry.job_id);
      row.setAttribute("aria-expanded", String(isExpanded));
      const values = [isExpanded ? "−" : "+", formatTime(entry.started_at),
        `${entry.filename || "Unbekannt"} (Paperless ${entry.document_id})`,
        entry.status, formatDuration(entry.duration_seconds), entry.job_id.slice(0,8)];
      values.forEach((value,index) => {
        const cell = document.createElement("td");
        if (index === 3) {
          const badge = document.createElement("span");
          badge.className = `status-badge ${statusTone(value)}`; setText(badge,value);
          cell.appendChild(badge);
        } else { setText(cell,value); }
        row.appendChild(cell);
      });
      const detailRow = buildDetails(entry); detailRow.hidden = !isExpanded;
      const toggle = () => {
        detailRow.hidden = !detailRow.hidden;
        if (detailRow.hidden) expandedJobIds.delete(entry.job_id);
        else expandedJobIds.add(entry.job_id);
        row.cells[0].textContent = detailRow.hidden ? "+" : "−";
        row.setAttribute("aria-expanded", String(!detailRow.hidden));
      };
      row.addEventListener("click", toggle);
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault(); toggle();
        }
      });
      body.append(row, detailRow);
    });
    empty.className = "empty-state";
    empty.hidden = filtered.length > 0;
    empty.textContent = query ? "Keine passenden Einträge gefunden." :
      "Noch keine Verarbeitungseinträge vorhanden.";
  }
  async function loadLogs() {
    const button = document.getElementById("refresh-logs");
    const empty = document.getElementById("log-empty");
    window.ezeusUI?.setBusy(button, true, "Lädt …");
    try {
      const limit = document.getElementById("log-limit").value;
      const response = await fetch(`/api/logs?limit=${encodeURIComponent(limit)}`,
        {headers:{"Accept":"application/json"},cache:"no-store"});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      logEntries = (await response.json()).entries;
      renderLogs();
      document.getElementById("refresh-info").textContent =
        `Aktualisiert ${new Date().toLocaleTimeString("de-DE")}`;
    } catch (error) {
      empty.hidden = false; empty.className = "notice error";
      empty.textContent = `Logs konnten nicht geladen werden: ${error.message}`;
    } finally { window.ezeusUI?.setBusy(button, false); }
  }
  document.getElementById("refresh-logs").addEventListener("click", loadLogs);
  document.getElementById("log-limit").addEventListener("change", loadLogs);
  document.getElementById("log-search").addEventListener("input", renderLogs);
  fetch("/ready",{cache:"no-store"}).then((response) => {
    if (!response.ok) throw new Error();
    document.getElementById("api-dot").classList.add("ok");
    document.getElementById("api-status").textContent = "Bereit";
    document.getElementById("api-note").textContent = "Alle Komponenten erreichbar";
  }).catch(() => {
    document.getElementById("api-status").textContent = "Nicht bereit";
    document.getElementById("api-note").textContent = "Bereitschaftsprüfung fehlgeschlagen";
  });
  loadLogs();
  setInterval(loadLogs, 10000);
</script>
"""


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> str:
    content = DASHBOARD_CONTENT.replace(
        "{{OLLAMA_MODEL}}",
        escape(get_settings().ollama_model),
    )
    return page_shell(
        title="Betriebsübersicht",
        description=(
            "Status, Verarbeitungsschritte und technische Ereignisse aller "
            "angebundenen Paperless-Instanzen."
        ),
        active="dashboard",
        content=content,
        script=DASHBOARD_SCRIPT,
    )


@router.get("/api/logs")
def processing_logs(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=250)] = 100,
) -> dict[str, object]:
    jobs = db.scalars(select(Job).order_by(Job.created_at.desc()).limit(limit)).all()
    now = datetime.now(UTC)
    job_ids = [job.id for job in jobs]
    phases_by_job: dict[object, list[JobPhaseEntry]] = {job_id: [] for job_id in job_ids}
    if job_ids:
        phases = db.scalars(
            select(JobPhaseEntry)
            .where(JobPhaseEntry.job_id.in_(job_ids))
            .order_by(JobPhaseEntry.started_at.asc())
        )
        for phase in phases:
            phases_by_job[phase.job_id].append(phase)

    instances = {instance.slug: instance.name for instance in db.scalars(select(PaperlessInstance))}
    entries: list[dict[str, object]] = []
    for job in jobs:
        document = job.document
        phase_entries = [
            phase
            for phase in phases_by_job[job.id]
            if job.started_at is None or phase.started_at >= job.started_at
        ]
        started_at = job.started_at or job.created_at
        finished_at = job.finished_at
        duration = (finished_at or now) - started_at
        slug = instance_slug_from_connector(document.connector)
        steps: list[dict[str, object]] = []
        for phase_entry in phase_entries:
            phase_finished_at = phase_entry.finished_at
            phase_duration = (phase_finished_at or now) - phase_entry.started_at
            phase_name = phase_entry.phase.value
            error = phase_entry.error
            if error and job.error_message:
                error = f"{error}: {job.error_message}"
            steps.append(
                {
                    "phase": phase_name,
                    "label": phase_name.replace("_", " ").title(),
                    "description": PHASE_DESCRIPTIONS.get(
                        phase_name, "Verarbeitungsschritt ausgeführt."
                    ),
                    "status": phase_entry.status.value,
                    "started_at": phase_entry.started_at.isoformat(),
                    "finished_at": (phase_finished_at.isoformat() if phase_finished_at else None),
                    "duration_seconds": round(max(phase_duration.total_seconds(), 0), 3),
                    "metadata": phase_entry.metadata_json or {},
                    "error": error,
                }
            )
        entries.append(
            {
                "job_id": str(job.id),
                "document_id": document.external_document_id,
                "filename": document.filename,
                "connector": document.connector,
                "instance_name": instances.get(slug) if slug else "Legacy-Konfiguration",
                "status": job.status.value,
                "started_at": started_at.isoformat(),
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                "duration_seconds": round(max(duration.total_seconds(), 0), 1),
                "error_type": job.error_type,
                "error_message": job.error_message,
                "worker_id": job.worker_id,
                "retry_count": job.retry_count,
                "steps": steps,
            }
        )
    return {"entries": entries, "generated_at": now.isoformat()}
