"""Failures while processing a document must be diagnosable from logs and job records."""

import json
import logging
from collections.abc import Iterator
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.api.dashboard import derive_step_warnings, explain_error
from apps.worker.tasks import _claim_job
from connectors.base.errors import ConnectionError as ConnectorConnectionError
from connectors.base.errors import ConnectorError
from connectors.base.errors import TimeoutError as ConnectorTimeoutError
from connectors.base.errors import ValidationError as ConnectorValidationError
from connectors.base.interface import (
    ConnectorCorrespondent,
    ConnectorCustomField,
    ConnectorDocument,
    DocumentConnector,
)
from connectors.paperless.connector import PaperlessConnector
from core.config.settings import Settings
from core.db.base import Base
from core.logging import JSONFormatter, bind_log_context, describe_exception, log_context
from core.models.document import Document
from core.models.enums import JobPhase, JobStatus
from core.models.job import Job
from core.models.job_phase import JobPhaseEntry
from core.orchestration.orchestrator import Orchestrator
from core.queue.sweeper import sweep_stale_jobs
from plugins.llm.metadata import OllamaMetadataProvider
from plugins.llm.ollama import OllamaExtractionProvider
from webhooks.paperless.router import _verify_instance_trigger
from webhooks.paperless.schemas import PaperlessWebhookPayload


class _JSONCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.setFormatter(JSONFormatter())
        self.entries: list[dict[str, object]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.entries.append(json.loads(self.format(record)))

    def matching(self, text: str) -> dict[str, object]:
        return next(entry for entry in self.entries if text in str(entry["message"]))


@pytest.fixture(autouse=True)
def _resolvable_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.security.outbound.resolve_hosts", lambda _host: ["203.0.113.10"])


@pytest.fixture
def logs() -> Iterator[_JSONCapture]:
    handler = _JSONCapture()
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    yield handler
    root.removeHandler(handler)
    root.setLevel(previous_level)


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _job(db: Session, *, status: JobStatus = JobStatus.QUEUED) -> Job:
    document = Document(
        connector="paperless:test", external_document_id="4711", filename="rechnung.pdf"
    )
    job = Job(document=document, status=status, worker_id="worker-1")
    db.add(job)
    db.commit()
    return job


class _Connector(DocumentConnector):
    """Serves one invoice; each write fails with the configured error."""

    def __init__(self, write_error: Exception | None = None) -> None:
        self.write_error = write_error
        self.closed = False

    async def close(self) -> None:
        self.closed = True

    async def health_check(self) -> bool:
        return True

    async def get_document(self, external_document_id: str) -> ConnectorDocument:
        return ConnectorDocument(
            external_id=external_document_id,
            filename="rechnung.pdf",
            mime_type="application/pdf",
            content="Rechnungsnummer: RE-123\nGesamtbetrag: 123,45 EUR",
            custom_fields={"10": None},
        )

    async def list_custom_fields(self) -> list[ConnectorCustomField]:
        return [ConnectorCustomField("10", "Rechnungsnummer", "string")]

    async def list_correspondents(self) -> list[ConnectorCorrespondent]:
        return [ConnectorCorrespondent("99", "(noch nicht angelegt)", "", 0, True)]

    async def write_correspondent_if_empty(
        self, document: ConnectorDocument, correspondent_id: str
    ) -> bool:
        return True

    async def write_title(self, document: ConnectorDocument, title: str) -> bool:
        return True

    async def write_empty_fields(
        self, document: ConnectorDocument, values: dict[str, object]
    ) -> dict[str, object]:
        if self.write_error is not None:
            raise self.write_error
        return values


# --- log formatter ------------------------------------------------------------------


def test_formatter_emits_extras_context_and_traceback(logs: _JSONCapture) -> None:
    logger = logging.getLogger("tests.diagnostics")
    with log_context(job_id="job-1", document_id="4711"):
        bind_log_context(phase="WRITE_METADATA")
        try:
            raise RuntimeError("field rejected")
        except RuntimeError as exc:
            logger.warning("failed", exc_info=exc, extra={"field_id": "10"})
    logger.info("outside")

    entry = logs.matching("failed")
    assert entry["job_id"] == "job-1"
    assert entry["document_id"] == "4711"
    assert entry["phase"] == "WRITE_METADATA"
    assert entry["field_id"] == "10"
    assert entry["exception_type"] == "RuntimeError"
    assert entry["exception"] == "field rejected"
    assert 'raise RuntimeError("field rejected")' in str(entry["traceback"])
    assert "job_id" not in logs.matching("outside")


def test_formatter_redacts_extras_and_traceback(logs: _JSONCapture) -> None:
    try:
        raise RuntimeError("Authorization: Bearer top-secret-token")
    except RuntimeError as exc:
        logging.getLogger("tests.diagnostics").error(
            "failed", exc_info=exc, extra={"url": "https://user:top-secret-token@host/?token=abc"}
        )

    rendered = json.dumps(logs.matching("failed"))
    assert "top-secret-token" not in rendered
    assert "token=abc" not in rendered


def test_exception_without_message_is_still_described() -> None:
    assert describe_exception(httpx.ReadTimeout("")) == "ReadTimeout (no message)"

    wrapped = ConnectorError()
    wrapped.__cause__ = httpx.ReadTimeout("")
    wrapped.add_note("field=invoice_number")
    assert describe_exception(wrapped) == (
        "ConnectorError (no message), caused by ReadTimeout: ReadTimeout (no message)"
        " | field=invoice_number"
    )


# --- Paperless connector ------------------------------------------------------------


def _paperless(handler: object) -> PaperlessConnector:
    connector = PaperlessConnector(base_url="https://paperless.example.test", api_token="t")
    connector._settings = Settings(outbound_block_private_networks=False)
    connector._http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
        base_url=connector.base_url,
    )
    return connector


@pytest.mark.asyncio
async def test_paperless_rejection_says_what_paperless_objected_to() -> None:
    connector = _paperless(
        lambda _request: httpx.Response(
            400, json={"custom_fields": [{"value": ["Enter a valid boolean."]}]}
        )
    )
    document = ConnectorDocument(external_id="4711", custom_fields={})

    with pytest.raises(ConnectorValidationError) as exc_info:
        await connector.write_empty_fields(document, {"10": "Ja"})

    message = str(exc_info.value)
    assert "PATCH" in message
    assert "/api/documents/4711/" in message
    assert "Enter a valid boolean." in message


@pytest.mark.asyncio
async def test_paperless_server_error_names_request_and_response() -> None:
    connector = _paperless(lambda _request: httpx.Response(502, text="<h1>Bad Gateway</h1>"))

    with pytest.raises(ConnectorConnectionError) as exc_info:
        await connector.get_document("4711")

    assert exc_info.value.retryable
    assert "HTTP 502 from GET" in str(exc_info.value)
    assert "Bad Gateway" in str(exc_info.value)


@pytest.mark.asyncio
async def test_paperless_timeout_message_is_never_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("", request=request)

    with pytest.raises(ConnectorTimeoutError) as exc_info:
        await _paperless(handler).get_document("4711")

    assert "GET" in str(exc_info.value)
    assert "ReadTimeout" in str(exc_info.value)


@pytest.mark.asyncio
async def test_paperless_redirect_names_its_target() -> None:
    connector = _paperless(
        lambda _request: httpx.Response(302, headers={"location": "https://login.example.test/"})
    )

    with pytest.raises(ConnectorValidationError, match=r"redirect to https://login.example.test/"):
        await connector.get_document("4711")


@pytest.mark.asyncio
async def test_paperless_non_json_answer_names_request_and_content_type() -> None:
    connector = _paperless(
        lambda _request: httpx.Response(
            200, text="<html>Login</html>", headers={"content-type": "text/html"}
        )
    )

    with pytest.raises(ConnectorValidationError) as exc_info:
        await connector.get_document("4711")

    assert "/api/documents/4711/" in str(exc_info.value)
    assert "text/html" in str(exc_info.value)


# --- Ollama -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ollama_http_error_includes_ollamas_own_message() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(404, json={"error": "model 'x' not found"})
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://ollama:11434") as client:
        provider = OllamaExtractionProvider(client=client, model="x")
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await provider.extract("Text", {"field_name": "Rechnungsnummer"})

    description = describe_exception(exc_info.value)
    assert "model=x" in description
    assert "model 'x' not found" in description


@pytest.mark.asyncio
async def test_ollama_truncated_answer_reports_reason_without_document_text() -> None:
    truncated = '{"title": "Rechnung der Geheim GmbH'
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200, json={"message": {"content": truncated}, "done_reason": "length"}
        )
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://ollama:11434") as client:
        provider = OllamaMetadataProvider(client=client, model="x")
        with pytest.raises(ValueError) as exc_info:
            await provider.suggest_title("Text")

    assert "done_reason=length" in str(exc_info.value)
    assert "Geheim" not in str(exc_info.value)


# --- orchestrator -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connector_setup_failure_is_recorded_on_the_job(
    db: Session, logs: _JSONCapture
) -> None:
    job = _job(db)

    with (
        patch(
            "core.orchestration.orchestrator.connector_for_document",
            side_effect=ValueError("Paperless instance is unavailable (disabled or deleted): test"),
        ),
        pytest.raises(ValueError),
    ):
        await Orchestrator(db).process(job.id)

    db.refresh(job)
    assert job.status == JobStatus.FAILED
    assert job.error_type == "ValueError"
    assert "disabled or deleted" in str(job.error_message)
    assert job.finished_at is not None
    entry = logs.matching("Verarbeitungsversuch fehlgeschlagen")
    assert entry["job_id"] == str(job.id)
    assert entry["document_id"] == "4711"
    assert "keine automatische Wiederholung" in str(entry["message"])


@pytest.mark.asyncio
async def test_failure_message_names_field_and_provider(db: Session, logs: _JSONCapture) -> None:
    job = _job(db)
    orchestrator = Orchestrator(db)
    orchestrator.connector = _Connector()

    with (
        patch(
            "plugins.extraction.regex.RegexExtractionProvider.extract",
            side_effect=TimeoutError(),
        ),
        pytest.raises(TimeoutError),
    ):
        await orchestrator.process(job.id)

    db.refresh(job)
    assert job.error_message is not None
    assert "TimeoutError (no message)" in job.error_message
    assert "field=" in job.error_message
    assert "provider=regex" in job.error_message
    entry = logs.matching("Verarbeitungsversuch fehlgeschlagen")
    assert entry["phase"] == JobPhase.EXTRACT_FIELDS.value
    assert entry["error_type"] == "TimeoutError"


@pytest.mark.asyncio
async def test_retryable_failure_does_not_claim_processing_ended(
    db: Session, logs: _JSONCapture
) -> None:
    class _Unavailable(_Connector):
        async def get_document(self, external_document_id: str) -> ConnectorDocument:
            raise ConnectorConnectionError("Paperless server error: HTTP 503")

    job = _job(db)
    orchestrator = Orchestrator(db)
    orchestrator.connector = _Unavailable()

    with pytest.raises(ConnectorConnectionError):
        await orchestrator.process(job.id)

    entry = logs.matching("Verarbeitungsversuch fehlgeschlagen")
    assert entry["retryable"] is True
    assert "automatische Wiederholung" in str(entry["message"])
    assert "keine automatische" not in str(entry["message"])


@pytest.mark.asyncio
async def test_failed_status_update_does_not_hide_the_original_error(
    db: Session, logs: _JSONCapture
) -> None:
    class _Unavailable(_Connector):
        async def get_document(self, external_document_id: str) -> ConnectorDocument:
            raise ConnectorConnectionError("Paperless server error: HTTP 503")

    job = _job(db)
    orchestrator = Orchestrator(db)
    orchestrator.connector = _Unavailable()

    with (
        patch.object(orchestrator, "_finish_phase", side_effect=RuntimeError("database is down")),
        pytest.raises(ConnectorConnectionError),
    ):
        await orchestrator.process(job.id)

    assert "HTTP 503" in str(logs.matching("Verarbeitungsversuch fehlgeschlagen")["message"])
    assert logs.matching("Fehlerstatus konnte nicht gespeichert")["exception"] == (
        "database is down"
    )


@pytest.mark.asyncio
async def test_swallowed_write_failure_is_visible_in_log_and_phase(
    db: Session, logs: _JSONCapture
) -> None:
    job = _job(db)
    orchestrator = Orchestrator(db)
    orchestrator.connector = _Connector(
        write_error=ConnectorValidationError("Paperless rejected the request: HTTP 400")
    )

    await orchestrator.process(job.id)

    entry = logs.matching("Benutzerdefiniertes Feld 10")
    assert entry["job_id"] == str(job.id)
    assert entry["phase"] == JobPhase.WRITE_METADATA.value
    assert entry["field_id"] == "10"
    assert entry["error_type"] == "ValidationError"
    assert "HTTP 400" in str(entry["message"])
    assert "traceback" in entry
    assert "custom_field_write" in str(logs.matching("Metadaten-Schritte")["message"])

    phase = db.query(JobPhaseEntry).filter_by(job_id=job.id, phase=JobPhase.WRITE_METADATA).one()
    problems = phase.metadata_json["problems"]
    assert problems[0]["step"] == "custom_field_write"
    assert problems[0]["field_id"] == "10"
    warnings = derive_step_warnings("WRITE_METADATA", phase.metadata_json)
    assert "custom_field_write (ValidationError)" in warnings[0]["message"]
    assert "HTTP 400" in warnings[0]["reason"]


# --- worker, sweeper, webhook guard, dashboard ----------------------------------------


def test_claim_logs_why_a_delivery_is_skipped(db: Session, logs: _JSONCapture) -> None:
    job = _job(db, status=JobStatus.COMPLETED)

    assert not _claim_job(db, job.id, "worker-2")
    assert not _claim_job(db, uuid4(), "worker-2")

    assert "COMPLETED" in str(logs.matching("erlaubt keine Übernahme")["message"])
    assert logs.matching("nicht in der Datenbank")["level"] == "WARNING"


def test_claim_warns_when_recovering_an_interrupted_job(db: Session, logs: _JSONCapture) -> None:
    job = _job(db, status=JobStatus.RUNNING)

    assert _claim_job(db, job.id, "worker-2", redelivered=True)

    assert "worker-1" in str(logs.matching("erneuter Zustellung")["message"])


def test_sweeper_reports_real_state_and_keeps_the_previous_error(
    db: Session, logs: _JSONCapture
) -> None:
    job = _job(db, status=JobStatus.RUNNING)
    job.phase = JobPhase.EXTRACT_FIELDS
    job.retry_count = 3
    job.error_type = "ConnectionError"
    job.error_message = "Paperless server error: HTTP 503"
    db.commit()

    with patch("core.queue.sweeper.get_settings") as settings:
        settings.return_value.sweeper_stale_threshold_seconds = -1
        settings.return_value.job_max_retries = 3
        result = sweep_stale_jobs(db)

    assert result.failed == 1
    db.refresh(job)
    assert job.status == JobStatus.FAILED
    assert job.error_message is not None
    assert "stalled in RUNNING at phase EXTRACT_FIELDS" in job.error_message
    assert "previous error: ConnectionError: Paperless server error: HTTP 503" in job.error_message
    assert "gave up after 3 retries" in job.error_message
    entry = logs.matching("endgültig beendet")
    assert entry["level"] == "ERROR"
    assert entry["job_id"] == str(job.id)


@pytest.mark.asyncio
async def test_rejected_ocr_webhook_logs_tags_needed_to_diagnose_it(
    logs: _JSONCapture, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import asynccontextmanager

    from core.models.paperless_instance import PaperlessInstance

    class _TagConnector:
        async def get_document(self, document_id: str) -> ConnectorDocument:
            return ConnectorDocument(external_id=document_id, tag_ids=frozenset({"52", "53"}))

        async def find_tag(self, name: str) -> dict[str, object]:
            return {"id": {"OCR fertig": 52, "OCR verarbeitet": 53}[name], "name": name}

    @asynccontextmanager
    async def factory(_instance: PaperlessInstance):  # type: ignore[no-untyped-def]
        yield _TagConnector()

    monkeypatch.setattr("webhooks.paperless.router.connector_for_instance", factory)
    instance = PaperlessInstance(
        name="Pilot",
        slug="pilot",
        ocr_handoff_enabled=True,
        ocr_complete_tag_name="OCR fertig",
        ocr_triggered_tag_name="OCR verarbeitet",
    )

    with pytest.raises(HTTPException) as exc_info:
        await _verify_instance_trigger(
            instance, PaperlessWebhookPayload(document_id=257), "ocr-complete"
        )

    assert exc_info.value.status_code == 409
    entry = logs.matching("Webhook 409: Bedingung")
    assert entry["document_id"] == "257"
    assert entry["trigger"] == "ocr-complete"
    assert "OCR verarbeitet" in str(entry["forbidden_tags"])
    assert "53" in str(entry["document_tag_ids"])


@pytest.mark.asyncio
async def test_disabled_trigger_rejection_is_logged(logs: _JSONCapture) -> None:
    from core.models.paperless_instance import PaperlessInstance

    instance = PaperlessInstance(name="Pilot", slug="pilot", manual_reprocess_enabled=False)

    with pytest.raises(HTTPException):
        await _verify_instance_trigger(instance, PaperlessWebhookPayload(document_id=257), "manual")

    assert logs.matching("Manual reprocessing is disabled")["document_id"] == "257"


def test_dashboard_does_not_promise_a_retry_for_a_finished_job() -> None:
    assert (
        "wiederholt den Vorgang" in explain_error("StalledJob", "stalled", "LOAD_DOCUMENT")["warum"]
    )
    explanation = explain_error("StalledJob", "stalled", "LOAD_DOCUMENT", retries_ended=True)
    assert "wiederholt den Vorgang" not in explanation["warum"]
    assert "nicht mehr automatisch" in explanation["warum"]
