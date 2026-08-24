from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from core.config.settings import get_settings
from core.db.base import Base
from core.db.session import get_db
from core.models.admin_user import AdminUser
from core.models.document import Document
from core.models.job import Job
from core.models.paperless_instance import PaperlessInstance
from core.security.passwords import hash_password

ADMIN_HEADERS = {"X-EZEUS-Admin-User": "admin", "X-EZEUS-Admin-Password": "test-pass"}


def _seed_admin(session: Session) -> None:
    session.add(
        AdminUser(
            username="admin",
            password_hash=hash_password("test-pass"),
            role="admin",
            enabled=True,
        )
    )
    session.commit()


def empty_db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)
    with session_factory() as session:
        _seed_admin(session)
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
    assert 'new URLSearchParams({limit: "50"})' in response.text
    assert 'btn.textContent = "Mehr laden"' in response.text
    assert 'id="log-limit"' not in response.text
    assert "Dokument-ID, Dateiname, Status oder Job-ID" in response.text


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


def test_processing_logs_require_authentication() -> None:
    app.dependency_overrides[get_db] = empty_db
    try:
        client = TestClient(app)
        assert client.get("/api/logs").status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_processing_logs_are_empty_without_jobs() -> None:
    app.dependency_overrides[get_db] = empty_db
    try:
        client = TestClient(app)
        response = client.get("/api/logs", headers=ADMIN_HEADERS)
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
        _seed_admin(session)
        yield session


def test_processing_logs_filter_by_instance_and_return_urls() -> None:
    app.dependency_overrides[get_db] = populated_log_db
    try:
        client = TestClient(app)
        response = client.get("/api/logs?instance_slug=kunde-a&limit=100", headers=ADMIN_HEADERS)
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
        unknown_instance = client.get(
            "/api/logs?instance_slug=missing", headers=ADMIN_HEADERS
        )
        assert unknown_instance.status_code == 404
        assert client.get("/api/logs?limit=501", headers=ADMIN_HEADERS).status_code == 422
    finally:
        app.dependency_overrides.clear()


def paginated_log_db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)
    with session_factory() as session:
        created_at = datetime(2026, 1, 1, tzinfo=UTC)
        for index in range(3):
            document = Document(
                connector="paperless:kunde-a",
                external_document_id=str(index),
                filename=f"{index}.pdf",
            )
            session.add(
                Job(
                    id=UUID(int=index + 1),
                    document=document,
                    created_at=created_at if index > 0 else created_at - timedelta(seconds=1),
                )
            )
        session.commit()
        _seed_admin(session)
        yield session


def test_processing_logs_paginate_stably_with_equal_timestamps() -> None:
    app.dependency_overrides[get_db] = paginated_log_db
    try:
        client = TestClient(app)
        first = client.get("/api/logs?limit=1", headers=ADMIN_HEADERS)
        assert first.status_code == 200
        first_payload = first.json()
        assert [entry["document_id"] for entry in first_payload["entries"]] == ["2"]
        assert first_payload["has_more"] is True

        second = client.get(
            "/api/logs",
            params={"limit": 1, "before": first_payload["next_cursor"]},
            headers=ADMIN_HEADERS,
        )
        assert second.status_code == 200
        second_payload = second.json()
        assert [entry["document_id"] for entry in second_payload["entries"]] == ["1"]
        assert second_payload["has_more"] is True

        third = client.get(
            "/api/logs",
            params={"limit": 1, "before": second_payload["next_cursor"]},
            headers=ADMIN_HEADERS,
        )
        assert third.status_code == 200
        assert [entry["document_id"] for entry in third.json()["entries"]] == ["0"]
        assert third.json()["has_more"] is False
        assert third.json()["next_cursor"] is None
    finally:
        app.dependency_overrides.clear()


def test_processing_logs_reject_invalid_cursor() -> None:
    app.dependency_overrides[get_db] = populated_log_db
    try:
        response = TestClient(app).get(
            "/api/logs", params={"before": "not-a-cursor"}, headers=ADMIN_HEADERS
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
