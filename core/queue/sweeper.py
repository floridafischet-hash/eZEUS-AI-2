from __future__ import annotations

import logging
import signal
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Event

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config.settings import Settings, get_settings
from core.db.session import SessionLocal
from core.models.enums import JobStatus
from core.models.job import Job
from core.queue.outbox import add_job_to_outbox, publish_outbox_event

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {JobStatus.RECEIVED, JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.RETRY_WAITING}


@dataclass(frozen=True, slots=True)
class SweepResult:
    requeued: int = 0
    failed: int = 0


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
        )
        .with_for_update(skip_locked=True)
    ).all()
    requeued = 0
    failed = 0
    for job in stale_jobs:
        if job.retry_count < runtime.job_max_retries:
            job.error_type = "StalledJob"
            job.error_message = f"Job stalled in {job.status.value} (worker: {job.worker_id})"
            job.started_at = None
            job.finished_at = None
            job.retry_count += 1
            outbox = add_job_to_outbox(db, job)
            db.commit()
            publish_outbox_event(db, event_id=outbox.id)
            requeued += 1
            logger.info("Requeued stale job %s (was %s)", job.id, job.status.value)
        else:
            job.status = JobStatus.FAILED
            job.finished_at = datetime.now(UTC)
            job.error_type = "StalledJob"
            job.error_message = (
                f"Job stalled in {job.status.value} after {job.retry_count} retries "
                f"(worker: {job.worker_id})"
            )
            db.commit()
            failed += 1
            logger.info("Failed stale job %s (max retries exhausted)", job.id)
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
        "Job sweeper started (interval=%.0fs, threshold=%ds)",
        runtime.sweeper_interval_seconds,
        runtime.sweeper_stale_threshold_seconds,
    )
    while not stop.is_set():
        try:
            with SessionLocal() as db:
                result = sweep_stale_jobs(db, settings=runtime)
            if result.requeued or result.failed:
                logger.info("Sweep: requeued=%d failed=%d", result.requeued, result.failed)
        except Exception:
            logger.exception("Job sweeper iteration failed")
        stop.wait(runtime.sweeper_interval_seconds)
    logger.info("Job sweeper stopped")


if __name__ == "__main__":
    run_sweeper()
