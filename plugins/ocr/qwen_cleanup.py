import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

import httpx

from core.config.settings import get_settings

PROTECTED_TOKEN_PATTERN = re.compile(
    r"\b(?=[A-Za-zÄÖÜäöüß0-9./,:_%+-]*\d)"
    r"[A-Za-zÄÖÜäöüß0-9][A-Za-zÄÖÜäöüß0-9./,:_%+-]*\b"
)

CLEANUP_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"corrected_text": {"type": "string"}},
    "required": ["corrected_text"],
}


@dataclass(slots=True, frozen=True)
class OCRCleanupResult:
    text: str | None
    accepted: bool
    reason: str | None
    model: str


class QwenOCRCleanup:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.timeout_seconds = settings.ocr_qwen_cleanup_timeout_seconds
        self.keep_alive = settings.ollama_keep_alive
        self.client = client

    @staticmethod
    def _protected_tokens(text: str) -> Counter[str]:
        return Counter(
            match.group(0).casefold() for match in PROTECTED_TOKEN_PATTERN.finditer(text)
        )

    def _validate(self, raw_text: str, cleaned_text: str) -> str | None:
        if not cleaned_text.strip():
            return "Qwen returned empty text"
        ratio = len(cleaned_text) / max(len(raw_text), 1)
        if ratio < 0.7 or ratio > 1.3:
            return "Qwen changed the document length beyond the allowed range"
        raw_tokens = self._protected_tokens(raw_text)
        cleaned_tokens = self._protected_tokens(cleaned_text)
        missing = raw_tokens - cleaned_tokens
        if missing:
            return "Qwen removed or changed protected values"
        added = cleaned_tokens - raw_tokens
        if added:
            return "Qwen added protected values"
        return None

    async def clean(self, raw_text: str) -> OCRCleanupResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Du bereinigst deutschen OCR-Text, ohne Informationen zu "
                        "ergänzen oder zu entfernen. Korrigiere nur offensichtliche "
                        "Worttrennungen, Leerzeichen, Zeilenumbrüche und Buchstabenfehler. "
                        "Verändere niemals Zahlen, Beträge, Datumswerte, Kennungen, "
                        "Rechnungsnummern, Steuerdaten, IBANs oder andere Codes. "
                        "Gib den vollständigen Text im vorgegebenen JSON-Schema zurück."
                    ),
                },
                {"role": "user", "content": f"OCR-Rohtext:\n{raw_text}"},
            ],
            "stream": False,
            "think": False,
            "format": CLEANUP_SCHEMA,
            "keep_alive": self.keep_alive,
            "options": {"temperature": 0, "num_predict": 4096},
        }
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
        )
        try:
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return OCRCleanupResult(
                None,
                False,
                f"Qwen cleanup failed: {type(exc).__name__}",
                self.model,
            )
        finally:
            if owns_client:
                await client.aclose()

        message = body.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            return OCRCleanupResult(None, False, "Qwen returned no text response", self.model)
        try:
            decoded = json.loads(message["content"])
        except json.JSONDecodeError:
            return OCRCleanupResult(None, False, "Qwen returned invalid JSON", self.model)
        if not isinstance(decoded, dict) or not isinstance(decoded.get("corrected_text"), str):
            return OCRCleanupResult(
                None, False, "Qwen returned an invalid cleanup result", self.model
            )
        cleaned_text = decoded["corrected_text"].strip()
        reason = self._validate(raw_text, cleaned_text)
        return OCRCleanupResult(
            cleaned_text,
            reason is None,
            reason,
            self.model,
        )
