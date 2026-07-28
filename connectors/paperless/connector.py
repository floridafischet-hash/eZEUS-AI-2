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
from connectors.base.interface import ConnectorDocument, DocumentConnector
from core.config.settings import get_settings


class PaperlessConnector(DocumentConnector):
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.paperless_base_url.rstrip("/")
        self.token = settings.paperless_api_token
        self.verify_tls = settings.paperless_verify_tls

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
        if response.status_code == 401:
            raise AuthenticationError("Paperless authentication failed")
        if response.status_code == 403:
            raise AuthorizationError("Paperless authorization failed")
        if response.status_code == 404:
            raise NotFoundError("Paperless document not found")
        if response.status_code == 409:
            raise ConflictError("Paperless reported a conflict")
        if response.status_code == 429:
            raise RateLimitError("Paperless rate limit exceeded")
        if response.status_code in {400, 422}:
            raise ValidationError("Paperless rejected the request")
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
