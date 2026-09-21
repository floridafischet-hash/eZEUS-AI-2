"""Reject oversized HTTP request bodies before parsing or authentication."""

from __future__ import annotations

import json
from collections.abc import Sequence

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestBodyTooLarge(Exception):
    """Internal control-flow exception raised while streaming a request body."""


class BodySizeLimitMiddleware:
    """Apply a default request limit and optional path-prefix limits.

    This is plain ASGI middleware so requests without ``Content-Length`` are
    counted incrementally while downstream code reads them.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        default_max_bytes: int,
        path_limits: Sequence[tuple[str, int]] = (),
    ) -> None:
        self.app = app
        self.default_max_bytes = default_max_bytes
        self.path_limits = sorted(path_limits, key=lambda item: len(item[0]), reverse=True)

    def limit_for(self, path: str) -> int:
        for prefix, limit in self.path_limits:
            normalized = prefix.rstrip("/")
            if path == normalized or path.startswith(f"{normalized}/"):
                return limit
        return self.default_max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = self.limit_for(scope.get("path", ""))
        content_lengths: list[int] = []
        for name, value in scope.get("headers", []):
            if name.lower() != b"content-length":
                continue
            try:
                declared = int(value)
            except ValueError:
                await _reject(send, 400, "Invalid Content-Length header")
                return
            if declared < 0:
                await _reject(send, 400, "Invalid Content-Length header")
                return
            content_lengths.append(declared)
        if len(set(content_lengths)) > 1:
            await _reject(send, 400, "Conflicting Content-Length headers")
            return
        if content_lengths and content_lengths[0] > limit:
            await _reject(send, 413, "Request body too large")
            return

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise RequestBodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except RequestBodyTooLarge:
            if not response_started:
                await _reject(send, 413, "Request body too large")


async def _reject(send: Send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
