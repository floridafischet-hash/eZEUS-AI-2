from sqlalchemy import select
from sqlalchemy.orm import Session

from connectors.paperless.connector import PaperlessConnector
from core.models.paperless_instance import PaperlessInstance
from core.security.credentials import decrypt_credential
from webhooks.paperless.security import verify_shared_secret

CONNECTOR_PREFIX = "paperless:"


def connector_name(slug: str) -> str:
    return f"{CONNECTOR_PREFIX}{slug}"


def instance_slug_from_connector(value: str) -> str | None:
    if not value.startswith(CONNECTOR_PREFIX):
        return None
    return value.removeprefix(CONNECTOR_PREFIX)


def get_enabled_instance(db: Session, slug: str) -> PaperlessInstance | None:
    return db.scalar(
        select(PaperlessInstance).where(
            PaperlessInstance.slug == slug,
            PaperlessInstance.enabled.is_(True),
        )
    )


def find_enabled_instance_by_webhook_secret(
    db: Session, provided_secret: str | None
) -> PaperlessInstance | None:
    if provided_secret is None:
        return None
    instances = db.scalars(
        select(PaperlessInstance).where(PaperlessInstance.enabled.is_(True))
    )
    for instance in instances:
        if verify_shared_secret(
            provided_secret, decrypt_credential(instance.webhook_secret_encrypted)
        ):
            return instance
    return None


def connector_for_document(db: Session, connector: str) -> PaperlessConnector:
    slug = instance_slug_from_connector(connector)
    if slug is None:
        return PaperlessConnector()
    instance = get_enabled_instance(db, slug)
    if instance is None:
        raise ValueError(f"Paperless instance is unavailable: {slug}")
    return PaperlessConnector(
        base_url=instance.base_url,
        api_token=decrypt_credential(instance.api_token_encrypted),
        verify_tls=instance.verify_tls,
    )
