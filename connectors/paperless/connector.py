from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from connectors.base.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    ConnectionError,
    NotFoundError,
    RateLimitError,
    TimeoutError,
    ValidationError,
)
from connectors.base.interface import (
    ConnectorCorrespondent,
    ConnectorCustomField,
    ConnectorDocument,
    DocumentConnector,
)
from core.config.settings import get_settings
from core.security.outbound import (
    DisallowedOutboundHost,
    DownloadTooLargeError,
    stream_capped,
    validate_outbound_url,
)


class PaperlessConnector(DocumentConnector):
    def __init__(
        self,
        base_url: str | None = None,
        api_token: str | None = None,
        verify_tls: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.paperless_base_url).rstrip("/")
        self.token = api_token if api_token is not None else settings.paperless_api_token
        self.verify_tls = verify_tls if verify_tls is not None else settings.paperless_verify_tls
        self._settings = settings

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Token {self.token}"},
            timeout=30.0,
            verify=self.verify_tls,
        )

    def _validated_request_url(self, url: str) -> str:
        absolute_url = urljoin(f"{self.base_url}/", url)
        base = urlparse(self.base_url)
        target = urlparse(absolute_url)
        base_port = base.port or (443 if base.scheme == "https" else 80)
        target_port = target.port or (443 if target.scheme == "https" else 80)
        if (target.scheme, target.hostname, target_port) != (
            base.scheme,
            base.hostname,
            base_port,
        ):
            raise ConnectionError("Paperless response attempted a cross-origin request")
        try:
            # Managed instances may supply their own host while the operator
            # leaves OUTBOUND_ALLOWED_HOSTS empty.  As soon as the operator
            # configures that list it becomes authoritative.
            dynamic_hosts = () if self._settings.outbound_allowed_hosts else (base.hostname or "",)
            validate_outbound_url(
                absolute_url,
                extra_allowed_hosts=dynamic_hosts,
                settings=self._settings,
            )
        except DisallowedOutboundHost as exc:
            raise ConnectionError(str(exc)) from exc
        return absolute_url

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        request_url = self._validated_request_url(url)
        max_bytes = self._settings.paperless_max_download_bytes
        try:
            async with self._client() as client:
                response, body = await stream_capped(
                    client, method, request_url, max_bytes=max_bytes, **kwargs
                )
        except httpx.TimeoutException as exc:
            raise TimeoutError(str(exc)) from exc
        except DownloadTooLargeError as exc:
            raise ValidationError(str(exc)) from exc
        except httpx.RequestError as exc:
            raise ConnectionError(str(exc)) from exc
        del body
        request_url = str(response.request.url)
        if response.status_code == 401:
            raise AuthenticationError(
                f"Paperless authentication failed: HTTP 401 from {request_url}"
            )
        if response.status_code == 403:
            raise AuthorizationError(f"Paperless authorization failed: HTTP 403 from {request_url}")
        if response.status_code == 404:
            raise NotFoundError(f"Paperless resource not found: HTTP 404 from {request_url}")
        if response.status_code == 409:
            raise ConflictError("Paperless reported a conflict")
        if response.status_code == 429:
            raise RateLimitError("Paperless rate limit exceeded")
        if response.status_code in {400, 422}:
            raise ValidationError(
                f"Paperless rejected the request: HTTP {response.status_code} from {request_url}"
            )
        if response.status_code >= 500:
            raise ConnectionError(f"Paperless server error: HTTP {response.status_code}")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ValidationError(
                f"Unexpected Paperless response: HTTP {response.status_code}"
            ) from exc
        return response

    async def health_check(self) -> bool:
        response = await self._request(
            "GET",
            "/api/documents/?page_size=1",
            timeout=5.0,
        )
        return response.status_code == 200

    async def find_webhook_workflow(self, webhook_url: str) -> dict[str, object] | None:
        """Read-only lookup of a Paperless workflow whose webhook action targets
        ``webhook_url``. Does not create or modify anything, so it is safe to call
        for workflows the user configured by hand instead of via
        :meth:`ensure_ezeus_workflow`.
        """
        response = await self._request("GET", "/api/workflows/?page_size=100")
        workflows = response.json().get("results", [])
        for item in workflows:
            if not isinstance(item, dict):
                continue
            for action in item.get("actions") or []:
                webhook = action.get("webhook") if isinstance(action, dict) else None
                if isinstance(webhook, dict) and webhook.get("url") == webhook_url:
                    trigger_types = [
                        trigger.get("type")
                        for trigger in item.get("triggers") or []
                        if isinstance(trigger, dict)
                    ]
                    return {
                        "workflow_id": item.get("id"),
                        "workflow_name": item.get("name"),
                        "enabled": bool(item.get("enabled")),
                        "trigger_types": trigger_types,
                    }
        return None

    async def ensure_ezeus_workflow(
        self,
        *,
        webhook_url: str,
        webhook_secret: str,
    ) -> dict[str, object]:
        """Create or repair the workflow managed by eZEUS.

        The stable workflow name makes this operation idempotent.  User-created
        workflows are never modified.
        """
        workflow_name = "eZEUS-AI-2 – automatische Dokumentverarbeitung"
        payload: dict[str, object] = {
            "name": workflow_name,
            "order": 0,
            "enabled": True,
            "triggers": [
                {"type": 2},  # Document added
            ],
            "actions": [
                {
                    "type": 4,
                    "webhook": {
                        "url": webhook_url,
                        "use_params": True,
                        "as_json": True,
                        # Paperless 2.20.x documents ``doc_id`` but does not
                        # expose it to the workflow template context.  The
                        # stable document URL does contain the same id.
                        "params": {
                            "document_id": '{{ doc_url.split("/")[-2] }}',
                        },
                        "body": None,
                        "headers": {
                            "X-EZEUS-Webhook-Secret": webhook_secret,
                            "Content-Type": "application/json",
                        },
                        "include_document": False,
                    },
                }
            ],
        }
        response = await self._request("GET", "/api/workflows/?page_size=100")
        workflows = response.json().get("results", [])
        managed = next(
            (
                item
                for item in workflows
                if isinstance(item, dict) and item.get("name") == workflow_name
            ),
            None,
        )
        if managed is None:
            result = await self._request("POST", "/api/workflows/", json=payload)
            workflow = result.json()
            return {
                "configured": True,
                "created": True,
                "workflow_id": workflow.get("id"),
                "workflow_name": workflow_name,
            }

        workflow_id = managed.get("id")
        if workflow_id is None:
            raise ValidationError("Paperless workflow has no id")
        result = await self._request(
            "PUT",
            f"/api/workflows/{workflow_id}/",
            json=payload,
        )
        workflow = result.json()
        return {
            "configured": True,
            "created": False,
            "workflow_id": workflow.get("id", workflow_id),
            "workflow_name": workflow_name,
        }

    async def get_document(self, external_document_id: str) -> ConnectorDocument:
        response = await self._request("GET", f"/api/documents/{external_document_id}/")
        data = response.json()
        fields = {str(item["field"]): item.get("value") for item in data.get("custom_fields", [])}
        return ConnectorDocument(
            external_id=str(data["id"]),
            title=data.get("title"),
            filename=data.get("original_file_name"),
            mime_type=data.get("mime_type"),
            document_type_id=str(data["document_type"]) if data.get("document_type") else None,
            correspondent_id=str(data["correspondent"]) if data.get("correspondent") else None,
            content=data.get("content"),
            custom_fields=fields,
        )

    async def list_custom_fields(self) -> list[ConnectorCustomField]:
        fields: list[ConnectorCustomField] = []
        url = "/api/custom_fields/?page_size=100"
        while url:
            response = await self._request("GET", url)
            data = response.json()
            fields.extend(
                ConnectorCustomField(
                    external_id=str(item["id"]),
                    name=str(item["name"]),
                    data_type=str(item["data_type"]),
                    extra_data=(
                        dict(item["extra_data"]) if isinstance(item.get("extra_data"), dict) else {}
                    ),
                )
                for item in data.get("results", [])
            )
            next_url = data.get("next")
            url = str(next_url) if next_url else ""
        return fields

    async def create_custom_field(
        self,
        name: str,
        data_type: str,
        options: list[str] | None = None,
    ) -> ConnectorCustomField:
        payload: dict[str, object] = {"name": name, "data_type": data_type}
        if data_type == "select":
            payload["extra_data"] = {
                "select_options": [{"label": option} for option in options or []]
            }
        elif data_type == "monetary":
            payload["extra_data"] = {"default_currency": "EUR"}
        response = await self._request("POST", "/api/custom_fields/", json=payload)
        item = response.json()
        return ConnectorCustomField(
            external_id=str(item["id"]),
            name=str(item["name"]),
            data_type=str(item["data_type"]),
            extra_data=(
                dict(item["extra_data"]) if isinstance(item.get("extra_data"), dict) else {}
            ),
        )

    async def update_custom_field(
        self,
        external_field_id: str,
        name: str,
        data_type: str,
        options: list[str] | None = None,
    ) -> ConnectorCustomField:
        payload: dict[str, object] = {"name": name}
        if data_type == "select":
            current = await self._request("GET", f"/api/custom_fields/{external_field_id}/")
            current_data = current.json()
            extra_data = current_data.get("extra_data")
            current_options = (
                extra_data.get("select_options", []) if isinstance(extra_data, dict) else []
            )
            ids_by_label = {
                str(option["label"]): str(option["id"])
                for option in current_options
                if isinstance(option, dict) and option.get("label") and option.get("id")
            }
            payload["extra_data"] = {
                "select_options": [
                    {
                        "label": option,
                        **({"id": ids_by_label[option]} if option in ids_by_label else {}),
                    }
                    for option in options or []
                ]
            }
        response = await self._request(
            "PATCH",
            f"/api/custom_fields/{external_field_id}/",
            json=payload,
        )
        item = response.json()
        return ConnectorCustomField(
            external_id=str(item["id"]),
            name=str(item["name"]),
            data_type=str(item["data_type"]),
            extra_data=(
                dict(item["extra_data"]) if isinstance(item.get("extra_data"), dict) else {}
            ),
        )

    async def list_correspondents(self) -> list[ConnectorCorrespondent]:
        correspondents: list[ConnectorCorrespondent] = []
        url = "/api/correspondents/?page_size=100"
        while url:
            response = await self._request("GET", url)
            data = response.json()
            correspondents.extend(
                ConnectorCorrespondent(
                    external_id=str(item["id"]),
                    name=str(item["name"]),
                    match=str(item.get("match") or ""),
                    matching_algorithm=int(item.get("matching_algorithm") or 0),
                    is_insensitive=bool(item.get("is_insensitive", True)),
                )
                for item in data.get("results", [])
            )
            next_url = data.get("next")
            url = str(next_url) if next_url else ""
        return correspondents

    async def write_title(self, external_document_id: str, title: str) -> bool:
        current = await self.get_document(external_document_id)
        if current.title == title:
            return False
        await self._request(
            "PATCH",
            f"/api/documents/{external_document_id}/",
            json={"title": title},
        )
        return True

    async def write_correspondent_if_empty(
        self, external_document_id: str, correspondent_id: str
    ) -> bool:
        current = await self.get_document(external_document_id)
        if current.correspondent_id is not None:
            return False
        await self._request(
            "PATCH",
            f"/api/documents/{external_document_id}/",
            json={"correspondent": int(correspondent_id)},
        )
        return True

    async def write_empty_fields(
        self, external_document_id: str, values: dict[str, object]
    ) -> dict[str, object]:
        current = await self.get_document(external_document_id)
        merged = dict(current.custom_fields)
        changed = False
        written: dict[str, object] = {}
        for field_id, value in values.items():
            if merged.get(str(field_id)) in (None, "", []):
                merged[str(field_id)] = value
                changed = True
                written[str(field_id)] = value
        if not changed:
            return {}
        payload = {
            "custom_fields": [{"field": int(key), "value": value} for key, value in merged.items()]
        }
        await self._request("PATCH", f"/api/documents/{external_document_id}/", json=payload)
        return written
