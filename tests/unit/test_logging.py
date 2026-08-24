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
