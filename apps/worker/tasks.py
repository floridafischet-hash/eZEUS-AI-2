import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from celery import Task
from sqlalchemy import select
from sqlalchemy.orm import Session

from connectors.base.errors import ConnectorError
from core.config.settings import get_settings
from core.db.session import SessionLocal
from core.models.enums import JobStatus
from core.models.job import Job
from core.orchestration.orchestrator import Orchestrator
from core.queue.celery_app import celery_app
from core.security.redaction import redact_sensitive_text

logger = logging.getLogger(__name__)


def _claim_job(
    db: Session,
    job_id: UUID,
    worker_id: str,
    *,
    redelivered: bool = False,
) -> bool:
    job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
    claimable = {JobStatus.QUEUED, JobStatus.RETRY_WAITING}
    if redelivered:
        # Celery uses late acknowledgements and rejects messages when a worker
        # dies.  The broker marks that delivery, so a RUNNING database row may
        # safely be recovered instead of being acknowledged as a duplicate.
        claimable.add(JobStatus.RUNNING)
    if job is None or job.status not in claimable:
        return False
    job.status = JobStatus.RUNNING
    job.worker_id = worker_id
    db.commit()
    return True


@celery_app.task(name="ezeus.process_document_job", bind=True, acks_late=True)  # type: ignore[untyped-decorator]
def process_document_job(self: Task, job_id: str) -> None:
    settings = get_settings()
    parsed_job_id = UUID(job_id)
    worker_id = str(self.request.hostname)
    extra = {"job_id": job_id, "worker_id": worker_id}
    logger.info("Task received", extra=extra)
    try:
        with SessionLocal() as db:
            delivery_info = self.request.delivery_info or {}
            if not _claim_job(
                db,
                parsed_job_id,
                worker_id,
                redelivered=bool(delivery_info.get("redelivered")),
            ):
                logger.info("Task skipped (not claimable)", extra=extra)
                return
            logger.info("Task claimed, starting processing", extra=extra)
            asyncio.run(Orchestrator(db).process(parsed_job_id))
        logger.info("Task completed", extra=extra)
    except ConnectorError as exc:
        if not exc.retryable or self.request.retries >= settings.job_max_retries:
            logger.error("Task failed (not retryable): %s", type(exc).__name__,
                         exc_info=exc, extra=extra)
            raise
        delay_index = min(self.request.retries, len(settings.job_retry_delays_seconds) - 1)
        retry_delay = settings.job_retry_delays_seconds[delay_index]
        logger.warning("Task retrying in %ds (attempt %d): %s", retry_delay,
                        self.request.retries + 1, type(exc).__name__, extra=extra)
        with SessionLocal() as db:
            job = db.get(Job, parsed_job_id)
            if job:
                job.status = JobStatus.RETRY_WAITING
                job.retry_count = self.request.retries + 1
                job.finished_at = None
                job.error_type = type(exc).__name__
                job.error_message = redact_sensitive_text(exc)
                job.updated_at = datetime.now(UTC)
                db.commit()
        raise self.retry(
            exc=exc,
            countdown=retry_delay,
        ) from exc
