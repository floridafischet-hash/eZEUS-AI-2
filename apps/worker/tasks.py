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
from core.logging import describe_exception
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
    extra = {"job_id": str(job_id), "worker_id": worker_id}
    if job is None:
        logger.warning("Auftrag übersprungen: nicht in der Datenbank vorhanden", extra=extra)
        return False
    if job.status not in claimable:
        logger.info(
            "Auftrag übersprungen: Status %s erlaubt keine Übernahme (erneute Zustellung=%s)",
            job.status.value,
            redelivered,
            extra=extra,
        )
        return False
    if job.status == JobStatus.RUNNING:
        logger.warning(
            "Auftrag wird nach erneuter Zustellung übernommen; vorheriger Worker %s wurde "
            "vermutlich unterbrochen (Absturz, Speichermangel oder Zeitlimit)",
            job.worker_id,
            extra=extra,
        )
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
    logger.info("Verarbeitungsauftrag empfangen", extra=extra)
    try:
        with SessionLocal() as db:
            delivery_info = self.request.delivery_info or {}
            if not _claim_job(
                db,
                parsed_job_id,
                worker_id,
                redelivered=bool(delivery_info.get("redelivered")),
            ):
                return
            logger.info("Auftrag übernommen; Dokumentverarbeitung startet", extra=extra)
            asyncio.run(Orchestrator(db).process(parsed_job_id))
        logger.info("Verarbeitungsauftrag abgeschlossen", extra=extra)
    except ConnectorError as exc:
        if not exc.retryable or self.request.retries >= settings.job_max_retries:
            logger.error(
                "Auftrag endgültig fehlgeschlagen: %s; keine automatische Wiederholung (%s)",
                type(exc).__name__,
                (
                    f"Wiederholungen ausgeschöpft: {self.request.retries}"
                    f"/{settings.job_max_retries}"
                    if exc.retryable
                    else "Fehlerart wird nicht wiederholt"
                ),
                exc_info=exc,
                extra=extra,
            )
            raise
        delay_index = min(self.request.retries, len(settings.job_retry_delays_seconds) - 1)
        retry_delay = settings.job_retry_delays_seconds[delay_index]
        logger.warning(
            "Auftrag fehlgeschlagen: %s: %s; Wiederholung in %d s (Wiederholung %d von %d)",
            type(exc).__name__,
            redact_sensitive_text(describe_exception(exc)),
            retry_delay,
            self.request.retries + 1,
            settings.job_max_retries,
            extra=extra,
        )
        with SessionLocal() as db:
            job = db.get(Job, parsed_job_id)
            if job:
                job.status = JobStatus.RETRY_WAITING
                job.retry_count = self.request.retries + 1
                job.finished_at = None
                job.error_type = type(exc).__name__
                job.error_message = redact_sensitive_text(describe_exception(exc))
                job.updated_at = datetime.now(UTC)
                db.commit()
        raise self.retry(
            exc=exc,
            countdown=retry_delay,
        ) from exc
    except Exception as exc:
        logger.error(
            "Auftrag endgültig fehlgeschlagen: %s; keine automatische Wiederholung "
            "(Fehlerart wird nicht wiederholt)",
            type(exc).__name__,
            exc_info=exc,
            extra=extra,
        )
        raise
