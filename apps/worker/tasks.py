import asyncio
from datetime import UTC, datetime
from uuid import UUID

from celery import Task

from connectors.base.errors import ConnectorError
from core.config.settings import get_settings
from core.db.session import SessionLocal
from core.models.enums import JobStatus
from core.models.job import Job
from core.orchestration.orchestrator import Orchestrator
from core.queue.celery_app import celery_app


@celery_app.task(name="ezeus.process_document_job", bind=True, acks_late=True)  # type: ignore[untyped-decorator]
def process_document_job(self: Task, job_id: str) -> None:
    settings = get_settings()
    try:
        with SessionLocal() as db:
            job = db.get(Job, UUID(job_id))
            if job:
                job.worker_id = str(self.request.hostname)
                db.commit()
            asyncio.run(Orchestrator(db).process(UUID(job_id)))
    except ConnectorError as exc:
        if not exc.retryable or self.request.retries >= settings.job_max_retries:
            raise
        delay_index = min(self.request.retries, len(settings.job_retry_delays_seconds) - 1)
        with SessionLocal() as db:
            job = db.get(Job, UUID(job_id))
            if job:
                job.status = JobStatus.RETRY_WAITING
                job.retry_count = self.request.retries + 1
                job.finished_at = None
                job.error_type = type(exc).__name__
                job.error_message = str(exc)[:4000]
                job.updated_at = datetime.now(UTC)
                db.commit()
        raise self.retry(
            exc=exc,
            countdown=settings.job_retry_delays_seconds[delay_index],
        ) from exc
