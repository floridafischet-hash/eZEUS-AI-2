from __future__ import annotations

import logging
import signal
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Event

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from core.config.settings import Settings, get_settings
from core.db.session import SessionLocal
from core.jobs.retention import purge_expired_logs
from core.models.enums import JobStatus
from core.models.job import Job
from core.models.queue_outbox import QueueOutbox
from core.queue.outbox import add_job_to_outbox, publish_outbox_event

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {JobStatus.RECEIVED, JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.RETRY_WAITING}


@dataclass(frozen=True, slots=True)
class SweepResult:
    requeued: int = 0
    failed: int = 0


def _describe_stall(job: Job, runtime: Settings) -> str:
    phase = job.phase.value if job.phase else "none"
    message = (
        f"Job stalled in {job.status.value} at phase {phase} "
        f"(worker: {job.worker_id}, no update for at least "
        f"{runtime.sweeper_stale_threshold_seconds} s)"
    )
    # Do not lose the cause recorded by the last attempt when a repeat stalls.
    if job.error_type and job.error_type != "StalledJob":
        message += f"; previous error: {job.error_type}: {job.error_message}"
    elif (
        job.error_type == "StalledJob"
        and job.error_message
        and "previous error: " in job.error_message
    ):
        message += "; previous error: " + job.error_message.split("previous error: ", 1)[1]
    return message


def sweep_stale_jobs(
    db: Session,
    *,
    settings: Settings | None = None,
) -> SweepResult:
    runtime = settings or get_settings()
    threshold = datetime.now(UTC) - timedelta(seconds=runtime.sweeper_stale_threshold_seconds)
    stale_jobs = db.scalars(
        select(Job)
        .where(
            Job.status.in_(ACTIVE_STATUSES),
            Job.updated_at <= threshold,
            ~exists().where(
                QueueOutbox.job_id == Job.id,
                QueueOutbox.status == "PENDING",
                QueueOutbox.available_at > datetime.now(UTC),
            ),
        )
        .with_for_update(skip_locked=True)
    ).all()
    requeued = 0
    failed = 0
    for job in stale_jobs:
        extra = {"job_id": str(job.id), "worker_id": job.worker_id}
        stalled = _describe_stall(job, runtime)
        if job.retry_count < runtime.job_max_retries:
            job.error_type = "StalledJob"
            job.error_message = stalled
            job.started_at = None
            job.finished_at = None
            job.retry_count += 1
            outbox = add_job_to_outbox(db, job)
            db.commit()
            publish_outbox_event(db, event_id=outbox.id)
            requeued += 1
            logger.warning(
                "Stillstehenden Auftrag %s erneut eingeplant: %s", job.id, stalled, extra=extra
            )
        else:
            stalled = f"{stalled}; gave up after {job.retry_count} retries"
            job.status = JobStatus.FAILED
            job.finished_at = datetime.now(UTC)
            job.error_type = "StalledJob"
            job.error_message = stalled
            db.commit()
            failed += 1
            logger.error(
                "Stillstehenden Auftrag %s endgültig beendet: %s", job.id, stalled, extra=extra
            )
    return SweepResult(requeued=requeued, failed=failed)


def run_sweeper() -> None:
    from core.logging import configure_logging

    configure_logging()
    runtime = get_settings()
    stop = Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    logger.info(
        "Auftragsüberwachung gestartet (Intervall=%.0fs, Stillstandsgrenze=%ds)",
        runtime.sweeper_interval_seconds,
        runtime.sweeper_stale_threshold_seconds,
    )
    while not stop.is_set():
        try:
            with SessionLocal() as db:
                result = sweep_stale_jobs(db, settings=runtime)
                purged = purge_expired_logs(db, retention_days=runtime.log_retention_days)
            if result.requeued or result.failed:
                logger.info(
                    "Überwachungslauf abgeschlossen: erneut_eingeplant=%d fehlgeschlagen=%d",
                    result.requeued,
                    result.failed,
                )
            if purged:
                logger.info("%d abgelaufene Verarbeitungsprotokolle gelöscht", purged)
        except Exception:
            logger.exception(
                "Auftragsüberwachung fehlgeschlagen; Stillstandsprüfung wird im nächsten "
                "Lauf wiederholt"
            )
        stop.wait(runtime.sweeper_interval_seconds)
    logger.info("Auftragsüberwachung beendet")


if __name__ == "__main__":
    run_sweeper()
