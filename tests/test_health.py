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
    def slow_database() -> tuple[bool, bool]:
        time.sleep(0.05)
        return True, False

    async def paperless_ready() -> bool:
        return True

    monkeypatch.setattr(api_main, "_database_readiness", slow_database)
    monkeypatch.setattr(api_main, "_redis_readiness", lambda _url: True)
    monkeypatch.setattr(api_main, "_paperless_readiness", paperless_ready)
    monkeypatch.setattr(api_main, "READINESS_TIMEOUT_SECONDS", 0.001)

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["checks"] == {"dependency_timeout": False}
