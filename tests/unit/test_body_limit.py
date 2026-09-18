"""Request body limits are enforced before parsing and authentication."""

import asyncio

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from core.security.body_limit import BodySizeLimitMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        BodySizeLimitMiddleware,
        default_max_bytes=1000,
        path_limits=(("/webhooks/", 100),),
    )
    parsed: list[int] = []

    @app.post("/webhooks/paperless")
    async def webhook(request: Request) -> dict[str, int]:
        body = await request.body()
        parsed.append(len(body))
        return {"size": len(body)}

    @app.post("/api/other")
    async def other(request: Request) -> dict[str, int]:
        body = await request.body()
        parsed.append(len(body))
        return {"size": len(body)}

    app.state.parsed = parsed
    return app


def test_small_bodies_pass_at_exact_limits() -> None:
    client = TestClient(_app())
    assert client.post("/webhooks/paperless", content=b"x" * 100).json() == {"size": 100}
    assert client.post("/api/other", content=b"x" * 1000).json() == {"size": 1000}


def test_webhook_limit_is_stricter_than_default() -> None:
    app = _app()
    client = TestClient(app)
    assert client.post("/webhooks/paperless", content=b"x" * 101).status_code == 413
    assert app.state.parsed == []
    assert client.post("/api/other", content=b"x" * 101).status_code == 200


def test_chunked_body_without_content_length_is_limited() -> None:
    app = _app()
    client = TestClient(app)

    def chunks():
        for _ in range(20):
            yield b"x" * 10

    assert client.post("/webhooks/paperless", content=chunks()).status_code == 413
    assert app.state.parsed == []


async def _call_with_headers(headers: list[tuple[bytes, bytes]]) -> list[dict]:
    middleware = BodySizeLimitMiddleware(_app(), default_max_bytes=10)
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await middleware({"type": "http", "path": "/api/other", "headers": headers}, receive, send)
    return sent


@pytest.mark.parametrize(
    "headers",
    [
        [(b"content-length", b"abc")],
        [(b"content-length", b"-1")],
        [(b"content-length", b"1"), (b"content-length", b"2")],
    ],
)
def test_invalid_or_conflicting_content_lengths_are_rejected(
    headers: list[tuple[bytes, bytes]],
) -> None:
    sent = asyncio.run(_call_with_headers(headers))
    assert sent[0]["status"] == 400


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/webhooks", 100),
        ("/webhooks/", 100),
        ("/webhooks/paperless", 100),
        ("/webhooks/paperless/tenant-a", 100),
        ("/webhooksX", 1000),
        ("/api/logs", 1000),
    ],
)
def test_limit_selection_by_prefix(path: str, expected: int) -> None:
    middleware = BodySizeLimitMiddleware(
        _app(), default_max_bytes=1000, path_limits=(("/webhooks/", 100),)
    )
    assert middleware.limit_for(path) == expected


def test_real_app_rejects_oversized_webhook_before_authentication() -> None:
    from apps.api.main import app

    response = TestClient(app).post(
        "/webhooks/paperless",
        headers={"X-EZEUS-Webhook-Secret": "irrelevant"},
        content=b'{"document_id": 1, "pad": "' + b"x" * 70_000 + b'"}',
    )
    assert response.status_code == 413
