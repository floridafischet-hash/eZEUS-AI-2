from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.dashboard import PHASE_LABELS, STATUS_LABELS, explain_error
from apps.api.main import app
from core.config.settings import get_settings
from core.db.base import Base
from core.db.session import get_db
from core.models.admin_user import AdminUser
from core.models.audit import AuditEntry
from core.models.document import Document
from core.models.enums import JobPhase, JobStatus, PhaseStatus
from core.models.job import Job
from core.models.job_phase import JobPhaseEntry
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
    assert "Was ist passiert" in response.text
    assert "Technische Details" in response.text
    assert "const selectedJobIds = new Set();" in response.text
    assert "Alle ${totalMatches} Treffer auswählen" in response.text
    assert "localStorage.getItem(instanceStorageKey)" in response.text
    assert '.join("\\n");' in response.text
    assert 'id="log-instance"' in response.text
    assert 'new URLSearchParams({limit: "50"})' in response.text
    assert 'id="previous-page"' in response.text
    assert 'id="next-page"' in response.text
    assert "Seite ${currentPage + 1}" in response.text
    assert "logEntries = logEntries.concat" not in response.text
    assert 'button.textContent = "Mehr laden"' not in response.text
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
            webhook_secret_hmac="1" * 64,
        )
        second = PaperlessInstance(
            name="Kunde B",
            slug="kunde-b",
            base_url="https://b.example.test",
            api_token_encrypted="encrypted",
            webhook_secret_encrypted="encrypted",
            webhook_secret_hmac="2" * 64,
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


def test_processing_logs_searches_across_all_matching_rows() -> None:
    app.dependency_overrides[get_db] = populated_log_db
    try:
        client = TestClient(app)
        by_filename = client.get("/api/logs", params={"q": "b.pdf"}, headers=ADMIN_HEADERS)
        assert by_filename.status_code == 200
        assert [entry["document_id"] for entry in by_filename.json()["entries"]] == ["202"]

        by_instance = client.get("/api/logs", params={"q": "Kunde A"}, headers=ADMIN_HEADERS)
        assert by_instance.status_code == 200
        assert [entry["document_id"] for entry in by_instance.json()["entries"]] == ["101"]
    finally:
        app.dependency_overrides.clear()


def test_completed_processing_log_can_be_deleted_but_active_job_is_protected() -> None:
    database_generator = populated_log_db()
    session = next(database_generator)

    def database() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = database
    try:
        client = TestClient(app)
        listing = client.get("/api/logs", headers=ADMIN_HEADERS).json()["entries"]
        active_id = listing[0]["job_id"]
        assert client.delete(f"/api/logs/{active_id}", headers=ADMIN_HEADERS).status_code == 409

        job = session.get(Job, UUID(active_id))
        assert job is not None
        job.status = JobStatus.COMPLETED
        job.finished_at = datetime.now(UTC)
        session.commit()

        deleted = client.delete(f"/api/logs/{active_id}", headers=ADMIN_HEADERS)
        assert deleted.status_code == 204
        assert session.get(Job, UUID(active_id)) is None
    finally:
        app.dependency_overrides.clear()
        database_generator.close()


def test_processing_logs_reject_unknown_instance_and_excessive_limit() -> None:
    app.dependency_overrides[get_db] = populated_log_db
    try:
        client = TestClient(app)
        unknown_instance = client.get("/api/logs?instance_slug=missing", headers=ADMIN_HEADERS)
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


def test_bulk_delete_skips_active_jobs_and_writes_one_audit_entry() -> None:
    database_generator = populated_log_db()
    session = next(database_generator)

    def database() -> Generator[Session, None, None]:
        yield session

    jobs = list(session.scalars(select(Job).order_by(Job.id)).all())
    jobs[0].status = JobStatus.COMPLETED_WITH_WARNINGS
    jobs[0].finished_at = datetime.now(UTC)
    session.commit()
    app.dependency_overrides[get_db] = database
    try:
        client = TestClient(app)
        assert (
            client.post(
                "/api/logs/delete", json={"job_ids": [str(job.id) for job in jobs]}
            ).status_code
            == 401
        )
        response = client.post(
            "/api/logs/delete",
            json={"job_ids": [str(job.id) for job in jobs]},
            headers=ADMIN_HEADERS,
        )
        assert response.status_code == 200
        assert response.json() == {"deleted": 1, "skipped": 1}
        assert session.get(Job, jobs[0].id) is None
        assert session.get(Job, jobs[1].id) is not None
        audits = list(
            session.scalars(
                select(AuditEntry).where(AuditEntry.action == "DELETE_PROCESSING_LOGS")
            ).all()
        )
        assert len(audits) == 1
        assert audits[0].actor == "admin"
        assert audits[0].details["deleted"] == 1
    finally:
        app.dependency_overrides.clear()
        database_generator.close()


def test_delete_matching_respects_instance_and_removes_orphan_document() -> None:
    database_generator = populated_log_db()
    session = next(database_generator)

    def database() -> Generator[Session, None, None]:
        yield session

    jobs = list(session.scalars(select(Job).join(Document).order_by(Document.connector)).all())
    for job in jobs:
        job.status = JobStatus.CANCELLED
        job.finished_at = datetime.now(UTC)
    removed_document_id = jobs[0].document_id
    kept_document_id = jobs[1].document_id
    session.commit()
    app.dependency_overrides[get_db] = database
    try:
        response = TestClient(app).post(
            "/api/logs/delete-matching",
            json={"instance_slug": "kunde-a", "q": None},
            headers=ADMIN_HEADERS,
        )
        assert response.status_code == 200
        assert response.json() == {"deleted": 1, "skipped": 0}
        assert session.get(Document, removed_document_id) is None
        assert session.get(Document, kept_document_id) is not None
        assert session.get(Job, jobs[1].id) is not None
        audit = session.scalar(
            select(AuditEntry).where(AuditEntry.action == "DELETE_MATCHING_PROCESSING_LOGS")
        )
        assert audit is not None
        assert audit.details["filters"]["instance_slug"] == "kunde-a"
    finally:
        app.dependency_overrides.clear()
        database_generator.close()


def test_german_status_and_phase_labels_are_searchable() -> None:
    database_generator = populated_log_db()
    session = next(database_generator)

    def database() -> Generator[Session, None, None]:
        yield session

    job = session.scalar(
        select(Job).join(Document).where(Document.connector == "paperless:kunde-a")
    )
    assert job is not None
    job.status = JobStatus.COMPLETED_WITH_WARNINGS
    phase = JobPhaseEntry(
        job_id=job.id,
        phase=JobPhase.WRITE_METADATA,
        status=PhaseStatus.COMPLETED,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    session.add(phase)
    session.commit()
    app.dependency_overrides[get_db] = database
    try:
        client = TestClient(app)
        status_response = client.get(
            "/api/logs", params={"q": "mit Hinweisen"}, headers=ADMIN_HEADERS
        )
        assert [item["job_id"] for item in status_response.json()["entries"]] == [str(job.id)]
        phase_response = client.get(
            "/api/logs", params={"q": "Metadaten schreiben"}, headers=ADMIN_HEADERS
        )
        assert [item["job_id"] for item in phase_response.json()["entries"]] == [str(job.id)]
        entry = status_response.json()["entries"][0]
        assert entry["status_label"] == "Abgeschlossen mit Hinweisen"
        assert entry["deletable"] is True
    finally:
        app.dependency_overrides.clear()
        database_generator.close()


def test_error_explanations_cover_known_classes_and_redact_secrets() -> None:
    error_types = [
        "AuthenticationError",
        "AuthorizationError",
        "NotFoundError",
        "RateLimitError",
        "TimeoutError",
        "ConnectionError",
        "ConflictError",
        "ValidationError",
        "RetryableEmptyTextError",
        "OllamaResponseError",
        "StalledJob",
        "FieldConfigurationError",
        "CandidateConflict",
        "FieldWriteError",
        "SomethingUnknown",
    ]
    for error_type in error_types:
        explanation = explain_error(
            error_type,
            "Authorization: Bearer secret-token OCR: vertraulicher Inhalt",
            "WRITE_METADATA",
            document_id="123",
            field="invoice_number",
        )
        assert set(explanation) == {"was", "warum", "empfehlung", "technisch"}
        assert all(explanation.values())
        rendered = " ".join(explanation.values())
        assert "secret-token" not in rendered
        assert "vertraulicher Inhalt" not in rendered
        assert "Dokument 123" in explanation["was"]
        assert "invoice_number" in explanation["was"]
    assert STATUS_LABELS[JobStatus.RUNNING] == "In Bearbeitung"
    assert PHASE_LABELS["WRITE_METADATA"] == "Metadaten schreiben"
