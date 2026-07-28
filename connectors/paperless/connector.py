from typing import Any

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
from connectors.base.interface import ConnectorCustomField, ConnectorDocument, DocumentConnector
from core.config.settings import get_settings


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

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Token {self.token}"},
            timeout=30.0,
            verify=self.verify_tls,
        )

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            async with self._client() as client:
                response = await client.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise TimeoutError(str(exc)) from exc
        except httpx.RequestError as exc:
            raise ConnectionError(str(exc)) from exc
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
        response.raise_for_status()
        return response

    async def health_check(self) -> bool:
        response = await self._request("GET", "/api/documents/?page_size=1")
        return response.status_code == 200

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

    async def download_original(self, external_document_id: str) -> bytes:
        response = await self._request("GET", f"/api/documents/{external_document_id}/download/")
        settings = get_settings()
        if len(response.content) > settings.max_document_bytes:
            raise ValidationError("Document exceeds the configured size limit")
        return response.content

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
                )
                for item in data.get("results", [])
            )
            next_url = data.get("next")
            url = str(next_url) if next_url else ""
        return fields

    async def write_content(self, external_document_id: str, content: str) -> bool:
        current = await self.get_document(external_document_id)
        if current.content:
            return False
        await self._request(
            "PATCH",
            f"/api/documents/{external_document_id}/",
            json={"content": content},
        )
        return True

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
