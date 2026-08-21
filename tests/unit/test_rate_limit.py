from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.config.settings import Settings
from core.security.rate_limit import InMemoryRateLimiter, RateLimitMiddleware


def _client(rate: int = 3, burst: int = 0) -> TestClient:
    settings = Settings(
        rate_limit_requests_per_minute=rate,
        rate_limit_burst=burst,
        rate_limit_exempt_paths=("/health",),
    )  # type: ignore[call-arg]
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, settings=settings)

    @app.get("/api/x")
    def _x() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/health")
    def _h() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(app)


def test_rate_limit_blocks_after_limit() -> None:
    client = _client(rate=2, burst=0)
    assert client.get("/api/x").status_code == 200
    assert client.get("/api/x").status_code == 200
    third = client.get("/api/x")
    assert third.status_code == 429
    assert "Retry-After" in third.headers


def test_rate_limit_exempts_health() -> None:
    client = _client(rate=1, burst=0)
    for _ in range(5):
        assert client.get("/health").status_code == 200


def test_rate_limiter_bounds_tracked_clients() -> None:
    limiter = InMemoryRateLimiter(requests_per_minute=1, burst=0, max_clients=2)
    assert limiter.check("client-a")[0]
    assert limiter.check("client-b")[0]
    assert limiter.check("client-c")[0]
    assert list(limiter._events) == ["client-b", "client-c"]
