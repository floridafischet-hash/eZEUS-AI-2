import json

import httpx
import pytest

from connectors.base.interface import ConnectorCorrespondent
from plugins.llm.metadata import OllamaMetadataProvider


@pytest.fixture(autouse=True)
def _resolve_ollama_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "core.security.outbound.resolve_hosts",
        lambda _host: ["10.96.0.42"],
    )


@pytest.mark.asyncio
async def test_title_suggestion_uses_customer_instructions() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "Rechnungsnummer zuerst" in body["messages"][1]["content"]
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps({"found": True, "title": "RE-2026-42 – Wartungsrechnung"})
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://ollama:11434",
    ) as client:
        title = await OllamaMetadataProvider(client=client).suggest_title(
            "Rechnung RE-2026-42 für Wartung",
            "Rechnungsnummer zuerst",
        )

    assert title == "RE-2026-42 – Wartungsrechnung"


@pytest.mark.asyncio
async def test_correspondent_selection_accepts_only_existing_id() -> None:
    correspondents = [
        ConnectorCorrespondent("7", "Müller GmbH", "Müller", 3, True),
        ConnectorCorrespondent("8", "Beispiel AG", "Beispiel", 3, True),
    ]

    async def valid_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps({"found": True, "correspondent_id": "7"})}},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(valid_handler),
        base_url="http://ollama:11434",
    ) as client:
        selected = await OllamaMetadataProvider(client=client).select_correspondent(
            "Absender Müller GmbH",
            correspondents,
            "Müller-Niederlassungen dem Hauptlieferanten zuordnen",
        )
    assert selected == correspondents[0]

    async def invalid_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps({"found": True, "correspondent_id": "999"})}},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(invalid_handler),
        base_url="http://ollama:11434",
    ) as client:
        selected = await OllamaMetadataProvider(client=client).select_correspondent(
            "Unbekannter Absender",
            correspondents,
        )
    assert selected is None
