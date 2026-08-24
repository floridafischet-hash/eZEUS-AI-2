from __future__ import annotations

import logging
import signal
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from core.config.settings import Settings, get_settings
from core.db.session import SessionLocal
from core.metrics import QUEUE_DEPTH
from core.models.document import Document
from core.models.enums import JobPriority, JobStatus
from core.models.job import Job
from core.models.queue_outbox import QueueOutbox
from core.queue.adapter import QueueAdapter
from core.security.redaction import redact_sensitive_text

logger = logging.getLogger(__name__)

PENDING = "PENDING"
PROCESSING = "PROCESSING"
PUBLISHED = "PUBLISHED"


@dataclass(frozen=True, slots=True)
class DispatchResult:
    published: int = 0
    failed: int = 0


ACTIVE_JOB_STATUSES = (
    JobStatus.RECEIVED,
    JobStatus.QUEUED,
    JobStatus.RUNNING,
    JobStatus.RETRY_WAITING,
)


def _queue_priority(db: Session, job: Job, settings: Settings) -> JobPriority:
    if job.priority != JobPriority.NORMAL:
        return job.priority
    connector = db.scalar(select(Document.connector).where(Document.id == job.document_id))
    if connector is None:
        return job.priority
    in_flight = db.scalar(
        select(func.count(Job.id))
        .join(Document, Job.document_id == Document.id)
        .where(
            Document.connector == connector,
            Job.id != job.id,
            Job.status.in_(ACTIVE_JOB_STATUSES),
        )
    )
    if int(in_flight or 0) < settings.max_concurrent_jobs_per_instance:
        return job.priority
    logger.info(
        "Routing job to low-priority queue because instance is at its in-flight limit",
        extra={
            "job_id": str(job.id),
            "instance_slug": connector.removeprefix("paperless:"),
        },
    )
    return JobPriority.LOW


def add_job_to_outbox(
    db: Session, job: Job, *, settings: Settings | None = None
) -> QueueOutbox:
    priority = _queue_priority(db, job, settings or get_settings())
    job.priority = priority
    event = QueueOutbox(job_id=job.id, priority=priority.value, status=PENDING)
    job.status = JobStatus.QUEUED
    db.add(event)
    return event


def _claim_event(
    db: Session,
    *,
    event_id: UUID | None = None,
    settings: Settings,
) -> QueueOutbox | None:
    now = datetime.now(UTC)
    stale_before = now - timedelta(seconds=settings.outbox_claim_timeout_seconds)
    query = select(QueueOutbox).where(
        or_(
            (QueueOutbox.status == PENDING) & (QueueOutbox.available_at <= now),
            (QueueOutbox.status == PROCESSING) & (QueueOutbox.claimed_at <= stale_before),
        )
    )
    if event_id is not None:
        query = query.where(QueueOutbox.id == event_id)
    event = db.scalar(
        query.order_by(QueueOutbox.available_at, QueueOutbox.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if event is None:
        return None
    event.status = PROCESSING
    event.claimed_at = now
    event.attempts += 1
    db.commit()
    db.refresh(event)
    return event


def publish_outbox_event(
    db: Session,
    *,
    event_id: UUID | None = None,
    adapter: QueueAdapter | None = None,
    settings: Settings | None = None,
) -> DispatchResult:
    runtime = settings or get_settings()
    event = _claim_event(db, event_id=event_id, settings=runtime)
    if event is None:
        return DispatchResult()
    queue = adapter or QueueAdapter()
    try:
        queue.enqueue_document_job(event.job_id, JobPriority(event.priority))
    except Exception as exc:
        event.status = PENDING
        event.claimed_at = None
        event.last_error = redact_sensitive_text(exc)
        delay = min(2 ** min(event.attempts, 16), runtime.outbox_max_backoff_seconds)
        event.available_at = datetime.now(UTC) + timedelta(seconds=delay)
        db.commit()
        logger.warning("Queue outbox publish failed for event %s: %s", event.id, event.last_error)
        QUEUE_DEPTH.labels(outcome="failed").inc()
        return DispatchResult(failed=1)
    event.status = PUBLISHED
    event.claimed_at = None
    event.published_at = datetime.now(UTC)
    event.last_error = None
    db.commit()
    QUEUE_DEPTH.labels(outcome="published").inc()
    return DispatchResult(published=1)


def dispatch_pending(
    *,
    session_factory: sessionmaker[Session] = SessionLocal,
    settings: Settings | None = None,
) -> DispatchResult:
    runtime = settings or get_settings()
    published = 0
    failed = 0
    for _ in range(runtime.outbox_batch_size):
        with session_factory() as db:
            result = publish_outbox_event(db, settings=runtime)
        published += result.published
        failed += result.failed
        if result == DispatchResult():
            break
    return DispatchResult(published=published, failed=failed)


def run_dispatcher() -> None:
    from core.logging import configure_logging
    configure_logging()
    runtime = get_settings()
    stop = Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    logger.info("Queue outbox dispatcher started")
    while not stop.is_set():
        try:
            dispatch_pending(settings=runtime)
        except Exception:
            logger.exception("Queue outbox dispatcher iteration failed")
        stop.wait(runtime.outbox_poll_seconds)
    logger.info("Queue outbox dispatcher stopped")


if __name__ == "__main__":
    run_dispatcher()
