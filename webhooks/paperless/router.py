from typing import Annotated

from celery.exceptions import CeleryError
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.config.settings import get_settings
from core.db.session import get_db
from core.events.document_imported import DocumentImportedEvent
from core.jobs.service import JobService
from core.models.enums import JobPriority
from core.queue.adapter import QueueAdapter
from webhooks.paperless.schemas import PaperlessWebhookPayload
from webhooks.paperless.security import verify_shared_secret

router = APIRouter(prefix="/webhooks/paperless", tags=["webhooks"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def receive_paperless_webhook(
    payload: PaperlessWebhookPayload,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    x_ezeus_webhook_secret: str | None = Header(default=None),
) -> dict[str, str | bool]:
    settings = get_settings()
    if not verify_shared_secret(x_ezeus_webhook_secret, settings.paperless_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    event = DocumentImportedEvent(
        external_document_id=str(payload.document_id),
        source_event_id=payload.event_id,
        payload=payload.model_dump(),
    )
    try:
        service = JobService(db)
        job, created = service.create_from_event(event, priority=JobPriority.NORMAL)
        if created:
            QueueAdapter().enqueue_document_job(job.id, job.priority)
            service.mark_queued(job)
        else:
            response.status_code = status.HTTP_200_OK
        return {
            "accepted": True,
            "job_id": str(job.id),
            "created": created,
            "status": job.status.value,
        }
    except (CeleryError, SQLAlchemyError) as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Job service unavailable") from exc
