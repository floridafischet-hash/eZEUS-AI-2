import json

import httpx
import pytest

from plugins.ocr.qwen_cleanup import QwenOCRCleanup


def _client(corrected_text: str) -> httpx.AsyncClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps({"corrected_text": corrected_text})}},
        )

    return httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_cleanup_accepts_text_correction_with_unchanged_values() -> None:
    raw = "Rech nungsbetrag: 342,48 EUR\nRechnung 2026-4711"
    async with _client("Rechnungsbetrag: 342,48 EUR\nRechnung 2026-4711") as client:
        result = await QwenOCRCleanup(client).clean(raw)

    assert result.accepted is True
    assert result.text == "Rechnungsbetrag: 342,48 EUR\nRechnung 2026-4711"
    assert result.reason is None


@pytest.mark.asyncio
async def test_cleanup_rejects_changed_amount_and_keeps_proposal_for_audit() -> None:
    raw = "Brutto-Rechnungsbetrag 342,48 EUR"
    async with _client("Brutto-Rechnungsbetrag 642,48 EUR") as client:
        result = await QwenOCRCleanup(client).clean(raw)

    assert result.accepted is False
    assert result.text == "Brutto-Rechnungsbetrag 642,48 EUR"
    assert result.reason == "Qwen removed or changed protected values"


@pytest.mark.asyncio
async def test_cleanup_rejects_added_critical_value() -> None:
    raw = "Rechnung ohne Zahlungsziel"
    async with _client("Rechnung mit Zahlungsziel 30 Tage") as client:
        result = await QwenOCRCleanup(client).clean(raw)

    assert result.accepted is False
    assert result.reason == "Qwen added protected values"
