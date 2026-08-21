import pytest

from core.config.settings import Settings
from core.security.documents import DocumentSafetyError, validate_paperless_document
from core.security.redaction import redact_sensitive_text


def test_document_safety_rejects_unsupported_mime_type() -> None:
    with pytest.raises(DocumentSafetyError, match="Unsupported document MIME type"):
        validate_paperless_document(
            mime_type="application/x-executable",
            content="text",
            settings=Settings(),
        )


def test_document_safety_caps_paperless_text() -> None:
    with pytest.raises(DocumentSafetyError, match="exceeds 10 characters"):
        validate_paperless_document(
            mime_type="application/pdf",
            content="x" * 11,
            settings=Settings(paperless_max_text_chars=10),
        )


def test_sensitive_error_text_is_redacted() -> None:
    value = (
        "Authorization: Bearer abc.def secret=topsecret "
        "https://user:pass@example.test/a?access_token=xyz&client_secret=client-value "
        "token=plain-token"
    )
    redacted = redact_sensitive_text(value)
    assert "abc.def" not in redacted
    assert "topsecret" not in redacted
    assert "user:pass" not in redacted
    assert "xyz" not in redacted
    assert "client-value" not in redacted
    assert "plain-token" not in redacted
    assert redacted.count("[REDACTED]") >= 6
