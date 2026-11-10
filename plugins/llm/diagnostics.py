import json
from typing import Any

import httpx

from core.security.redaction import response_excerpt


def add_ollama_request_note(
    exc: Exception,
    *,
    url: str,
    model: str,
    timeout_seconds: int,
) -> None:
    """Add the request details, and Ollama's own error text, to a failed call.

    ``raise_for_status`` omits the response body, which is where Ollama says for
    example that a model is not installed.
    """

    note = f"Ollama request: POST {url}, model={model}, timeout={timeout_seconds} s"
    if isinstance(exc, httpx.HTTPStatusError):
        note += f", response: {response_excerpt(exc.response.text)}"
    exc.add_note(note)


def parse_ollama_content(content: str, body: dict[str, Any], *, model: str) -> object:
    """Decode the model's JSON answer without repeating document-derived text."""

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Ollama response content is not valid JSON: "
            f"{exc.msg} at position {exc.pos} of {len(content)} characters "
            f"(model={model}, done_reason={body.get('done_reason')})"
        ) from exc
