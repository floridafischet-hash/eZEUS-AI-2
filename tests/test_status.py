from collections.abc import Generator

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import apps.api.status as api_status
from apps.api.main import app
from core.db.base import Base
from core.db.session import get_db
from core.models.admin_user import AdminUser
from core.security.passwords import hash_password

ADMIN_HEADERS = {"X-EZEUS-Admin-User": "admin", "X-EZEUS-Admin-Password": "test-pass"}


def _database() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            AdminUser(
                username="admin",
                password_hash=hash_password("test-pass"),
                role="admin",
                enabled=True,
            )
        )
        db.commit()
        yield db


def test_dependency_status_requires_authentication() -> None:
    app.dependency_overrides[get_db] = _database
    try:
        response = TestClient(app).get("/status/dependencies")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_dependency_status_is_informational(
    monkeypatch: MonkeyPatch,
) -> None:
    async def ollama_unavailable() -> dict[str, object]:
        return {"enabled": True, "reachable": False, "model_available": False}

    monkeypatch.setattr(api_status, "_ollama_status", ollama_unavailable)
    app.dependency_overrides[get_db] = _database
    try:
        response = TestClient(app).get(
            "/status/dependencies",
            headers=ADMIN_HEADERS,
        )
        assert response.status_code == 200
        assert response.json() == {
            "informational": True,
            "paperless": [],
            "ollama": {"enabled": True, "reachable": False, "model_available": False},
        }
    finally:
        app.dependency_overrides.clear()
