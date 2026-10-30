import json
import logging

from core.logging import JSONFormatter


def test_json_formatter_emits_structured_job_context() -> None:
    record = logging.LogRecord(
        name="core.orchestration.orchestrator",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Phase started",
        args=(),
        exc_info=None,
    )
    record.job_id = "job-123"
    record.instance_slug = "tenant-a"
    record.phase = "LOAD_DOCUMENT"

    payload = json.loads(JSONFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["message"] == "Phase started"
    assert payload["job_id"] == "job-123"
    assert payload["instance_slug"] == "tenant-a"
    assert payload["phase"] == "LOAD_DOCUMENT"


def test_json_formatter_redacts_secrets_from_message_and_exception() -> None:
    try:
        raise RuntimeError("Authorization: Bearer top-secret-token")
    except RuntimeError as exc:
        record = logging.LogRecord(
            name="core.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=30,
            msg="Anfrage fehlgeschlagen: token=top-secret-token",
            args=(),
            exc_info=(type(exc), exc, exc.__traceback__),
        )

    payload = json.loads(JSONFormatter().format(record))
    rendered = json.dumps(payload)
    assert "top-secret-token" not in rendered
    assert "[REDACTED]" in rendered
