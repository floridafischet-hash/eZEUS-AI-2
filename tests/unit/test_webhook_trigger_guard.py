from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException

from connectors.base.interface import ConnectorDocument
from core.models.paperless_instance import PaperlessInstance
from webhooks.paperless.router import _verify_instance_trigger
from webhooks.paperless.schemas import PaperlessWebhookPayload


def _instance(**changes: object) -> PaperlessInstance:
    values: dict[str, object] = {
        "name": "Pilot",
        "slug": "pilot",
        "base_url": "https://paperless.example.test",
        "api_token_encrypted": "encrypted-token",
        "webhook_secret_encrypted": "encrypted-secret",
        "webhook_secret_hmac": "0" * 64,
        "verify_tls": True,
        "enabled": True,
        "ocr_handoff_enabled": False,
        "ocr_request_tag_name": None,
        "ocr_complete_tag_name": "OCR fertig",
        "ocr_pending_tag_name": "OCR wartet",
        "ocr_triggered_tag_name": "OCR verarbeitet",
        "manual_reprocess_enabled": True,
        "manual_reprocess_tag_name": "9",
    }
    values.update(changes)
    return PaperlessInstance(**values)


class _Connector:
    def __init__(self, *, document_tags: set[str], tags: dict[str, int]) -> None:
        self.document_tags = document_tags
        self.tags = tags

    async def get_document(self, document_id: str) -> ConnectorDocument:
        return ConnectorDocument(external_id=document_id, tag_ids=frozenset(self.document_tags))

    async def find_tag(self, name: str) -> dict[str, object] | None:
        tag_id = self.tags.get(name)
        return {"id": tag_id, "name": name} if tag_id is not None else None


def _connector_factory(connector: _Connector):
    @asynccontextmanager
    async def factory(_instance: PaperlessInstance) -> AsyncIterator[_Connector]:
        yield connector

    return factory


@pytest.mark.asyncio
async def test_manual_trigger_requires_configured_tag_on_document(monkeypatch) -> None:
    connector = _Connector(document_tags={"55"}, tags={"9": 55})
    monkeypatch.setattr(
        "webhooks.paperless.router.connector_for_instance", _connector_factory(connector)
    )

    await _verify_instance_trigger(_instance(), PaperlessWebhookPayload(document_id=257), "manual")

    connector.document_tags.clear()
    with pytest.raises(HTTPException) as exc_info:
        await _verify_instance_trigger(
            _instance(), PaperlessWebhookPayload(document_id=257), "manual"
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_deleted_manual_tag_fails_closed(monkeypatch) -> None:
    connector = _Connector(document_tags=set(), tags={})
    monkeypatch.setattr(
        "webhooks.paperless.router.connector_for_instance", _connector_factory(connector)
    )

    with pytest.raises(HTTPException) as exc_info:
        await _verify_instance_trigger(
            _instance(), PaperlessWebhookPayload(document_id=257), "manual"
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_ocr_trigger_is_optional_and_checks_both_marker_tags(monkeypatch) -> None:
    connector = _Connector(document_tags={"52"}, tags={"OCR fertig": 52, "OCR verarbeitet": 53})
    monkeypatch.setattr(
        "webhooks.paperless.router.connector_for_instance", _connector_factory(connector)
    )
    payload = PaperlessWebhookPayload(document_id=257)

    with pytest.raises(HTTPException) as disabled:
        await _verify_instance_trigger(_instance(), payload, "ocr-complete")
    assert disabled.value.status_code == 409

    enabled = _instance(ocr_handoff_enabled=True)
    await _verify_instance_trigger(enabled, payload, "ocr-complete")

    connector.tags.pop("OCR verarbeitet")
    with pytest.raises(HTTPException) as missing_marker:
        await _verify_instance_trigger(enabled, payload, "ocr-complete")
    assert missing_marker.value.status_code == 409

    connector.tags["OCR verarbeitet"] = 53
    connector.document_tags.add("53")
    with pytest.raises(HTTPException) as already_processed:
        await _verify_instance_trigger(enabled, payload, "ocr-complete")
    assert already_processed.value.status_code == 409


@pytest.mark.asyncio
async def test_document_added_and_legacy_webhooks_keep_standard_behavior() -> None:
    instance = _instance(manual_reprocess_enabled=False)
    payload = PaperlessWebhookPayload(document_id=257)

    await _verify_instance_trigger(instance, payload, "document-added")
    await _verify_instance_trigger(instance, payload, None)
