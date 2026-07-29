from collections.abc import Generator

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from core.config.settings import get_settings
from core.db.base import Base
from core.db.session import get_db


def empty_db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)
    with session_factory() as session:
        yield session


def test_dashboard_is_available() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Logs" in response.text
    assert "qwen3:4b" in response.text
    assert "const expandedJobIds = new Set();" in response.text
    assert "expandedJobIds.add(entry.job_id);" in response.text
    assert "Was ist passiert?" in response.text
    assert "Vollständiger Jobfehler" in response.text


def test_dashboard_uses_configured_ollama_model(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "custom-model:12b")
    get_settings.cache_clear()
    try:
        response = TestClient(app).get("/")
        assert response.status_code == 200
        assert "custom-model:12b" in response.text
        assert "qwen3:4b" not in response.text
    finally:
        get_settings.cache_clear()


def test_processing_logs_are_empty_without_jobs() -> None:
    app.dependency_overrides[get_db] = empty_db
    try:
        client = TestClient(app)
        response = client.get("/api/logs")
        assert response.status_code == 200
        assert response.json()["entries"] == []
    finally:
        app.dependency_overrides.clear()
