import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.config.settings import get_settings
from core.db.session import get_db
from core.events.document_imported import DocumentImportedEvent
from core.jobs.service import JobService
from core.models.enums import JobPriority
from core.paperless.service import (
    AmbiguousWebhookSecretError,
    connector_name,
    find_enabled_instance_by_webhook_secret,
    get_enabled_instance,
)
from core.queue.outbox import publish_outbox_event
from core.security.credentials import CredentialEncryptionError, decrypt_credential
from webhooks.paperless.schemas import PaperlessWebhookPayload
from webhooks.paperless.security import verify_shared_secret

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/paperless", tags=["webhooks"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def receive_paperless_webhook(
    payload: PaperlessWebhookPayload,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    x_ezeus_webhook_secret: str | None = Header(default=None),
) -> dict[str, str | bool]:
    settings = get_settings()
    try:
        instance = find_enabled_instance_by_webhook_secret(db, x_ezeus_webhook_secret)
    except AmbiguousWebhookSecretError as exc:
        logger.warning("Webhook 409: ambiguous secret matches multiple instances")
        raise HTTPException(
            status_code=409,
            detail=(
                "Webhook secret matches multiple Paperless instances; "
                "use the instance-specific webhook URL"
            ),
        ) from exc
    if instance is not None:
        return _accept_event(
            payload,
            response,
            db,
            connector=connector_name(instance.slug),
            source_prefix=str(instance.id),
        )
    if not verify_shared_secret(x_ezeus_webhook_secret, settings.paperless_webhook_secret):
        logger.warning("Webhook 401: invalid shared secret for legacy endpoint")
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    return _accept_event(payload, response, db, connector="paperless", source_prefix="legacy")


@router.post("/{instance_slug}", status_code=status.HTTP_202_ACCEPTED)
def receive_instance_webhook(
    instance_slug: str,
    payload: PaperlessWebhookPayload,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    x_ezeus_webhook_secret: str | None = Header(default=None),
) -> dict[str, str | bool]:
    instance = get_enabled_instance(db, instance_slug)
    if instance is None:
        logger.warning("Webhook 404: instance not found: %s", instance_slug)
        raise HTTPException(status_code=404, detail="Paperless instance not found")
    try:
        expected_secret = decrypt_credential(instance.webhook_secret_encrypted)
    except CredentialEncryptionError as exc:
        logger.error(
            "Webhook 503: credential decryption failed for instance %s", instance_slug, exc_info=exc
        )
        raise HTTPException(status_code=503, detail="Credential service unavailable") from exc
    if not verify_shared_secret(x_ezeus_webhook_secret, expected_secret):
        logger.warning(
            "Webhook 401: invalid secret for instance %s",
            instance_slug,
            extra={"instance_slug": instance_slug},
        )
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    return _accept_event(
        payload,
        response,
        db,
        connector=connector_name(instance.slug),
        source_prefix=str(instance.id),
    )


def _accept_event(
    payload: PaperlessWebhookPayload,
    response: Response,
    db: Session,
    *,
    connector: str,
    source_prefix: str,
) -> dict[str, str | bool]:
    event = DocumentImportedEvent(
        connector=connector,
        external_document_id=str(payload.document_id),
        source_event_id=f"{source_prefix}:{payload.event_id}" if payload.event_id else None,
        payload=payload.model_dump(),
    )
    try:
        service = JobService(db)
        job, created, outbox = service.create_from_event(event, priority=JobPriority.NORMAL)
        if outbox is not None:
            publish_outbox_event(db, event_id=outbox.id)
        else:
            response.status_code = status.HTTP_200_OK
        return {
            "accepted": True,
            "job_id": str(job.id),
            "created": created,
            "status": job.status.value,
        }
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Webhook 503: job service unavailable", exc_info=exc)
        raise HTTPException(status_code=503, detail="Job service unavailable") from exc
