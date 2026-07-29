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
from core.models.document import Document
from core.models.job import Job
from core.models.paperless_instance import PaperlessInstance


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
    assert 'id="log-instance"' in response.text
    assert '<option value="5000">5.000</option>' in response.text


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
        assert response.json()["instances"] == []
    finally:
        app.dependency_overrides.clear()


def populated_log_db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)
    with session_factory() as session:
        first = PaperlessInstance(
            name="Kunde A",
            slug="kunde-a",
            base_url="https://a.example.test",
            api_token_encrypted="encrypted",
            webhook_secret_encrypted="encrypted",
        )
        second = PaperlessInstance(
            name="Kunde B",
            slug="kunde-b",
            base_url="https://b.example.test",
            api_token_encrypted="encrypted",
            webhook_secret_encrypted="encrypted",
        )
        first_document = Document(
            connector="paperless:kunde-a",
            external_document_id="101",
            filename="a.pdf",
        )
        second_document = Document(
            connector="paperless:kunde-b",
            external_document_id="202",
            filename="b.pdf",
        )
        session.add_all(
            [
                first,
                second,
                first_document,
                second_document,
                Job(document=first_document),
                Job(document=second_document),
            ]
        )
        session.commit()
        yield session


def test_processing_logs_filter_by_instance_and_return_urls() -> None:
    app.dependency_overrides[get_db] = populated_log_db
    try:
        client = TestClient(app)
        response = client.get("/api/logs?instance_slug=kunde-a&limit=5000")
        assert response.status_code == 200
        payload = response.json()
        assert [entry["document_id"] for entry in payload["entries"]] == ["101"]
        assert payload["entries"][0]["instance_name"] == "Kunde A"
        assert [instance["base_url"] for instance in payload["instances"]] == [
            "https://a.example.test",
            "https://b.example.test",
        ]
    finally:
        app.dependency_overrides.clear()


def test_processing_logs_reject_unknown_instance_and_excessive_limit() -> None:
    app.dependency_overrides[get_db] = populated_log_db
    try:
        client = TestClient(app)
        assert client.get("/api/logs?instance_slug=missing").status_code == 404
        assert client.get("/api/logs?limit=5001").status_code == 422
    finally:
        app.dependency_overrides.clear()
