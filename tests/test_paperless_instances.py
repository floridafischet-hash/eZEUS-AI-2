from collections.abc import Generator

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from core.config.settings import get_settings
from core.db.base import Base
from core.db.session import get_db
from core.models.document import Document
from core.models.paperless_instance import PaperlessInstance
from core.queue.adapter import QueueAdapter


def test_instance_credentials_are_encrypted_and_webhook_selects_source(
    monkeypatch,
) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)

    def database() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    encryption_key = Fernet.generate_key().decode()
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", encryption_key)
    monkeypatch.setenv("ADMIN_API_SECRET", "test-admin-secret")
    get_settings.cache_clear()
    monkeypatch.setattr(
        QueueAdapter,
        "enqueue_document_job",
        lambda *_args, **_kwargs: None,
    )
    app.dependency_overrides[get_db] = database
    try:
        client = TestClient(app)
        create_response = client.post(
            "/api/paperless-instances",
            headers={"X-EZEUS-Admin-Secret": "test-admin-secret"},
            json={
                "name": "Externes Paperless",
                "base_url": "https://paperless.example.test",
                "api_token": "plain-api-token",
                "webhook_secret": "plain-webhook-secret",
            },
        )
        assert create_response.status_code == 201
        assert (
            create_response.json()["webhook_path"] == "/webhooks/paperless/paperless-example-test"
        )

        with session_factory() as db:
            instance = db.scalar(select(PaperlessInstance))
            assert instance is not None
            assert "plain-api-token" not in instance.api_token_encrypted
            assert "plain-webhook-secret" not in instance.webhook_secret_encrypted

        listed = client.get(
            "/api/paperless-instances",
            headers={"X-EZEUS-Admin-Secret": "test-admin-secret"},
        )
        assert listed.status_code == 200
        serialized = str(listed.json())
        assert "plain-api-token" not in serialized
        assert "plain-webhook-secret" not in serialized

        unauthorized = client.post(
            "/webhooks/paperless/paperless-example-test",
            headers={"X-EZEUS-Webhook-Secret": "wrong-secret-value"},
            json={"document_id": 42, "event_id": "created-42"},
        )
        assert unauthorized.status_code == 401

        accepted = client.post(
            "/webhooks/paperless/paperless-example-test",
            headers={"X-EZEUS-Webhook-Secret": "plain-webhook-secret"},
            json={"document_id": 42, "event_id": "created-42"},
        )
        assert accepted.status_code == 202

        accepted_without_slug = client.post(
            "/webhooks/paperless",
            headers={"X-EZEUS-Webhook-Secret": "plain-webhook-secret"},
            json={"document_id": 43, "event_id": "created-43"},
        )
        assert accepted_without_slug.status_code == 202
        with session_factory() as db:
            documents = db.scalars(
                select(Document).order_by(Document.external_document_id)
            ).all()
            assert [document.connector for document in documents] == [
                "paperless:paperless-example-test",
                "paperless:paperless-example-test",
            ]
            assert [document.external_document_id for document in documents] == ["42", "43"]
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_instance_admin_page_is_available() -> None:
    response = TestClient(app).get("/admin/instances")
    assert response.status_code == 200
    assert "Paperless-Instanzen" in response.text
    assert response.text.count('<form id="instance-form">') == 1
    assert 'id="admin-secret"' in response.text
    assert "Admin-Secret" in response.text
    assert 'id="name"' in response.text
    assert 'id="base-url"' in response.text
    assert 'id="api-token"' in response.text
    assert 'id="webhook-secret"' in response.text
    assert "Instanz vollständig speichern" in response.text


def test_unscoped_webhook_rejects_secret_shared_by_multiple_instances(
    monkeypatch,
) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)

    def database() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("ADMIN_API_SECRET", "test-admin-secret")
    get_settings.cache_clear()
    monkeypatch.setattr(
        QueueAdapter,
        "enqueue_document_job",
        lambda *_args, **_kwargs: None,
    )
    app.dependency_overrides[get_db] = database
    try:
        client = TestClient(app)
        shared_secret = "shared-webhook-secret"
        for name, base_url in (
            ("Paperless A", "https://paperless-a.example.test"),
            ("Paperless B", "https://paperless-b.example.test"),
        ):
            response = client.post(
                "/api/paperless-instances",
                headers={"X-EZEUS-Admin-Secret": "test-admin-secret"},
                json={
                    "name": name,
                    "base_url": base_url,
                    "api_token": f"{name}-api-token",
                    "webhook_secret": shared_secret,
                },
            )
            assert response.status_code == 201

        response = client.post(
            "/webhooks/paperless",
            headers={"X-EZEUS-Webhook-Secret": shared_secret},
            json={"document_id": 42, "event_id": "created-42"},
        )

        assert response.status_code == 409
        assert "instance-specific webhook URL" in response.json()["detail"]
        with session_factory() as db:
            assert db.scalar(select(Document)) is None
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
