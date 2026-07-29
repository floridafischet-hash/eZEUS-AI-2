from collections.abc import Generator

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from connectors.base.interface import ConnectorCustomField
from core.config.settings import get_settings
from core.db.base import Base
from core.db.session import get_db
from core.field_config.service import FieldConfigurationService
from core.models.audit import AuditEntry
from core.models.instance_field_config import InstanceFieldConfig
from core.models.paperless_instance import PaperlessInstance
from plugins.extraction.regex import RegexExtractionProvider


@pytest.fixture
def field_config_client(
    monkeypatch,
) -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
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
    app.dependency_overrides[get_db] = database
    try:
        yield TestClient(app), session_factory
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def create_instance(client: TestClient, name: str, host: str) -> dict[str, object]:
    response = client.post(
        "/api/paperless-instances",
        headers=admin_headers(),
        json={
            "name": name,
            "base_url": f"https://{host}",
            "api_token": f"{name}-api-token",
            "webhook_secret": f"{name}-webhook-secret",
        },
    )
    assert response.status_code == 201
    return response.json()


def admin_headers(actor: str = "Administrator A") -> dict[str, str]:
    return {
        "X-EZEUS-Admin-Secret": "test-admin-secret",
        "X-EZEUS-Admin-Actor": actor,
    }


def test_url_slug_selects_tenant_and_requires_administrator(
    field_config_client,
) -> None:
    client, _ = field_config_client
    first = create_instance(client, "Kunde A", "kunde-a.example.test")
    second = create_instance(client, "Kunde B", "kunde-b.example.test")

    unauthorized = client.get(f"/api/instances/{first['slug']}/field-config")
    assert unauthorized.status_code == 401

    first_response = client.get(
        f"/api/instances/{first['slug']}/field-config", headers=admin_headers()
    )
    second_response = client.get(
        f"/api/instances/{second['slug']}/field-config", headers=admin_headers()
    )
    assert first_response.status_code == 200
    assert first_response.json()["instance"]["id"] == first["id"]
    assert second_response.json()["instance"]["id"] == second["id"]
    assert client.get(
        "/api/instances/not-a-tenant/field-config", headers=admin_headers()
    ).status_code == 404


def test_configuration_is_saved_reloaded_and_isolated_with_audit(
    field_config_client,
) -> None:
    client, session_factory = field_config_client
    first = create_instance(client, "Kunde A", "kunde-a.example.test")
    second = create_instance(client, "Kunde B", "kunde-b.example.test")
    endpoint = f"/api/instances/{first['slug']}/field-config"
    fields = client.get(endpoint, headers=admin_headers()).json()["fields"]
    for field in fields:
        if field["field_key"] == "invoice_amount":
            field["enabled"] = False
            field["required"] = False
    fields.append(
        {
            "field_key": None,
            "label": "Projektcode",
            "field_type": "select",
            "sort_order": 70,
            "enabled": True,
            "required": True,
            "ocr_enabled": True,
            "ai_enabled": True,
            "external_field_id": "77",
            "options": ["Nord", "Süd"],
            "extraction_instructions": "Nur den ausdrücklich genannten Projektcode verwenden.",
        }
    )

    saved = client.put(endpoint, headers=admin_headers("Alice"), json={"fields": fields})
    assert saved.status_code == 200
    saved_fields = saved.json()["fields"]
    custom = next(field for field in saved_fields if field["label"] == "Projektcode")
    assert custom["field_key"].startswith("custom_")
    assert custom["required"] is True

    reloaded = client.get(endpoint, headers=admin_headers()).json()["fields"]
    assert reloaded == saved_fields
    assert next(
        field for field in reloaded if field["field_key"] == "invoice_amount"
    )["enabled"] is False

    second_fields = client.get(
        f"/api/instances/{second['slug']}/field-config", headers=admin_headers()
    ).json()["fields"]
    assert next(
        field for field in second_fields if field["field_key"] == "invoice_amount"
    )["enabled"] is True
    assert all(field["label"] != "Projektcode" for field in second_fields)

    with session_factory() as db:
        first_instance = db.scalar(
            select(PaperlessInstance).where(PaperlessInstance.slug == first["slug"])
        )
        assert first_instance is not None
        audits = db.scalars(
            select(AuditEntry).where(AuditEntry.instance_id == first_instance.id)
        ).all()
        assert audits
        assert all(audit.actor == "Alice" for audit in audits)
        assert all(audit.details["tenant_slug"] == first["slug"] for audit in audits)


def test_preview_validates_fields_without_saving(field_config_client) -> None:
    client, session_factory = field_config_client
    instance = create_instance(client, "Kunde A", "kunde-a.example.test")
    endpoint = f"/api/instances/{instance['slug']}/field-config"
    fields = client.get(endpoint, headers=admin_headers()).json()["fields"]
    fields[0]["label"] = "Geänderter Vorschautext"

    preview = client.post(
        f"{endpoint}/preview", headers=admin_headers(), json={"fields": fields}
    )
    assert preview.status_code == 200
    assert preview.json()["fields"][0]["label"] == "Geänderter Vorschautext"

    with session_factory() as db:
        stored = db.scalar(
            select(InstanceFieldConfig).where(
                InstanceFieldConfig.field_key == fields[0]["field_key"]
            )
        )
        assert stored is not None
        assert stored.label != "Geänderter Vorschautext"


@pytest.mark.asyncio
async def test_runtime_extraction_uses_only_tenant_configuration(
    field_config_client,
) -> None:
    client, session_factory = field_config_client
    instance_data = create_instance(client, "Kunde A", "kunde-a.example.test")
    endpoint = f"/api/instances/{instance_data['slug']}/field-config"
    fields = client.get(endpoint, headers=admin_headers()).json()["fields"]
    for field in fields:
        if field["field_key"] == "invoice_amount":
            field["enabled"] = False
            field["required"] = False
        if field["field_key"] == "construction_site_number":
            field["enabled"] = True
            field["required"] = True
            field["ai_enabled"] = True
            field["external_field_id"] = "88"
    assert client.put(
        endpoint, headers=admin_headers(), json={"fields": fields}
    ).status_code == 200

    with session_factory() as db:
        instance = db.scalar(
            select(PaperlessInstance).where(
                PaperlessInstance.slug == instance_data["slug"]
            )
        )
        assert instance is not None
        runtime = FieldConfigurationService(db).runtime_config(
            instance,
            [
                ConnectorCustomField("14", "Rechnungsnummer", "string"),
                ConnectorCustomField("15", "Rechnungsbetrag", "monetary"),
                ConnectorCustomField("88", "Baustellennummer", "string"),
            ],
        )
        assert "invoice_amount" not in runtime.template.fields
        site = runtime.template.fields["construction_site_number"]
        assert site.required is True
        assert site.target_field_id == 88
        assert [provider.type for provider in site.providers] == ["regex", "ollama"]
        regex_config = site.providers[0].model_dump(exclude={"type"})
        candidates = await RegexExtractionProvider().extract(
            "Baustellennummer: 25164\nGesamtbetrag: 999,00 EUR",
            regex_config,
        )
        assert [candidate.value for candidate in candidates] == ["25164"]
