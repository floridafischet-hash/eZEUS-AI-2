"""Validation for untrusted Paperless webhook identifiers."""

import pytest
from pydantic import ValidationError

from webhooks.paperless.schemas import PaperlessWebhookPayload


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(42, "42"), ("42", "42"), (" 128 ", "128"), (999_999_999_999, "999999999999")],
)
def test_accepts_positive_integer_document_ids(raw: object, expected: str) -> None:
    assert PaperlessWebhookPayload(document_id=raw).document_id == expected


@pytest.mark.parametrize(
    "raw",
    [
        "../users/1",
        "1/../../users",
        "1/?page=2",
        "1#fragment",
        "1%2F..%2Fusers",
        "//evil.example",
        "-1",
        "0",
        "01",
        "1.5",
        1.5,
        "",
        " ",
        True,
        None,
        "1" * 13,
        ["1"],
        {"id": 1},
    ],
)
def test_rejects_non_numeric_or_malicious_document_ids(raw: object) -> None:
    with pytest.raises(ValidationError):
        PaperlessWebhookPayload(document_id=raw)


@pytest.mark.parametrize(
    "event_id",
    ["created 42", "paperless/created/42", "opaque+event=value", "äußeres Ereignis"],
)
def test_event_id_remains_opaque_and_compatible(event_id: str) -> None:
    assert PaperlessWebhookPayload(document_id=1, event_id=event_id).event_id == event_id


@pytest.mark.parametrize("event_id", ["a\nb", "a\rb", "a\x00b", "a\x7fb"])
def test_event_id_rejects_control_characters(event_id: str) -> None:
    with pytest.raises(ValidationError):
        PaperlessWebhookPayload(document_id=1, event_id=event_id)


def test_event_id_length_is_limited_and_blank_is_missing() -> None:
    PaperlessWebhookPayload(document_id=1, event_id="e" * 200)
    with pytest.raises(ValidationError):
        PaperlessWebhookPayload(document_id=1, event_id="e" * 201)
    assert PaperlessWebhookPayload(document_id=1, event_id=" ").event_id is None


def test_unknown_document_payload_is_not_retained() -> None:
    payload = PaperlessWebhookPayload.model_validate(
        {"document_id": 1, "document": {"private": "content"}, "unknown": "value"}
    )
    assert payload.model_dump() == {"document_id": "1", "event_id": None}
