import time

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import apps.api.main as api_main

app = api_main.app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_times_out_when_database_check_hangs(monkeypatch: MonkeyPatch) -> None:
    def slow_database() -> bool:
        time.sleep(0.05)
        return True

    monkeypatch.setattr(api_main, "_database_readiness", slow_database)
    monkeypatch.setattr(api_main, "_redis_readiness", lambda _url: True)
    monkeypatch.setattr(api_main, "READINESS_TIMEOUT_SECONDS", 0.001)

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["checks"] == {"dependency_timeout": False}


def test_readiness_only_requires_database_and_redis(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_database_readiness", lambda: True)
    monkeypatch.setattr(api_main, "_redis_readiness", lambda _url: True)

    response = TestClient(app).get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": True, "redis": True},
    }


def test_readiness_fails_when_redis_is_unavailable(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_database_readiness", lambda: True)
    monkeypatch.setattr(api_main, "_redis_readiness", lambda _url: False)

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "status": "not_ready",
        "checks": {"database": True, "redis": False},
    }


def test_metrics_exposes_queue_outbox_and_stalled_job_series(
    monkeypatch: MonkeyPatch,
) -> None:
    class FakeRedis:
        def ping(self) -> bool:
            return True

        def llen(self, _queue: str) -> int:
            return 3

        def close(self) -> None:
            pass

    def no_database() -> None:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(api_main.Redis, "from_url", lambda *_args, **_kwargs: FakeRedis())
    monkeypatch.setattr(api_main, "SessionLocal", no_database)

    response = TestClient(app).get("/metrics")

    assert response.status_code == 200
    assert 'ezeus_celery_queue_depth{queue="normal"} 3.0' in response.text
    assert "ezeus_broker_reachable 1.0" in response.text
    assert "ezeus_outbox_depth" in response.text
    assert "ezeus_stalled_jobs" in response.text
