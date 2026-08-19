import json

import httpx
import pytest

from core.config.settings import get_settings
from plugins.llm.ollama import OllamaExtractionProvider


@pytest.mark.asyncio
async def test_ollama_provider_returns_structured_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_ENABLED", "true")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "qwen3:4b"
        assert body["stream"] is False
        assert body["think"] is False
        assert body["format"]["required"] == ["found", "value", "confidence"]
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {"found": True, "value": "RE-2026-42", "confidence": 0.93}
                    ),
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama:11434"
    ) as client:
        provider = OllamaExtractionProvider(client=client)
        result = await provider.extract(
            "Rechnungsnummer: RE-2026-42",
            {"field_name": "Rechnungsnummer", "value_hint": "Text"},
        )

    assert len(result) == 1
    assert result[0].value == "RE-2026-42"
    assert result[0].provider == "ollama"
    assert result[0].metadata["local"] is True
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_ollama_provider_returns_no_candidate_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_ENABLED", "true")
    get_settings.cache_clear()

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps({"found": False, "value": None, "confidence": 0}),
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama:11434"
    ) as client:
        provider = OllamaExtractionProvider(client=client)
        result = await provider.extract(
            "Kein Rechnungsbezug vorhanden",
            {"field_name": "Rechnungsnummer"},
        )

    assert result == []
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_ollama_provider_rejects_value_not_present_in_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_ENABLED", "true")
    get_settings.cache_clear()

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps({"found": True, "value": "642,48", "confidence": 1}),
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama:11434"
    ) as client:
        provider = OllamaExtractionProvider(client=client)
        result = await provider.extract(
            "Brutto-Rechnungsbetrag 342,48 €",
            {"field_name": "Rechnungsbetrag"},
        )

    assert result == []
    get_settings.cache_clear()
