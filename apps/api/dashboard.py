import re
from datetime import UTC, datetime
from html import escape
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from apps.api.ui import page_shell
from core.config.settings import get_settings
from core.db.session import get_db
from core.jobs.retention import TERMINAL_STATUSES, delete_jobs
from core.models.audit import AuditEntry
from core.models.document import Document
from core.models.enums import JobStatus
from core.models.job import Job
from core.models.job_phase import JobPhaseEntry
from core.models.paperless_instance import PaperlessInstance
from core.paperless.service import instance_slug_from_connector
from core.security.admin_auth import AdminPrincipal, require_admin_secret, require_admin_user
from core.security.redaction import redact_sensitive_text

router = APIRouter(tags=["dashboard"])

PHASE_DESCRIPTIONS = {
    "RECEIVE_EVENT": "Webhook empfangen, geprüft und als Verarbeitungsauftrag gespeichert.",
    "LOAD_DOCUMENT": "Dokumentmetadaten über die API der zugeordneten Paperless-Instanz geladen.",
    "READ_DOCUMENT_TEXT": (
        "Textinhalt aus Paperless gelesen; Quelle und Zeichenanzahl werden protokolliert."
    ),
    "SELECT_TEMPLATE": "Passende Verarbeitungsvorlage anhand des Dokumenttyps gesucht.",
    "EXTRACT_FIELDS": "Konfigurierte Felder mit den vorgesehenen Extraktionsverfahren ermittelt.",
    "VALIDATE_RESULTS": "Extrahierte Werte validiert und eindeutige Ergebnisse ausgewählt.",
    "RELOAD_METADATA": "Aktuelle Paperless-Metadaten vor dem Schreiben erneut geladen.",
    "WRITE_METADATA": "Leere Paperless-Felder mit validierten Ergebnissen befüllt.",
    "CLEANUP": "Temporäre Verarbeitungsdaten bereinigt.",
    "COMPLETE": "Verarbeitung abgeschlossen.",
}

STATUS_LABELS = {
    JobStatus.RECEIVED: "Eingegangen",
    JobStatus.QUEUED: "Wartet auf Verarbeitung",
    JobStatus.RUNNING: "In Bearbeitung",
    JobStatus.RETRY_WAITING: "Wartet auf Wiederholung",
    JobStatus.COMPLETED: "Abgeschlossen",
    JobStatus.COMPLETED_WITH_WARNINGS: "Abgeschlossen mit Hinweisen",
    JobStatus.FAILED: "Fehlgeschlagen",
    JobStatus.CANCELLED: "Abgebrochen",
}

PHASE_LABELS = {
    "RECEIVE_EVENT": "Ereignis annehmen",
    "LOAD_DOCUMENT": "Dokument laden",
    "READ_DOCUMENT_TEXT": "Dokumenttext lesen",
    "SELECT_TEMPLATE": "Vorlage auswählen",
    "EXTRACT_FIELDS": "Felder ermitteln",
    "VALIDATE_RESULTS": "Ergebnisse prüfen",
    "RELOAD_METADATA": "Metadaten neu laden",
    "WRITE_METADATA": "Metadaten schreiben",
    "CLEANUP": "Aufräumen",
    "COMPLETE": "Verarbeitung abschließen",
}

PHASE_STATUS_LABELS = {
    "RUNNING": "Läuft",
    "COMPLETED": "Abgeschlossen",
    "FAILED": "Fehlgeschlagen",
}

ACTIVE_STATUSES = frozenset(JobStatus) - TERMINAL_STATUSES
DELETE_BATCH_SIZE = 500


class DeleteLogsRequest(BaseModel):
    job_ids: list[UUID] = Field(min_length=1, max_length=DELETE_BATCH_SIZE)


class DeleteMatchingLogsRequest(BaseModel):
    instance_slug: str | None = Field(default=None, max_length=64)
    q: str | None = Field(default=None, max_length=255)


def _safe_error_detail(error_type: str | None, message: object, phase: str) -> str:
    cleaned = redact_sensitive_text(message or "Keine technische Meldung vorhanden.", limit=800)
    cleaned = re.sub(
        r"(?is)\b(ocr|document[_ -]?text|content)\s*[:=]\s*.+",
        r"\1=[DOKUMENTINHALT AUSGEBLENDET]",
        cleaned,
    )
    cleaned = " ".join(cleaned.split())[:500]
    return f"{error_type or 'UnbekannterFehler'} in {phase}: {cleaned}"


def _redact_display_value(key: str, value: object) -> object:
    normalized_key = key.lower()
    content_key = normalized_key in {
        "ocr",
        "ocr_text",
        "text",
        "document_text",
        "content",
        "raw_content",
    }
    if content_key:
        return "[DOKUMENTINHALT AUSGEBLENDET]"
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, dict):
        return {
            str(item_key): _redact_display_value(str(item_key), item)
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_display_value(key, item) for item in value]
    return value


def explain_error(
    error_type: str | None,
    message: object,
    phase: str,
    *,
    document_id: str | None = None,
    field: str | None = None,
) -> dict[str, str]:
    """Create a redacted, user-facing explanation without persisting new data."""
    kind = error_type or "UnbekannterFehler"
    lowered = f"{kind} {message}".lower()
    step = PHASE_LABELS.get(phase, phase or "unbekannter Schritt")
    subject = f"Dokument {document_id}" if document_id else "das Dokument"
    if field:
        subject += f", Feld „{field}“"
    retryable = kind in {
        "RateLimitError",
        "TimeoutError",
        "ConnectionError",
        "RetryableEmptyTextError",
        "StalledJob",
    }
    retry_text = (
        "eZEUS wiederholt den Vorgang automatisch."
        if retryable
        else "eZEUS wiederholt diesen Fehler nicht automatisch."
    )

    if kind in {"AuthenticationError", "AuthorizationError"}:
        reason = "Die Anmeldung oder Berechtigung an Paperless wurde abgelehnt."
        recommendation = "API-Token und Rechte der gewählten Paperless-Instanz prüfen."
    elif kind == "NotFoundError":
        reason = "Das angeforderte Dokument oder Zielobjekt ist in Paperless nicht mehr vorhanden."
        recommendation = (
            "Dokument-ID und Paperless-Instanz prüfen und den Auftrag danach neu starten."
        )
    elif kind == "RateLimitError":
        reason = "Paperless hat vorübergehend zu viele Anfragen gemeldet."
        recommendation = (
            "Die automatische Wiederholung abwarten; bei Dauerproblemen das API-Limit prüfen."
        )
    elif kind == "TimeoutError":
        reason = "Der angesprochene Dienst hat nicht rechtzeitig geantwortet."
        recommendation = (
            "Erreichbarkeit und Auslastung des Dienstes prüfen; die Wiederholung abwarten."
        )
    elif kind == "ConnectionError":
        reason = (
            "Die Verbindung zu Paperless oder einem benötigten Dienst konnte nicht "
            "aufgebaut werden."
        )
        recommendation = (
            "Netzwerk, Zieladresse und Dienstzustand prüfen; die Wiederholung abwarten."
        )
    elif kind == "ConflictError":
        reason = "Paperless meldet einen Konflikt mit dem aktuellen Dokumentzustand."
        recommendation = (
            "Dokumentänderungen prüfen und den Auftrag mit aktuellen Metadaten erneut starten."
        )
    elif kind == "ValidationError":
        reason = (
            "Ein gelieferter Wert erfüllt die erwarteten Regeln oder das Paperless-Format nicht."
        )
        recommendation = (
            "Feldkonfiguration und den betroffenen Wert prüfen und anschließend neu verarbeiten."
        )
    elif kind == "RetryableEmptyTextError":
        reason = "Paperless hat noch keinen verwertbaren OCR-Text bereitgestellt."
        recommendation = (
            "Die OCR-Verarbeitung in Paperless abschließen lassen; eZEUS versucht es erneut."
        )
    elif "ollama" in lowered:
        reason = "Die lokale KI konnte die Anfrage nicht vollständig verarbeiten."
        recommendation = (
            "Ollama-Modell, Arbeitsspeicher und Dienstzustand prüfen und den Auftrag neu starten."
        )
    elif kind == "StalledJob":
        reason = "Der Auftrag hat innerhalb der erlaubten Zeit keinen Fortschritt gemeldet."
        recommendation = (
            "Worker-Zustand und Warteschlange prüfen; eZEUS plant den Auftrag erneut ein."
        )
    elif "field" in lowered and ("config" in lowered or "auflös" in lowered):
        reason = "Die konfigurierte Feldreferenz konnte in Paperless nicht aufgelöst werden."
        recommendation = "Feldname beziehungsweise Feld-ID in der Instanzkonfiguration korrigieren."
    elif "candidate" in lowered or "kandidat" in lowered or "ambiguous" in lowered:
        reason = (
            "Mehrere Extraktionskandidaten widersprechen sich; eine eindeutige Auswahl "
            "war nicht möglich."
        )
        recommendation = "Extraktionsregel präzisieren oder den korrekten Wert im Dokument prüfen."
    elif "write" in lowered or "geschrieben" in lowered:
        reason = (
            f"Der ermittelte Wert für {field or 'ein Feld'} wurde nicht nach Paperless geschrieben."
        )
        recommendation = "Feldrechte, Feldtyp und den bereits vorhandenen Paperless-Wert prüfen."
    else:
        reason = f"Im Schritt „{step}“ ist ein nicht näher klassifizierter Fehler aufgetreten."
        recommendation = (
            "Technische Details prüfen, Ursache im betroffenen Dienst beheben und neu starten."
        )

    return {
        "was": (
            f"Der Schritt „{step}“ für {subject} konnte nicht wie vorgesehen abgeschlossen werden."
        ),
        "warum": f"{reason} {retry_text}",
        "empfehlung": recommendation,
        "technisch": _safe_error_detail(kind, message, phase),
    }


def elapsed_seconds(started_at: datetime, finished_at: datetime | None, now: datetime) -> float:
    endpoint = finished_at or now
    if started_at.tzinfo is None and endpoint.tzinfo is not None:
        endpoint = endpoint.replace(tzinfo=None)
    return max((endpoint - started_at).total_seconds(), 0)


def derive_step_warnings(phase_name: str, metadata: dict[str, object]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []

    def add(message: str, reason: str, hint: str) -> None:
        warnings.append({"message": message, "reason": reason, "hint": hint})

    if phase_name == "SELECT_TEMPLATE" and metadata.get("selected") is False:
        add(
            "Keine passende Verarbeitungsvorlage für den Dokumenttyp gefunden.",
            "Dokumenttyp und aktive Vorlagen ergaben keine eindeutige Zuordnung.",
            "Dokumenttyp und Vorlagenzuordnung der Instanz prüfen.",
        )
    if phase_name == "EXTRACT_FIELDS":
        if metadata.get("candidates_found") == 0:
            add(
                "Keine Extraktionskandidaten aus dem Dokumenttext ermittelt.",
                "Die aktiven Regeln fanden keinen passenden Wert.",
                "Extraktionsprofil und Dokumentlayout prüfen.",
            )
        elif metadata.get("text_characters") == 0:
            add(
                "Dokument enthielt keinen Text für die Extraktion.",
                "Paperless hat noch keinen verwertbaren OCR-Text geliefert.",
                "OCR in Paperless abschließen lassen und den Auftrag erneut starten.",
            )
    if phase_name == "VALIDATE_RESULTS":
        missing = metadata.get("missing_fields") or []
        if isinstance(missing, list) and missing:
            add(
                "Fehlende Pflichtfelder: " + ", ".join(str(item) for item in missing),
                "Für mindestens ein Pflichtfeld lag kein eindeutiger gültiger Wert vor.",
                "Genannte Felder, Extraktionsregeln und Dokumentinhalt prüfen.",
            )
        if metadata.get("fields_accepted") == 0:
            add(
                "Kein Feld hat die Validierung bestanden.",
                "Alle Kandidaten wurden durch Format-, Plausibilitäts- oder "
                "Konfliktregeln abgelehnt.",
                "Validierungsregeln und Kandidaten im Dokument prüfen.",
            )
    if phase_name == "WRITE_METADATA":
        fields_written = metadata.get("fields_written")
        wrote_any = (
            (isinstance(fields_written, int) and fields_written > 0)
            or bool(metadata.get("title_written"))
            or bool(metadata.get("correspondent_written"))
        )
        if not wrote_any and metadata:
            add(
                "Keine Metadaten in Paperless geschrieben (keine übernehmbaren Werte).",
                "Es gab keinen validierten freien Zielwert oder vorhandene Werte wurden geschützt.",
                "Zielwerte und Feldkonfiguration in Paperless prüfen.",
            )
    return warnings


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
    <div class="metric-value">Paperless-ngx</div>
    <div class="metric-note">OCR wird von Paperless-ngx übernommen</div>
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
        Zugangsdaten oder Tokens. Zunächst werden die letzten 50 Einträge
        der gewählten Instanz geladen; weitere lassen sich nachladen.</p>
    </div>
    <span class="status-badge success">Automatische Aktualisierung</span>
  </div>
  <div class="log-toolbar">
    <div>
      <label for="log-instance">Instanz (Paperless-URL)</label>
      <select id="log-instance">
        <option value="">Alle Instanzen</option>
      </select>
    </div>
    <div>
      <label for="log-search">Einträge durchsuchen</label>
      <input id="log-search" type="search"
        placeholder="Dokument-ID, Dateiname, Status oder Job-ID">
    </div>
    <button id="refresh-logs" class="primary" type="button">Aktualisieren</button>
    <button id="delete-selected-logs" class="danger" type="button" disabled>
      Ausgewählte löschen (0)
    </button>
    <span class="help-text" id="refresh-info" role="status">Wird geladen</span>
  </div>
  <div class="selection-toolbar" id="selection-toolbar" hidden>
    <span id="selection-summary"></span>
    <button id="select-all-matches" class="small" type="button" hidden></button>
  </div>
  <div class="notice info compact" id="delete-info" role="status" hidden></div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th class="selection-cell">
          <input id="select-page" type="checkbox" aria-label="Diese Seite auswählen"
            title="Diese Seite auswählen">
        </th><th aria-label="Details"></th><th>Zeit</th><th>Dokument</th>
        <th>Status</th><th>Dauer</th><th>Job</th>
      </tr></thead>
      <tbody id="log-body"></tbody>
    </table>
    <div class="loading-state" id="log-empty" role="status">Logs werden geladen</div>
  </div>
  <div class="pagination-toolbar" aria-label="Seitennavigation">
    <button id="previous-page" class="small" type="button" disabled>
      Vorherige Seite
    </button>
    <span id="page-info" class="help-text" role="status">Seite 1</span>
    <button id="next-page" class="small" type="button" disabled>
      Nächste Seite
    </button>
  </div>
</section>
"""

DASHBOARD_SCRIPT = """
<script>
  const expandedJobIds = new Set();
  let logEntries = [];
  let logInstancesLoaded = false;
  let nextCursor = null;

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
    if (entry.warnings && entry.warnings.length) {
      const wrap = document.createElement("div");
      wrap.className = "warning-box";
      const title = document.createElement("div");
      title.className = "warning-title";
      title.textContent = `Warnungen (${entry.warnings.length})`;
      wrap.appendChild(title);
      const list = document.createElement("ul");
      list.className = "warning-list";
      entry.warnings.forEach((message) => {
        const item = document.createElement("li");
        item.textContent = message;
        list.appendChild(item);
      });
      wrap.appendChild(list);
      details.appendChild(wrap);
    }
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
      if (step.warnings && step.warnings.length) {
        const w = document.createElement("div");
        w.className = "warning-box step-warning";
        const t = document.createElement("div");
        t.className = "warning-title";
        t.textContent = "Warnung";
        w.appendChild(t);
        const ul = document.createElement("ul");
        ul.className = "warning-list";
        step.warnings.forEach((message) => {
          const li = document.createElement("li");
          li.textContent = message;
          ul.appendChild(li);
        });
        w.appendChild(ul);
        explanation.appendChild(w);
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
    const filtered = logEntries;
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
      const deleteButton=document.createElement("button");
      deleteButton.type="button"; deleteButton.className="small danger";
      deleteButton.textContent="Löschen";
      deleteButton.disabled=!entry.deletable;
      deleteButton.title=entry.deletable?"Diesen Logeintrag löschen":
        "Laufende oder wartende Aufträge können nicht als Log gelöscht werden";
      deleteButton.addEventListener("click",async(event)=>{
        event.stopPropagation();
        if(!confirm(`Log ${entry.job_id.slice(0,8)} wirklich löschen?`)) return;
        const response=await fetch(`/api/logs/${entry.job_id}`,{method:"DELETE"});
        if(!response.ok) {
          let detail=`HTTP ${response.status}`;
          try { detail=(await response.json()).detail||detail; } catch(error) {}
          alert(`Löschen fehlgeschlagen: ${detail}`); return;
        }
        logEntries=logEntries.filter((item)=>item.job_id!==entry.job_id);
        renderLogs();
      });
      row.cells[5].append(" ",deleteButton);
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
    empty.textContent = document.getElementById("log-search").value.trim() ?
      "Keine passenden Einträge gefunden." :
      "Noch keine Verarbeitungseinträge vorhanden.";
  }
  function renderInstances(instances) {
    if (logInstancesLoaded) return;
    const select = document.getElementById("log-instance");
    instances.forEach((instance) => {
      const option = document.createElement("option");
      option.value = instance.slug;
      option.textContent = `${instance.base_url} (${instance.name})`;
      select.appendChild(option);
    });
    logInstancesLoaded = true;
  }
  function updateLoadMoreButton() {
    let btn = document.getElementById("load-more");
    if (!btn) {
      btn = document.createElement("button");
      btn.id = "load-more"; btn.className = "btn";
      btn.textContent = "Mehr laden";
      btn.addEventListener("click", loadMoreLogs);
      document.getElementById("log-body").parentElement.after(btn);
    }
    btn.hidden = !nextCursor;
  }
  async function fetchLogs(cursor) {
    const instance = document.getElementById("log-instance").value;
    const params = new URLSearchParams({limit: "50"});
    if (instance) params.set("instance_slug", instance);
    const query=document.getElementById("log-search").value.trim();
    if(query) params.set("q",query);
    if (cursor) params.set("before", cursor);
    const response = await fetch(`/api/logs?${params.toString()}`,
      {headers:{"Accept":"application/json"},cache:"no-store"});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
  async function loadLogs() {
    const button = document.getElementById("refresh-logs");
    const empty = document.getElementById("log-empty");
    window.ezeusUI?.setBusy(button, true, "Lädt …");
    try {
      const payload = await fetchLogs(null);
      renderInstances(payload.instances);
      logEntries = payload.entries;
      nextCursor = payload.next_cursor;
      renderLogs();
      updateLoadMoreButton();
      document.getElementById("refresh-info").textContent =
        `Aktualisiert ${new Date().toLocaleTimeString("de-DE")}`;
    } catch (error) {
      empty.hidden = false; empty.className = "notice error";
      empty.textContent = `Logs konnten nicht geladen werden: ${error.message}`;
    } finally { window.ezeusUI?.setBusy(button, false); }
  }
  async function loadMoreLogs() {
    const btn = document.getElementById("load-more");
    if (!nextCursor) return;
    btn.disabled = true; btn.textContent = "Lädt …";
    try {
      const payload = await fetchLogs(nextCursor);
      logEntries = logEntries.concat(payload.entries);
      nextCursor = payload.next_cursor;
      renderLogs();
      updateLoadMoreButton();
    } catch (error) {
      btn.textContent = "Fehler – erneut versuchen";
    } finally { btn.disabled = false; if (nextCursor) btn.textContent = "Mehr laden"; }
  }
  document.getElementById("refresh-logs").addEventListener("click", loadLogs);
  document.getElementById("log-instance").addEventListener("change", loadLogs);
  let searchTimer=null;
  document.getElementById("log-search").addEventListener("input",()=>{
    clearTimeout(searchTimer); searchTimer=setTimeout(loadLogs,300);
  });
  document.getElementById("delete-visible-logs").addEventListener("click",async()=>{
    const ids=logEntries.filter((entry)=>entry.deletable).map((entry)=>entry.job_id);
    if(!ids.length) { alert("Keine abgeschlossenen Logeinträge zum Löschen geladen."); return; }
    if(!confirm(`${ids.length} geladene Logeinträge wirklich löschen?`)) return;
    for(const id of ids) {
      const response=await fetch(`/api/logs/${id}`,{method:"DELETE"});
      if(!response.ok) { alert(`Löschen bei ${id.slice(0,8)} abgebrochen.`); break; }
    }
    await loadLogs();
  });
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


DASHBOARD_SCRIPT_V2 = """
<script>
  const expandedJobIds = new Set();
  const selectedJobIds = new Set();
  const instanceStorageKey = "ezeus.log-instance";
  let logEntries = [];
  let logInstancesLoaded = false;
  let nextCursor = null;
  let currentPage = 0;
  let pageCursors = [null];
  let totalMatches = 0;
  let deletableMatches = 0;
  let selectAllMatching = false;
  let rememberedInstanceSlug = "";

  try { rememberedInstanceSlug = localStorage.getItem(instanceStorageKey) || ""; }
  catch (error) { rememberedInstanceSlug = ""; }

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
    if (value === "completed_with_warnings" || value === "cancelled") return "warning";
    if (value === "failed") return "danger";
    return "warning";
  }
  function currentInstanceSlug() {
    return logInstancesLoaded ?
      document.getElementById("log-instance").value : rememberedInstanceSlug;
  }
  function setDeleteInfo(message, tone = "info") {
    const info = document.getElementById("delete-info");
    info.hidden = !message; info.className = `notice ${tone} compact`;
    info.textContent = message || "";
  }
  function clearSelection() {
    selectedJobIds.clear(); selectAllMatching = false; updateSelectionUI();
  }
  function resetPagination() {
    currentPage = 0; pageCursors = [null]; nextCursor = null;
  }
  function selectedCount() {
    return selectAllMatching ? deletableMatches : selectedJobIds.size;
  }
  function updateSelectionUI() {
    const loadedDeletable = logEntries.filter((entry) => entry.deletable);
    const selectedLoaded = loadedDeletable.filter((entry) =>
      selectAllMatching || selectedJobIds.has(entry.job_id));
    const pageCheckbox = document.getElementById("select-page");
    pageCheckbox.checked = loadedDeletable.length > 0 &&
      selectedLoaded.length === loadedDeletable.length;
    pageCheckbox.indeterminate = selectedLoaded.length > 0 &&
      selectedLoaded.length < loadedDeletable.length;
    pageCheckbox.disabled = loadedDeletable.length === 0;
    const count = selectedCount();
    const button = document.getElementById("delete-selected-logs");
    button.textContent = `Ausgewählte löschen (${count})`; button.disabled = count === 0;
    const toolbar = document.getElementById("selection-toolbar");
    toolbar.hidden = count === 0;
    document.getElementById("selection-summary").textContent =
      selectAllMatching ? `${count} löschbare Treffer ausgewählt` : `${count} Einträge ausgewählt`;
    const allButton = document.getElementById("select-all-matches");
    const canOfferAll = !selectAllMatching && count > 0 && totalMatches > logEntries.length;
    allButton.hidden = !canOfferAll;
    allButton.textContent = `Alle ${totalMatches} Treffer auswählen`;
    document.querySelectorAll("input[data-job-select]").forEach((checkbox) => {
      checkbox.checked = selectAllMatching || selectedJobIds.has(checkbox.dataset.jobSelect);
    });
  }
  function appendExplanation(parent, explanation) {
    if (!explanation) return;
    const block = document.createElement("div"); block.className = "explanation-grid";
    appendText(block, "Was ist passiert", explanation.was, "explanation-item");
    appendText(block, "Warum", explanation.warum, "explanation-item");
    appendText(block, "Was tun", explanation.empfehlung, "explanation-item");
    const technical = document.createElement("details"); technical.className = "technical-details";
    const summary = document.createElement("summary"); summary.textContent = "Technische Details";
    const content = document.createElement("pre");
    content.textContent = explanation.technisch || "–";
    technical.append(summary, content); block.appendChild(technical); parent.appendChild(block);
  }
  function appendWarnings(parent, warnings, titleText) {
    if (!warnings || !warnings.length) return;
    const wrap = document.createElement("div"); wrap.className = "warning-box";
    const title = document.createElement("div"); title.className = "warning-title";
    title.textContent = `${titleText} (${warnings.length})`; wrap.appendChild(title);
    const list = document.createElement("ul"); list.className = "warning-list";
    warnings.forEach((warning) => {
      const item = document.createElement("li");
      const message = typeof warning === "string" ? warning : warning.message;
      item.textContent = message;
      if (typeof warning !== "string") {
        const detail = document.createElement("small");
        detail.textContent = `Grund: ${warning.reason} Hinweis: ${warning.hint}`;
        item.appendChild(document.createElement("br")); item.appendChild(detail);
      }
      list.appendChild(item);
    });
    wrap.appendChild(list); parent.appendChild(wrap);
  }
  function buildDetails(entry) {
    const detailRow = document.createElement("tr"); detailRow.className = "detail-row";
    const cell = document.createElement("td"); cell.colSpan = 7;
    const details = document.createElement("div"); details.className = "job-details";
    const summary = document.createElement("div"); summary.className = "detail-summary";
    appendText(summary, "Job-ID", entry.job_id);
    appendText(summary, "Paperless-Instanz", entry.instance_name || entry.connector);
    appendText(summary, "Dokument-ID", entry.document_id);
    appendText(summary, "Worker", entry.worker_id);
    appendText(summary, "Versuche", String(entry.retry_count + 1));
    appendText(summary, "Gesamtstatus", entry.status_label);
    details.appendChild(summary);
    appendWarnings(details, entry.warnings, "Hinweise");
    appendExplanation(details, entry.error_explanation);
    const steps = document.createElement("div"); steps.className = "steps";
    entry.steps.forEach((step, index) => {
      const element = document.createElement("div");
      element.className = `step ${step.status.toLowerCase()}`;
      const timing = document.createElement("div");
      appendText(timing, `Schritt ${index + 1}`, step.label, "step-label");
      appendText(timing, "Status", step.status_label, "step-label");
      appendText(timing, "Start", formatTime(step.started_at), "step-label");
      appendText(timing, "Dauer", formatDuration(step.duration_seconds), "step-label");
      const explanation = document.createElement("div");
      appendText(explanation, "Was ist passiert", step.description, "step-label");
      appendWarnings(explanation, step.warnings, "Hinweise");
      appendExplanation(explanation, step.error_explanation);
      if (step.metadata && Object.keys(step.metadata).length) {
        const technical = document.createElement("details");
        technical.className = "technical-details";
        const heading = document.createElement("summary"); heading.textContent = "Schrittdaten";
        const content = document.createElement("pre");
        content.textContent = Object.entries(step.metadata)
          .map(([key, value]) => `${key}: ${value ?? "–"}`).join("\\n");
        technical.append(heading, content); explanation.appendChild(technical);
      }
      element.append(timing, explanation); steps.appendChild(element);
    });
    details.appendChild(steps); cell.appendChild(details); detailRow.appendChild(cell);
    return detailRow;
  }
  function renderLogs() {
    const body = document.getElementById("log-body");
    const empty = document.getElementById("log-empty"); body.replaceChildren();
    logEntries.forEach((entry) => {
      const row = document.createElement("tr"); row.className = "job-row";
      row.tabIndex = 0; row.setAttribute("role", "button");
      const isExpanded = expandedJobIds.has(entry.job_id);
      row.setAttribute("aria-expanded", String(isExpanded));
      const selectCell = document.createElement("td"); selectCell.className = "selection-cell";
      const checkbox = document.createElement("input"); checkbox.type = "checkbox";
      checkbox.dataset.jobSelect = entry.job_id; checkbox.disabled = !entry.deletable;
      checkbox.title = entry.deletable ? "Diesen Eintrag auswählen" :
        "Laufende oder wartende Aufträge können nicht gelöscht werden";
      checkbox.setAttribute("aria-label", checkbox.title);
      checkbox.checked = selectAllMatching || selectedJobIds.has(entry.job_id);
      checkbox.addEventListener("click", (event) => event.stopPropagation());
      checkbox.addEventListener("change", () => {
        if (selectAllMatching) {
          selectAllMatching = false;
          selectedJobIds.clear();
          logEntries.filter((item) => item.deletable)
            .forEach((item) => selectedJobIds.add(item.job_id));
        }
        if (checkbox.checked) selectedJobIds.add(entry.job_id);
        else selectedJobIds.delete(entry.job_id);
        updateSelectionUI();
      });
      selectCell.appendChild(checkbox); row.appendChild(selectCell);
      const values = [isExpanded ? "−" : "+", formatTime(entry.started_at),
        `${entry.filename || "Unbekannt"} (Paperless ${entry.document_id})`,
        entry.status_label, formatDuration(entry.duration_seconds), entry.job_id.slice(0, 8)];
      values.forEach((value, index) => {
        const cell = document.createElement("td");
        if (index === 3) {
          const badge = document.createElement("span");
          badge.className = `status-badge ${statusTone(entry.status)}`; setText(badge, value);
          cell.appendChild(badge);
        } else { setText(cell, value); }
        row.appendChild(cell);
      });
      const detailRow = buildDetails(entry); detailRow.hidden = !isExpanded;
      const toggle = () => {
        detailRow.hidden = !detailRow.hidden;
        if (detailRow.hidden) expandedJobIds.delete(entry.job_id);
        else expandedJobIds.add(entry.job_id);
        row.cells[1].textContent = detailRow.hidden ? "+" : "−";
        row.setAttribute("aria-expanded", String(!detailRow.hidden));
      };
      row.addEventListener("click", toggle);
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle(); }
      });
      body.append(row, detailRow);
    });
    empty.className = "empty-state"; empty.hidden = logEntries.length > 0;
    empty.textContent = document.getElementById("log-search").value.trim() ?
      "Keine passenden Einträge gefunden." : "Noch keine Verarbeitungseinträge vorhanden.";
    updateSelectionUI();
  }
  function renderInstances(instances) {
    if (logInstancesLoaded) return;
    const select = document.getElementById("log-instance");
    instances.forEach((instance) => {
      const option = document.createElement("option"); option.value = instance.slug;
      option.textContent = `${instance.base_url} (${instance.name})`; select.appendChild(option);
    });
    logInstancesLoaded = true;
    const rememberedExists = [...select.options]
      .some((option) => option.value === rememberedInstanceSlug);
    if (rememberedInstanceSlug && rememberedExists) {
      select.value = rememberedInstanceSlug;
    }
  }
  function updatePaginationControls() {
    const previous = document.getElementById("previous-page");
    const next = document.getElementById("next-page");
    previous.disabled = currentPage === 0;
    next.disabled = !nextCursor;
    const first = totalMatches ? currentPage * 50 + 1 : 0;
    const last = totalMatches ? Math.min(currentPage * 50 + logEntries.length, totalMatches) : 0;
    document.getElementById("page-info").textContent =
      `Seite ${currentPage + 1} · Einträge ${first}–${last} von ${totalMatches}`;
  }
  async function fetchLogs(cursor) {
    const params = new URLSearchParams({limit: "50"});
    const instance = currentInstanceSlug(); if (instance) params.set("instance_slug", instance);
    const query = document.getElementById("log-search").value.trim();
    if (query) params.set("q", query); if (cursor) params.set("before", cursor);
    const response = await fetch(`/api/logs?${params.toString()}`,
      {headers: {"Accept": "application/json"}, cache: "no-store"});
    if (!response.ok) {
      const error = new Error(`HTTP ${response.status}`);
      error.status = response.status; throw error;
    }
    return response.json();
  }
  async function loadLogs(allowInstanceFallback = true) {
    const button = document.getElementById("refresh-logs");
    const empty = document.getElementById("log-empty");
    window.ezeusUI?.setBusy(button, true, "Lädt …");
    try {
      const payload = await fetchLogs(pageCursors[currentPage]);
      renderInstances(payload.instances);
      logEntries = payload.entries; nextCursor = payload.next_cursor;
      totalMatches = payload.total; deletableMatches = payload.deletable_total;
      if (!logEntries.length && currentPage > 0) {
        pageCursors = pageCursors.slice(0, currentPage);
        currentPage -= 1;
        await loadLogs(allowInstanceFallback);
        return;
      }
      renderLogs(); updatePaginationControls();
      document.getElementById("refresh-info").textContent =
        `Aktualisiert ${new Date().toLocaleTimeString("de-DE")}`;
    } catch (error) {
      if (error.status === 404 && allowInstanceFallback && currentInstanceSlug()) {
        rememberedInstanceSlug = "";
        resetPagination(); clearSelection();
        try { localStorage.removeItem(instanceStorageKey); } catch (storageError) {}
        if (logInstancesLoaded) document.getElementById("log-instance").value = "";
        setDeleteInfo(
          "Die gespeicherte Instanz existiert nicht mehr. Es werden alle Instanzen angezeigt.",
          "warning");
        await loadLogs(false); return;
      }
      empty.hidden = false; empty.className = "notice error";
      empty.textContent = `Logs konnten nicht geladen werden: ${error.message}`;
    } finally { window.ezeusUI?.setBusy(button, false); }
  }
  async function goToPage(direction) {
    const targetPage = currentPage + direction;
    if (targetPage < 0 || (direction > 0 && !nextCursor)) return;
    if (direction > 0) pageCursors[targetPage] = nextCursor;
    currentPage = targetPage;
    clearSelection();
    await loadLogs();
  }
  document.getElementById("refresh-logs").addEventListener("click", () => loadLogs());
  document.getElementById("previous-page").addEventListener("click", () => goToPage(-1));
  document.getElementById("next-page").addEventListener("click", () => goToPage(1));
  document.getElementById("log-instance").addEventListener("change", (event) => {
    clearSelection(); resetPagination(); rememberedInstanceSlug = event.target.value;
    try {
      if (rememberedInstanceSlug) localStorage.setItem(instanceStorageKey, rememberedInstanceSlug);
      else localStorage.removeItem(instanceStorageKey);
    } catch (error) {}
    loadLogs();
  });
  let searchTimer = null;
  document.getElementById("log-search").addEventListener("input", () => {
    clearSelection(); resetPagination(); clearTimeout(searchTimer);
    searchTimer = setTimeout(() => loadLogs(), 300);
  });
  document.getElementById("select-page").addEventListener("change", (event) => {
    selectAllMatching = false;
    logEntries.filter((entry) => entry.deletable).forEach((entry) => {
      if (event.target.checked) selectedJobIds.add(entry.job_id);
      else selectedJobIds.delete(entry.job_id);
    });
    updateSelectionUI();
  });
  document.getElementById("select-all-matches").addEventListener("click", () => {
    selectAllMatching = true; selectedJobIds.clear(); updateSelectionUI();
  });
  document.getElementById("delete-selected-logs").addEventListener("click", async () => {
    const count = selectedCount(); if (!count) return;
    const select = document.getElementById("log-instance");
    const instanceLabel = select.value ?
      select.options[select.selectedIndex].textContent : "Alle Instanzen";
    const confirmation = `${count} ausgewählte Logeinträge für ` +
      `„${instanceLabel}“ wirklich löschen?`;
    if (!confirm(confirmation)) return;
    const query = document.getElementById("log-search").value.trim();
    const endpoint = selectAllMatching ? "/api/logs/delete-matching" : "/api/logs/delete";
    const body = selectAllMatching ? {instance_slug: select.value || null, q: query || null} :
      {job_ids: [...selectedJobIds]};
    const response = await fetch(endpoint, {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
    });
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try { detail = (await response.json()).detail || detail; } catch (error) {}
      setDeleteInfo(`Löschen fehlgeschlagen: ${detail}`, "error"); return;
    }
    const result = await response.json(); clearSelection();
    setDeleteInfo(`${result.deleted} gelöscht, ${result.skipped} übersprungen`, "success");
    await loadLogs();
  });
  fetch("/ready", {cache: "no-store"}).then((response) => {
    if (!response.ok) throw new Error();
    document.getElementById("api-dot").classList.add("ok");
    document.getElementById("api-status").textContent = "Bereit";
    document.getElementById("api-note").textContent = "Alle Komponenten erreichbar";
  }).catch(() => {
    document.getElementById("api-status").textContent = "Nicht bereit";
    document.getElementById("api-note").textContent = "Bereitschaftsprüfung fehlgeschlagen";
  });
  loadLogs(); setInterval(() => loadLogs(), 10000);
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
        script=DASHBOARD_SCRIPT_V2,
    )


def _filtered_jobs_query(
    db: Session,
    *,
    instance_slug: str | None,
    q: str | None,
) -> tuple[Select[tuple[Job]], list[PaperlessInstance]]:
    instances = list(
        db.scalars(
            select(PaperlessInstance)
            .where(PaperlessInstance.deleted_at.is_(None))
            .order_by(PaperlessInstance.base_url)
        ).all()
    )
    instances_by_slug = {instance.slug: instance for instance in instances}
    jobs_query = select(Job).join(Document)
    if instance_slug:
        if instance_slug not in instances_by_slug:
            raise HTTPException(status_code=404, detail="Paperless-Instanz nicht gefunden")
        jobs_query = jobs_query.where(Document.connector == f"paperless:{instance_slug}")
    if q and (search_term := q.strip()):
        normalized = search_term.lower()
        pattern = f"%{normalized}%"
        matching_connectors = [
            f"paperless:{instance.slug}"
            for instance in instances
            if normalized in instance.name.lower() or normalized in instance.slug.lower()
        ]
        matching_statuses = [
            job_status for job_status, label in STATUS_LABELS.items() if normalized in label.lower()
        ]
        matching_phases = [
            phase_name for phase_name, label in PHASE_LABELS.items() if normalized in label.lower()
        ]
        conditions = [
            func.lower(func.coalesce(Document.filename, "")).like(pattern),
            func.lower(Document.external_document_id).like(pattern),
            func.lower(Document.connector).like(pattern),
            func.lower(cast(Job.id, String)).like(pattern),
            func.lower(cast(Job.status, String)).like(pattern),
            func.lower(func.coalesce(Job.error_type, "")).like(pattern),
        ]
        if matching_connectors:
            conditions.append(Document.connector.in_(matching_connectors))
        if matching_statuses:
            conditions.append(Job.status.in_(matching_statuses))
        if matching_phases:
            conditions.append(
                Job.id.in_(
                    select(JobPhaseEntry.job_id).where(JobPhaseEntry.phase.in_(matching_phases))
                )
            )
        jobs_query = jobs_query.where(or_(*conditions))
    return jobs_query, instances


@router.get("/api/logs", dependencies=[Depends(require_admin_user)])
def processing_logs(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    instance_slug: Annotated[str | None, Query(max_length=64)] = None,
    before: Annotated[str | None, Query(max_length=80)] = None,
    q: Annotated[str | None, Query(max_length=255)] = None,
) -> dict[str, object]:
    jobs_query, instances = _filtered_jobs_query(
        db,
        instance_slug=instance_slug,
        q=q,
    )
    total = db.scalar(select(func.count()).select_from(jobs_query.subquery())) or 0
    deletable_total = (
        db.scalar(
            select(func.count()).select_from(
                jobs_query.where(Job.status.in_(TERMINAL_STATUSES)).subquery()
            )
        )
        or 0
    )
    if before:
        try:
            cursor_timestamp, cursor_id_value = before.rsplit("|", 1)
            cursor_time = datetime.fromisoformat(cursor_timestamp)
            cursor_id = UUID(cursor_id_value)
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="Invalid 'before' cursor format") from None
        jobs_query = jobs_query.where(
            or_(
                Job.created_at < cursor_time,
                and_(Job.created_at == cursor_time, Job.id < cursor_id),
            )
        )
    jobs = db.scalars(
        jobs_query.order_by(Job.created_at.desc(), Job.id.desc()).limit(limit + 1)
    ).all()
    has_more = len(jobs) > limit
    if has_more:
        jobs = jobs[:limit]
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

    instance_names = {instance.slug: instance.name for instance in instances}
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
        slug = instance_slug_from_connector(document.connector)
        steps: list[dict[str, object]] = []
        for phase_entry in phase_entries:
            phase_finished_at = phase_entry.finished_at
            phase_name = phase_entry.phase.value
            error = phase_entry.error
            if error and job.error_message:
                error = redact_sensitive_text(f"{error}: {job.error_message}")
            step_metadata = {
                k: _redact_display_value(k, v) for k, v in (phase_entry.metadata_json or {}).items()
            }
            step_warnings = derive_step_warnings(phase_name, step_metadata)
            step_error_explanation = (
                explain_error(
                    job.error_type or error,
                    job.error_message or error,
                    phase_name,
                    document_id=document.external_document_id,
                    field=str(step_metadata.get("field") or step_metadata.get("field_id") or "")
                    or None,
                )
                if error
                else None
            )
            steps.append(
                {
                    "phase": phase_name,
                    "label": PHASE_LABELS.get(phase_name, "Unbekannter Verarbeitungsschritt"),
                    "description": PHASE_DESCRIPTIONS.get(
                        phase_name, "Verarbeitungsschritt ausgeführt."
                    ),
                    "status": phase_entry.status.value,
                    "status_label": PHASE_STATUS_LABELS.get(
                        phase_entry.status.value, "Unbekannter Status"
                    ),
                    "started_at": phase_entry.started_at.isoformat(),
                    "finished_at": (phase_finished_at.isoformat() if phase_finished_at else None),
                    "duration_seconds": round(
                        elapsed_seconds(phase_entry.started_at, phase_finished_at, now),
                        3,
                    ),
                    "metadata": step_metadata,
                    "warnings": step_warnings,
                    "error": error,
                    "error_explanation": step_error_explanation,
                }
            )
        job_warnings: list[dict[str, str]] = []
        for step in steps:
            raw_step_warnings = step.get("warnings")
            if isinstance(raw_step_warnings, list):
                job_warnings.extend(raw_step_warnings)
        error_phase = (
            job.phase.value
            if job.phase
            else (phase_entries[-1].phase.value if phase_entries else "")
        )
        job_error_explanation = (
            explain_error(
                job.error_type,
                job.error_message,
                error_phase,
                document_id=document.external_document_id,
            )
            if job.error_type or job.error_message
            else None
        )
        entries.append(
            {
                "job_id": str(job.id),
                "document_id": document.external_document_id,
                "filename": document.filename,
                "connector": document.connector,
                "instance_name": instance_names.get(slug) if slug else "Legacy-Konfiguration",
                "status": job.status.value,
                "status_label": STATUS_LABELS.get(job.status, "Unbekannter Status"),
                "started_at": started_at.isoformat(),
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                "duration_seconds": round(elapsed_seconds(started_at, finished_at, now), 1),
                "error_type": job.error_type,
                "error_message": (
                    redact_sensitive_text(job.error_message) if job.error_message else None
                ),
                "error_explanation": job_error_explanation,
                "worker_id": job.worker_id,
                "retry_count": job.retry_count,
                "deletable": job.status in TERMINAL_STATUSES,
                "warnings": job_warnings,
                "steps": steps,
            }
        )
    next_cursor = f"{jobs[-1].created_at.isoformat()}|{jobs[-1].id}" if has_more and jobs else None
    return {
        "entries": entries,
        "total": total,
        "deletable_total": deletable_total,
        "has_more": has_more,
        "next_cursor": next_cursor,
        "instances": [
            {
                "slug": instance.slug,
                "name": instance.name,
                "base_url": instance.base_url,
            }
            for instance in instances
        ],
        "generated_at": now.isoformat(),
    }


def _delete_log_jobs(
    db: Session,
    *,
    principal: AdminPrincipal,
    requested_ids: list[UUID],
    action: str,
    filters: dict[str, object],
) -> dict[str, int]:
    unique_ids = list(dict.fromkeys(requested_ids))
    jobs = list(db.scalars(select(Job).where(Job.id.in_(unique_ids))).all()) if unique_ids else []
    deletable_ids = [job.id for job in jobs if job.status in TERMINAL_STATUSES]
    skipped = len(unique_ids) - len(deletable_ids)
    db.add(
        AuditEntry(
            actor=principal.username,
            action=action,
            entity_type="job_log_selection",
            entity_id="matching-filter" if filters else "explicit-selection",
            details={
                "requested": len(unique_ids),
                "deleted": len(deletable_ids),
                "skipped": skipped,
                "filters": filters,
                "retention": "manual",
            },
        )
    )
    for start in range(0, len(deletable_ids), DELETE_BATCH_SIZE):
        delete_jobs(db, deletable_ids[start : start + DELETE_BATCH_SIZE])
    db.commit()
    return {"deleted": len(deletable_ids), "skipped": skipped}


@router.post("/api/logs/delete")
def delete_selected_processing_logs(
    payload: DeleteLogsRequest,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[AdminPrincipal, Depends(require_admin_secret)],
) -> dict[str, int]:
    return _delete_log_jobs(
        db,
        principal=principal,
        requested_ids=payload.job_ids,
        action="DELETE_PROCESSING_LOGS",
        filters={},
    )


@router.post("/api/logs/delete-matching")
def delete_matching_processing_logs(
    payload: DeleteMatchingLogsRequest,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[AdminPrincipal, Depends(require_admin_secret)],
) -> dict[str, int]:
    jobs_query, _instances = _filtered_jobs_query(
        db,
        instance_slug=payload.instance_slug,
        q=payload.q,
    )
    requested_ids = list(db.scalars(jobs_query.with_only_columns(Job.id)).all())
    return _delete_log_jobs(
        db,
        principal=principal,
        requested_ids=requested_ids,
        action="DELETE_MATCHING_PROCESSING_LOGS",
        filters={"instance_slug": payload.instance_slug, "q": payload.q},
    )


@router.delete("/api/logs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_processing_log(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[AdminPrincipal, Depends(require_admin_secret)],
) -> None:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Logeintrag nicht gefunden")
    if job.status not in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Laufende oder wartende Aufträge können nicht als Log gelöscht werden",
        )
    db.add(
        AuditEntry(
            actor=principal.username,
            action="DELETE_PROCESSING_LOG",
            entity_type="job",
            entity_id=str(job.id),
            old_value={"status": job.status.value},
            details={"retention": "manual"},
        )
    )
    delete_jobs(db, [job.id])
    db.commit()
