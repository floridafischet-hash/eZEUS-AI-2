from collections.abc import Generator
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from connectors.paperless.connector import PaperlessConnector
from core.config.settings import get_settings
from core.db.base import Base
from core.db.session import get_db
from core.models.admin_user import AdminUser
from core.models.audit import AuditEntry
from core.models.document import Document
from core.models.paperless_instance import PaperlessInstance
from core.queue.adapter import QueueAdapter
from core.security.passwords import hash_password

ADMIN_HEADERS = {
    "X-EZEUS-Admin-User": "test-admin",
    "X-EZEUS-Admin-Password": "test-admin-password",
}


def _seed_admin(session_factory: sessionmaker[Session]) -> None:
    with session_factory.begin() as db:
        db.add(
            AdminUser(
                username="test-admin",
                password_hash=hash_password("test-admin-password"),
                role="admin",
                enabled=True,
            )
        )


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
    _seed_admin(session_factory)

    def database() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    encryption_key = Fernet.generate_key().decode()
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", encryption_key)
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
            headers=ADMIN_HEADERS,
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
            headers=ADMIN_HEADERS,
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
            documents = db.scalars(select(Document).order_by(Document.external_document_id)).all()
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
    assert 'href="/static/ezeus-ui.css"' in response.text
    assert 'src="/static/ezeus-logo.png"' in response.text
    assert response.text.count('<form id="instance-form">') == 1
    assert 'id="admin-username"' in response.text
    assert 'id="admin-password"' in response.text
    assert 'id="name"' in response.text
    assert 'id="base-url"' in response.text
    assert 'id="api-token"' in response.text
    assert "eZEUS erzeugt das Secret sicher" in response.text
    assert "Instanz speichern" in response.text
    assert 'id="edit-instance-dialog"' in response.text
    assert 'id="edit-name"' in response.text
    assert 'id="edit-api-token"' in response.text
    assert "Bearbeiten" in response.text
    assert "Endgültig löschen" in response.text


def test_only_disabled_instance_can_be_deleted_and_deletion_is_audited(
    monkeypatch,
) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)
    _seed_admin(session_factory)

    def database() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    app.dependency_overrides[get_db] = database
    try:
        client = TestClient(app)
        created = client.post(
            "/api/paperless-instances",
            headers=ADMIN_HEADERS,
            json={
                "name": "Zu löschende Instanz",
                "base_url": "https://delete.example.test",
                "api_token": "api-token",
                "webhook_secret": "webhook-secret-long-enough",
            },
        ).json()
        endpoint = f"/api/paperless-instances/{created['id']}"

        active_delete = client.delete(endpoint, headers=ADMIN_HEADERS)
        assert active_delete.status_code == 409
        assert "deaktiviert" in active_delete.json()["detail"]

        disabled = client.patch(
            endpoint,
            headers=ADMIN_HEADERS,
            json={"enabled": False},
        )
        assert disabled.status_code == 200

        deleted = client.delete(endpoint, headers=ADMIN_HEADERS)
        assert deleted.status_code == 204
        assert deleted.content == b""

        with session_factory() as db:
            assert db.get(PaperlessInstance, UUID(created["id"])) is None
            update_audit = db.scalar(
                select(AuditEntry).where(AuditEntry.action == "UPDATE_PAPERLESS_INSTANCE")
            )
            assert update_audit is not None
            assert update_audit.instance_id is None
            delete_audit = db.scalar(
                select(AuditEntry).where(AuditEntry.action == "DELETE_PAPERLESS_INSTANCE")
            )
            assert delete_audit is not None
            assert delete_audit.actor == "test-admin"
            assert delete_audit.instance_id is None
            assert delete_audit.old_value["name"] == "Zu löschende Instanz"

        assert client.delete(endpoint, headers=ADMIN_HEADERS).status_code == 404
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_instance_can_be_edited_without_exposing_or_replacing_secrets(
    monkeypatch,
) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)
    _seed_admin(session_factory)

    def database() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    app.dependency_overrides[get_db] = database
    try:
        client = TestClient(app)
        headers = ADMIN_HEADERS
        created = client.post(
            "/api/paperless-instances",
            headers=headers,
            json={
                "name": "Alter Name",
                "base_url": "https://old.example.test",
                "api_token": "existing-api-token",
                "webhook_secret": "existing-webhook-secret",
            },
        ).json()
        with session_factory() as db:
            before = db.get(PaperlessInstance, UUID(created["id"]))
            assert before is not None
            old_token = before.api_token_encrypted
            old_secret = before.webhook_secret_encrypted
            old_slug = before.slug

        response = client.patch(
            f"/api/paperless-instances/{created['id']}",
            headers=headers,
            json={
                "name": "Neuer Name",
                "base_url": "https://new.example.test",
                "verify_tls": False,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Neuer Name"
        assert body["base_url"] == "https://new.example.test"
        assert body["slug"] == old_slug
        assert "existing-api-token" not in str(body)
        assert "existing-webhook-secret" not in str(body)

        with session_factory() as db:
            updated = db.get(PaperlessInstance, UUID(created["id"]))
            assert updated is not None
            assert updated.api_token_encrypted == old_token
            assert updated.webhook_secret_encrypted == old_secret
            audit = db.scalar(
                select(AuditEntry).where(AuditEntry.action == "UPDATE_PAPERLESS_INSTANCE")
            )
            assert audit is not None
            assert audit.instance_id == updated.id
            assert audit.new_value["api_token_replaced"] is False
            assert "existing-api-token" not in str(audit.new_value)
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_shared_design_assets_are_available() -> None:
    client = TestClient(app)
    stylesheet = client.get("/static/ezeus-ui.css")
    logo = client.get("/static/ezeus-logo.png")
    assert stylesheet.status_code == 200
    assert "--color-brand: #e53935" in stylesheet.text
    assert logo.status_code == 200
    assert logo.headers["content-type"] == "image/png"


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
    _seed_admin(session_factory)

    def database() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
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
                headers=ADMIN_HEADERS,
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


def _create_instance_for_test_connection(monkeypatch) -> tuple:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)
    _seed_admin(session_factory)

    def database() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    app.dependency_overrides[get_db] = database
    client = TestClient(app)
    created = client.post(
        "/api/paperless-instances",
        headers=ADMIN_HEADERS,
        json={
            "name": "Verbindungstest",
            "base_url": "https://paperless.example.test",
            "api_token": "plain-api-token",
            "webhook_secret": "plain-webhook-secret",
        },
    ).json()
    # Enable PUBLIC_WEBHOOK_BASE_URL only after creation so the create-time
    # auto-provisioning path (a separate feature) isn't exercised here.
    monkeypatch.setenv("PUBLIC_WEBHOOK_BASE_URL", "https://ezeus.example.test")
    get_settings.cache_clear()

    async def fake_health_check(self) -> bool:
        return True

    monkeypatch.setattr(PaperlessConnector, "health_check", fake_health_check)
    return client, created


def test_test_connection_reports_missing_workflow(monkeypatch) -> None:
    client, created = _create_instance_for_test_connection(monkeypatch)

    async def fake_find(self, webhook_url: str) -> None:
        return None

    monkeypatch.setattr(PaperlessConnector, "find_webhook_workflow", fake_find)
    try:
        response = client.post(
            f"/api/paperless-instances/{created['id']}/test",
            headers=ADMIN_HEADERS,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["reachable"] is True
        assert body["webhook_configured"] is False
        assert "kein Workflow" in body["detail"]
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_test_connection_warns_about_update_trigger_loop(monkeypatch) -> None:
    client, created = _create_instance_for_test_connection(monkeypatch)

    async def fake_find(self, webhook_url: str) -> dict[str, object]:
        return {
            "workflow_id": 7,
            "workflow_name": "eZEUS-AI-2 – automatische Dokumentverarbeitung",
            "enabled": True,
            "trigger_types": [2, 3],
        }

    monkeypatch.setattr(PaperlessConnector, "find_webhook_workflow", fake_find)
    try:
        response = client.post(
            f"/api/paperless-instances/{created['id']}/test",
            headers=ADMIN_HEADERS,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["reachable"] is True
        assert body["webhook_configured"] is False
        assert body["has_update_trigger_warning"] is True
        assert "Endlosschleife" in body["detail"]
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_test_connection_confirms_correctly_configured_workflow(monkeypatch) -> None:
    client, created = _create_instance_for_test_connection(monkeypatch)

    async def fake_find(self, webhook_url: str) -> dict[str, object]:
        return {
            "workflow_id": 7,
            "workflow_name": "eZEUS-AI-2 – automatische Dokumentverarbeitung",
            "enabled": True,
            "trigger_types": [2],
        }

    monkeypatch.setattr(PaperlessConnector, "find_webhook_workflow", fake_find)
    try:
        response = client.post(
            f"/api/paperless-instances/{created['id']}/test",
            headers=ADMIN_HEADERS,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["reachable"] is True
        assert body["webhook_configured"] is True
        assert body["has_update_trigger_warning"] is False
        assert "korrekt eingerichtet" in body["detail"]
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
