from __future__ import annotations

import time
from collections import OrderedDict, deque
from threading import Lock

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from core.config.settings import Settings


class InMemoryRateLimiter:
    """Sliding-window per-key rate limiter.

    Not a distributed limiter — for multi-replica setups place a real reverse
    proxy (nginx, Traefik) in front, or swap this out for Redis. The window is
    per process; combined with the requested burst allowance it is a safety
    net against runaway single clients, not a global quota.
    """

    def __init__(self, requests_per_minute: int, burst: int, max_clients: int) -> None:
        self.limit = max(1, requests_per_minute)
        self.burst = max(0, burst)
        self.max_clients = max(1, max_clients)
        self.window_seconds = 60.0
        self._events: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, float]:
        now = time.monotonic()
        with self._lock:
            events = self._events.get(key)
            if events is None:
                if len(self._events) >= self.max_clients:
                    self._events.popitem(last=False)
                events = deque()
                self._events[key] = events
            else:
                self._events.move_to_end(key)
            cutoff = now - self.window_seconds
            while events and events[0] < cutoff:
                events.popleft()
            recent = len(events)
            if recent >= self.limit + self.burst:
                retry_after = max(0.0, events[0] + self.window_seconds - now)
                return False, retry_after
            events.append(now)
            return True, 0.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings
        self.limiter = InMemoryRateLimiter(
            settings.rate_limit_requests_per_minute,
            settings.rate_limit_burst,
            settings.rate_limit_max_clients,
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self.settings.rate_limit_enabled:
            return await call_next(request)
        path = request.url.path
        for prefix in self.settings.rate_limit_exempt_paths:
            if path.startswith(prefix):
                return await call_next(request)
        key = _client_key(request, trust_proxy_headers=self.settings.rate_limit_trust_proxy_headers)
        allowed, retry_after = self.limiter.check(key)
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(max(1, int(retry_after)))},
            )
        response: Response = await call_next(request)
        return response


def _client_key(request: Request, *, trust_proxy_headers: bool) -> str:
    if trust_proxy_headers:
        # ingress-nginx overwrites X-Real-IP.  Prefer it over X-Forwarded-For,
        # whose left-most value can originate from an untrusted client.
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.rsplit(",", 1)[-1].strip()
    client = request.client
    return client.host if client else "unknown"
