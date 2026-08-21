import json
import re
import unicodedata
from typing import Any

import httpx

from core.config.settings import get_settings
from core.security.outbound import stream_capped, validate_outbound_url
from plugins.base.interfaces import ExtractionCandidate, ExtractionProvider

RESULT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "value": {"type": ["string", "null"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["found", "value", "confidence"],
}


class OllamaExtractionProvider(ExtractionProvider):
    id = "ollama"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: int | None = None,
        max_input_chars: int | None = None,
        keep_alive: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout_seconds = timeout_seconds or settings.ollama_timeout_seconds
        self.max_input_chars = max_input_chars or settings.ollama_max_input_chars
        self.keep_alive = keep_alive or settings.ollama_keep_alive
        self.client = client
        self._settings = settings

    def _trim_text(self, text: str) -> str:
        if len(text) <= self.max_input_chars:
            return text
        half = self.max_input_chars // 2
        return f"{text[:half]}\n\n[... Dokument gekürzt ...]\n\n{text[-half:]}"

    @staticmethod
    def _grounding_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value).casefold()
        return re.sub(r"[^a-z0-9]", "", normalized)

    async def extract(self, text: str, config: dict[str, object]) -> list[ExtractionCandidate]:
        field_name = str(config.get("field_name") or config.get("description") or "").strip()
        if not field_name:
            raise ValueError("Ollama provider requires field_name or description")
        value_hint = str(config.get("value_hint") or "Textwert").strip()
        instructions = str(config.get("instructions") or "").strip()
        document_text = self._trim_text(text)

        system_prompt = (
            "Du extrahierst genau ein Feld aus deutschem OCR-Text. "
            "Erfinde niemals Werte. Wenn das Feld nicht eindeutig vorhanden ist, "
            "setze found=false, value=null und confidence=0. "
            "Antworte ausschließlich im vorgegebenen JSON-Schema."
        )
        user_prompt = (
            f"Gesuchtes Feld: {field_name}\n"
            f"Erwartetes Format: {value_hint}\n"
            f"Zusätzliche Hinweise: {instructions or 'keine'}\n\n"
            f"OCR-Text:\n{document_text}"
        )
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "think": False,
            "format": RESULT_SCHEMA,
            "keep_alive": self.keep_alive,
            "options": {"temperature": 0, "num_predict": 160},
        }

        owns_client = self.client is None
        request_url = f"{self.base_url}/api/chat"
        validate_outbound_url(request_url, settings=self._settings)
        client = self.client or httpx.AsyncClient(
            base_url=self.base_url, timeout=self.timeout_seconds
        )
        try:
            response, _ = await stream_capped(
                client,
                "POST",
                request_url,
                max_bytes=self._settings.ollama_max_response_bytes,
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        finally:
            if owns_client:
                await client.aclose()

        message = body.get("message")
        if not isinstance(message, dict):
            raise ValueError("Ollama response does not contain a message")
        content = message.get("content")
        if not isinstance(content, str):
            raise ValueError("Ollama response does not contain JSON content")
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("Ollama response is not a JSON object")
        if result.get("found") is not True:
            return []
        value = result.get("value")
        if value is None or not str(value).strip():
            return []
        value_text = str(value).strip()
        grounded_value = self._grounding_text(value_text)
        grounded_document = self._grounding_text(document_text)
        if not grounded_value or grounded_value not in grounded_document:
            return []
        confidence = min(1.0, max(0.0, float(result.get("confidence", 0))))
        return [
            ExtractionCandidate(
                value=value_text,
                confidence=confidence,
                provider=self.id,
                metadata={"model": self.model, "local": True, "field": field_name},
            )
        ]
