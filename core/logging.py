import json
import logging
import sys
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from core.security.redaction import redact_sensitive_text

_STANDARD_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}
_PROTECTED_ENTRY_FIELDS = frozenset(
    {"timestamp", "level", "logger", "message", "exception_type", "exception", "traceback"}
)
_MAX_EXTRA_VALUE_CHARS = 1000
_MAX_TRACEBACK_CHARS = 12000

_log_context: ContextVar[dict[str, object] | None] = ContextVar("ezeus_log_context", default=None)


@contextmanager
def log_context(**fields: object) -> Iterator[None]:
    """Attach fields to every log record emitted inside the block.

    Connector and provider code does not know which job it is serving; this is
    how its log lines stay attributable to a job and document.
    """

    token = _log_context.set({**(_log_context.get() or {}), **fields})
    try:
        yield
    finally:
        _log_context.reset(token)


def bind_log_context(**fields: object) -> None:
    """Update the surrounding ``log_context`` block, for example with the phase."""

    _log_context.set({**(_log_context.get() or {}), **fields})


def describe_exception(exc: BaseException) -> str:
    """Return a non-empty description, including context added with ``add_note``.

    Several exceptions, for example ``httpx.ReadTimeout``, have an empty ``str()``.
    """

    message = str(exc).strip()
    if not message:
        cause = exc.__cause__
        message = f"{type(exc).__name__} (no message)"
        if cause is not None:
            message += f", caused by {type(cause).__name__}: {describe_exception(cause)}"
    notes = [str(note) for note in getattr(exc, "__notes__", [])]
    return " | ".join([message, *notes])


def _log_value(value: object) -> object:
    if value is None or isinstance(value, bool | int | float):
        return value
    return redact_sensitive_text(value, limit=_MAX_EXTRA_VALUE_CHARS)


def _format_traceback(exc: BaseException) -> str:
    rendered = "".join(traceback.format_exception(exc))
    redacted = redact_sensitive_text(rendered, limit=len(rendered) + 1)
    # The raising frame and the final message are at the end.
    return redacted[-_MAX_TRACEBACK_CHARS:]


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_text(record.getMessage()),
        }
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_RECORD_FIELDS
        }
        for key, value in {**(_log_context.get() or {}), **extras}.items():
            if value is not None and key not in _PROTECTED_ENTRY_FIELDS:
                entry[key] = _log_value(value)
        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            entry["exception_type"] = type(exc).__name__
            entry["exception"] = redact_sensitive_text(describe_exception(exc))
            entry["traceback"] = _format_traceback(exc)
        return json.dumps(entry, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
