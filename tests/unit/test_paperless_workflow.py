import json

import httpx
import pytest

from connectors.base.errors import ConnectionError, ValidationError
from connectors.paperless.connector import PaperlessConnector
from core.config.settings import Settings


@pytest.mark.asyncio
async def test_optional_workflow_features_are_disabled_by_default(monkeypatch) -> None:
    requests: list[httpx.Request] = []
    monkeypatch.setattr("core.security.outbound.resolve_hosts", lambda _host: ["203.0.113.10"])

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"results": []}, request=request)
        payload = json.loads(request.content)
        assert payload["name"] == "eZEUS-AI-2 – automatische Dokumentverarbeitung"
        return httpx.Response(201, json={"id": 17}, request=request)

    connector = PaperlessConnector(
        base_url="https://paperless.example.test",
        api_token="token",
    )
    connector._settings = Settings(outbound_block_private_networks=False)
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
        webhook_url="https://webhook.example.test/webhooks/paperless/default",
        webhook_secret="long-secret-value",
    )

    assert result["ocr_trigger"] is None
    assert result["manual_trigger"] is None
    assert not any(request.url.path == "/api/tags/" for request in requests)
    workflow_request = next(request for request in requests if request.method == "POST")
    payload = json.loads(workflow_request.content)
    assert payload["triggers"] == [{"type": 2}]
    assert [action["type"] for action in payload["actions"]] == [4]
    assert (
        payload["actions"][0]["webhook"]["headers"]["X-EZEUS-Workflow-Trigger"] == "document-added"
    )


@pytest.mark.asyncio
async def test_manual_trigger_is_independent_when_ocr_handoff_is_disabled(monkeypatch) -> None:
    requests: list[httpx.Request] = []
    monkeypatch.setattr("core.security.outbound.resolve_hosts", lambda _host: ["203.0.113.10"])

    workflows = [
        {"id": 71, "name": "eZEUS-AI-2 – automatische Dokumentverarbeitung", "enabled": True},
        {"id": 76, "name": "eZEUS-AI-2 – manuelle Neuverarbeitung", "enabled": True},
        {"id": 77, "name": "eZEUS-AI-2 – Paperless-gpt OCR anfordern", "enabled": True},
        {"id": 78, "name": "eZEUS-AI-2 – Paperless-gpt OCR-Abschluss", "enabled": True},
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/tags/" and request.method == "GET":
            return httpx.Response(200, json={"results": [{"id": 55, "name": "9"}]}, request=request)
        if request.url.path == "/api/workflows/" and request.method == "GET":
            return httpx.Response(200, json={"results": workflows}, request=request)
        workflow_id = int(request.url.path.rstrip("/").rsplit("/", 1)[-1])
        return httpx.Response(200, json={"id": workflow_id}, request=request)

    connector = PaperlessConnector(base_url="https://paperless.example.test", api_token="token")
    connector._settings = Settings(outbound_block_private_networks=False)
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
        webhook_url="https://webhook.example.test/webhooks/paperless/pilot",
        webhook_secret="long-secret-value",
        ocr_handoff_enabled=False,
        manual_reprocess_enabled=True,
        manual_reprocess_tag_name="9",
    )

    assert result["ocr_trigger"] is None
    assert result["manual_trigger"]["tag_name"] == "9"
    disabled = {
        request.url.path
        for request in requests
        if request.method == "PATCH" and json.loads(request.content) == {"enabled": False}
    }
    assert disabled == {"/api/workflows/77/", "/api/workflows/78/"}
    updates = {
        request.url.path: json.loads(request.content)
        for request in requests
        if request.method == "PUT"
    }
    automatic = updates["/api/workflows/71/"]
    assert automatic["triggers"] == [{"type": 2}]
    assert (
        automatic["actions"][0]["webhook"]["headers"]["X-EZEUS-Workflow-Trigger"]
        == "document-added"
    )
    manual = updates["/api/workflows/76/"]
    assert manual["triggers"] == [{"type": 3, "filter_has_all_tags": [55]}]
    assert manual["actions"][0]["webhook"]["headers"]["X-EZEUS-Workflow-Trigger"] == "manual"
    assert manual["actions"][1] == {"type": 2, "remove_tags": [55]}


@pytest.mark.asyncio
async def test_ezeus_workflow_is_created_with_safe_public_webhook(monkeypatch) -> None:
    requests: list[httpx.Request] = []
    monkeypatch.setattr(
        "core.security.outbound.resolve_hosts",
        lambda _host: ["203.0.113.10"],
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/tags/" and request.method == "GET":
            return httpx.Response(200, json={"results": []}, request=request)
        if request.url.path == "/api/tags/" and request.method == "POST":
            name = json.loads(request.content)["name"]
            tag_ids = {
                "OCR anfordern": 50,
                "OCR wartet": 51,
                "OCR fertig": 52,
                "OCR verarbeitet": 53,
                "Günther": 54,
            }
            return httpx.Response(
                201,
                json={"id": tag_ids[name], "name": name},
                request=request,
            )
        if request.method == "GET":
            return httpx.Response(200, json={"results": []}, request=request)
        workflow_name = json.loads(request.content)["name"]
        workflow_id = {
            "eZEUS-AI-2 – Paperless-gpt OCR anfordern": 15,
            "eZEUS-AI-2 – Paperless-gpt OCR-Abschluss": 16,
            "eZEUS-AI-2 – automatische Dokumentverarbeitung": 17,
            "eZEUS-AI-2 – manuelle Neuverarbeitung": 18,
        }[workflow_name]
        return httpx.Response(201, json={"id": workflow_id}, request=request)

    connector = PaperlessConnector(
        base_url="https://paperless.example.test",
        api_token="token",
    )
    connector._settings = Settings(outbound_block_private_networks=False)
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
        webhook_url=("https://webhook.example.test/webhooks/paperless/paperless-example-test"),
        webhook_secret="long-secret-value",
        ocr_handoff_enabled=True,
        ocr_request_tag_name="OCR anfordern",
        ocr_complete_tag_name="OCR fertig",
        ocr_pending_tag_name="OCR wartet",
        ocr_triggered_tag_name="OCR verarbeitet",
        manual_reprocess_enabled=True,
        manual_reprocess_tag_name="Günther",
    )

    assert result["configured"] is True
    assert result["created"] is True
    assert result["workflow_id"] == 17
    assert result["workflow_name"] == "eZEUS-AI-2 – automatische Dokumentverarbeitung"
    assert result["ocr_trigger"] == {
        "request_tag_name": "OCR anfordern",
        "request_tag_id": 50,
        "pending_tag_name": "OCR wartet",
        "pending_tag_id": 51,
        "complete_tag_name": "OCR fertig",
        "complete_tag_id": 52,
        "triggered_tag_name": "OCR verarbeitet",
        "triggered_tag_id": 53,
        "request_workflow": {
            "created": True,
            "workflow_id": 15,
            "workflow_name": "eZEUS-AI-2 – Paperless-gpt OCR anfordern",
        },
        "complete_workflow": {
            "created": True,
            "workflow_id": 16,
            "workflow_name": "eZEUS-AI-2 – Paperless-gpt OCR-Abschluss",
        },
    }
    assert result["manual_trigger"] == {
        "tag_name": "Günther",
        "tag_id": 54,
        "created": True,
        "workflow_id": 18,
        "workflow_name": "eZEUS-AI-2 – manuelle Neuverarbeitung",
    }
    workflow_requests = [
        request
        for request in requests
        if request.url.path == "/api/workflows/" and request.method == "POST"
    ]
    workflow_payloads = {
        payload["name"]: payload
        for payload in (json.loads(request.content) for request in workflow_requests)
    }
    request_payload = workflow_payloads["eZEUS-AI-2 – Paperless-gpt OCR anfordern"]
    assert request_payload["triggers"] == [{"type": 2}]
    assert request_payload["actions"] == [{"type": 1, "assign_tags": [50, 51]}]

    complete_payload = workflow_payloads["eZEUS-AI-2 – Paperless-gpt OCR-Abschluss"]
    assert complete_payload["triggers"] == [
        {
            "type": 3,
            "filter_has_all_tags": [51],
            "filter_has_not_tags": [50, 52],
        }
    ]
    assert complete_payload["actions"] == [
        {"type": 1, "assign_tags": [52]},
        {"type": 2, "remove_tags": [51]},
    ]

    payload = workflow_payloads["eZEUS-AI-2 – automatische Dokumentverarbeitung"]
    assert payload["enabled"] is True
    assert payload["triggers"] == [
        {
            "type": 3,
            "filter_has_all_tags": [52],
            "filter_has_not_tags": [53],
        }
    ]
    assert payload["actions"][0]["type"] == 4
    assert payload["actions"][1] == {"type": 1, "assign_tags": [53]}
    assert payload["actions"][2] == {"type": 2, "remove_tags": [51]}
    webhook = payload["actions"][0]["webhook"]
    assert webhook["as_json"] is True
    assert webhook["use_params"] is True
    assert webhook["params"] == {
        "document_id": '{{ doc_url.split("/")[-2] }}',
    }
    assert webhook["body"] is None
    assert webhook["headers"]["X-EZEUS-Webhook-Secret"] == "long-secret-value"
    assert webhook["headers"]["X-EZEUS-Workflow-Trigger"] == "ocr-complete"

    manual_payload = workflow_payloads["eZEUS-AI-2 – manuelle Neuverarbeitung"]
    assert manual_payload["triggers"] == [
        {"type": 3, "filter_has_all_tags": [54]},
    ]
    assert manual_payload["actions"][0]["type"] == 4
    assert (
        manual_payload["actions"][0]["webhook"]["headers"]["X-EZEUS-Workflow-Trigger"] == "manual"
    )
    assert manual_payload["actions"][1] == {"type": 2, "remove_tags": [54]}


@pytest.mark.asyncio
async def test_ezeus_workflow_is_repaired_instead_of_duplicated(monkeypatch) -> None:
    requests: list[httpx.Request] = []
    monkeypatch.setattr(
        "core.security.outbound.resolve_hosts",
        lambda _host: ["203.0.113.10"],
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/tags/":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 50, "name": "3"},
                        {"id": 51, "name": "ezeus-ai-2-ocr-pending"},
                        {"id": 52, "name": "paperless-gpt-auto-complete"},
                        {"id": 53, "name": "ezeus-ai-2-ocr-triggered"},
                        {"id": 54, "name": "9"},
                    ]
                },
                request=request,
            )
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 21,
                            "name": "eZEUS-AI-2 – Paperless-gpt OCR anfordern",
                        },
                        {
                            "id": 22,
                            "name": "eZEUS-AI-2 – Paperless-gpt OCR-Abschluss",
                        },
                        {
                            "id": 23,
                            "name": "eZEUS-AI-2 – automatische Dokumentverarbeitung",
                        },
                        {
                            "id": 24,
                            "name": "eZEUS-AI-2 – manuelle Neuverarbeitung (Tag 9)",
                        },
                    ]
                },
                request=request,
            )
        workflow_id = int(request.url.path.rstrip("/").rsplit("/", 1)[-1])
        return httpx.Response(200, json={"id": workflow_id}, request=request)

    connector = PaperlessConnector(
        base_url="https://paperless.example.test",
        api_token="token",
    )
    connector._settings = Settings(outbound_block_private_networks=False)
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
        ocr_handoff_enabled=True,
        ocr_request_tag_name="3",
        manual_reprocess_enabled=True,
    )

    assert result["created"] is False
    assert result["manual_trigger"]["created"] is False
    workflow_updates = [request for request in requests if request.method == "PUT"]
    assert [request.url.path for request in workflow_updates] == [
        "/api/workflows/21/",
        "/api/workflows/22/",
        "/api/workflows/23/",
        "/api/workflows/24/",
    ]
    legacy_manual_update = workflow_updates[-1]
    assert json.loads(legacy_manual_update.content)["name"] == (
        "eZEUS-AI-2 – manuelle Neuverarbeitung"
    )


@pytest.mark.asyncio
async def test_active_workflow_tag_names_must_be_unique(monkeypatch) -> None:
    monkeypatch.setattr("core.security.outbound.resolve_hosts", lambda _host: ["203.0.113.10"])

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []}, request=request)

    connector = PaperlessConnector(
        base_url="https://paperless.example.test",
        api_token="token",
    )
    connector._settings = Settings(outbound_block_private_networks=False)
    monkeypatch.setattr(
        connector,
        "_client",
        lambda: httpx.AsyncClient(
            base_url=connector.base_url,
            headers={"Authorization": "Token token"},
            transport=httpx.MockTransport(handler),
        ),
    )

    with pytest.raises(ValidationError, match="must be unique"):
        await connector.ensure_ezeus_workflow(
            webhook_url="https://webhook.example.test/webhooks/paperless/customer",
            webhook_secret="long-secret-value",
            ocr_handoff_enabled=True,
            ocr_complete_tag_name="gleich",
            ocr_triggered_tag_name="gleich",
        )


def test_paperless_pagination_cannot_switch_to_another_origin() -> None:
    connector = PaperlessConnector(
        base_url="https://paperless.example.test",
        api_token="token",
    )
    connector._settings = Settings(outbound_block_private_networks=False)

    with pytest.raises(ConnectionError, match="cross-origin"):
        connector._validated_request_url("https://attacker.example/api/custom_fields/")


def test_operator_outbound_allowlist_restricts_managed_instance_host() -> None:
    connector = PaperlessConnector(
        base_url="https://unapproved-paperless.example.test",
        api_token="token",
    )
    connector._settings = Settings(
        outbound_allowed_hosts=("approved-paperless.example.test",),
        outbound_block_private_networks=False,
    )

    with pytest.raises(ConnectionError, match="not in the allowed list"):
        connector._validated_request_url("/api/documents/")
