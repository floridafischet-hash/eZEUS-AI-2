import json

import httpx
import pytest

from connectors.paperless.connector import PaperlessConnector


@pytest.mark.asyncio
async def test_ezeus_workflow_is_created_with_safe_public_webhook(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"results": []}, request=request)
        return httpx.Response(201, json={"id": 17}, request=request)

    connector = PaperlessConnector(
        base_url="https://paperless.example.test",
        api_token="token",
    )
    monkeypatch.setattr(
        connector,
        "_client",
        lambda: httpx.AsyncClient(
            base_url=connector.base_url,
            headers={"Authorization": "Token token"},
            transport=httpx.MockTransport(handler),
        ),
    )

    result = await connector.ensure_ezeus_workflow(
        webhook_url=(
            "https://webhook.212-227-20-171.sslip.io/"
            "webhooks/paperless/paperless-example-test"
        ),
        webhook_secret="long-secret-value",
    )

    assert result == {
        "configured": True,
        "created": True,
        "workflow_id": 17,
        "workflow_name": "eZEUS-AI-2 – automatische Dokumentverarbeitung",
    }
    payload = json.loads(requests[1].content)
    assert payload["enabled"] is True
    assert payload["triggers"] == [{"type": 2}, {"type": 3}]
    assert payload["actions"][0]["type"] == 4
    webhook = payload["actions"][0]["webhook"]
    assert webhook["as_json"] is True
    assert webhook["use_params"] is True
    assert webhook["params"] == {
        "document_id": '{{ doc_url.split("/")[-2] }}',
    }
    assert webhook["body"] is None
    assert webhook["headers"]["X-EZEUS-Webhook-Secret"] == "long-secret-value"


@pytest.mark.asyncio
async def test_ezeus_workflow_is_repaired_instead_of_duplicated(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 23,
                            "name": "eZEUS-AI-2 – automatische Dokumentverarbeitung",
                        }
                    ]
                },
                request=request,
            )
        return httpx.Response(200, json={"id": 23}, request=request)

    connector = PaperlessConnector(
        base_url="https://paperless.example.test",
        api_token="token",
    )
    monkeypatch.setattr(
        connector,
        "_client",
        lambda: httpx.AsyncClient(
            base_url=connector.base_url,
            headers={"Authorization": "Token token"},
            transport=httpx.MockTransport(handler),
        ),
    )

    result = await connector.ensure_ezeus_workflow(
        webhook_url="https://webhook.example.test/webhooks/paperless/customer",
        webhook_secret="long-secret-value",
    )

    assert result["created"] is False
    assert requests[1].method == "PUT"
    assert requests[1].url.path == "/api/workflows/23/"
