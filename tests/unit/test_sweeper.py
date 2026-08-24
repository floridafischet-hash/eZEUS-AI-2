from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.config.settings import Settings, get_settings
from core.db.base import Base
from core.models.document import Document
from core.models.enums import JobStatus
from core.models.job import Job
from core.queue.sweeper import sweep_stale_jobs


def _make_db() -> tuple[Session, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session)
    session = factory()
    return session, factory


def _settings(**overrides: object) -> Settings:
    base = get_settings()
    values = {
        "sweeper_stale_threshold_seconds": 900,
        "job_max_retries": 3,
        "redis_url": base.redis_url,
        "credential_encryption_key": base.credential_encryption_key,
    }
    values.update(overrides)
    return base.model_copy(update=values)


def _create_stale_job(
    db: Session,
    status: JobStatus,
    minutes_old: int = 30,
    retry_count: int = 0,
) -> Job:
    doc = Document(connector="paperless:test", external_document_id=str(uuid4()), filename="t.pdf")
    db.add(doc)
    db.flush()
    job = Job(document_id=doc.id, status=status, worker_id="worker-1", retry_count=retry_count)
    db.add(job)
    db.commit()
    stale_time = datetime.now(UTC) - timedelta(minutes=minutes_old)
    db.execute(
        update(Job).where(Job.id == job.id).values(updated_at=stale_time, started_at=stale_time)
    )
    db.commit()
    db.refresh(job)
    return job


def test_sweeper_requeues_stale_running_job() -> None:
    db, _ = _make_db()
    settings = _settings(sweeper_stale_threshold_seconds=600)
    job = _create_stale_job(db, JobStatus.RUNNING, minutes_old=15)

    with patch("core.queue.sweeper.publish_outbox_event"):
        result = sweep_stale_jobs(db, settings=settings)

    assert result.requeued == 1
    assert result.failed == 0
    db.refresh(job)
    assert job.status == JobStatus.QUEUED
    assert job.error_type == "StalledJob"
    assert job.retry_count == 1


def test_sweeper_fails_job_after_max_retries() -> None:
    db, _ = _make_db()
    settings = _settings(sweeper_stale_threshold_seconds=600, job_max_retries=2)
    job = _create_stale_job(db, JobStatus.RUNNING, minutes_old=15, retry_count=2)

    result = sweep_stale_jobs(db, settings=settings)

    assert result.requeued == 0
    assert result.failed == 1
    db.refresh(job)
    assert job.status == JobStatus.FAILED
    assert job.finished_at is not None


def test_sweeper_ignores_fresh_jobs() -> None:
    db, _ = _make_db()
    settings = _settings(sweeper_stale_threshold_seconds=600)
    _create_stale_job(db, JobStatus.RUNNING, minutes_old=5)

    result = sweep_stale_jobs(db, settings=settings)

    assert result.requeued == 0
    assert result.failed == 0


def test_sweeper_ignores_terminal_jobs() -> None:
    db, _ = _make_db()
    settings = _settings(sweeper_stale_threshold_seconds=60)
    job = _create_stale_job(db, JobStatus.COMPLETED, minutes_old=30)

    result = sweep_stale_jobs(db, settings=settings)

    assert result.requeued == 0
    assert result.failed == 0
    db.refresh(job)
    assert job.status == JobStatus.COMPLETED


def test_sweeper_handles_all_active_statuses() -> None:
    db, _ = _make_db()
    settings = _settings(sweeper_stale_threshold_seconds=600)
    for s in [JobStatus.RECEIVED, JobStatus.QUEUED, JobStatus.RETRY_WAITING]:
        _create_stale_job(db, s, minutes_old=15)

    with patch("core.queue.sweeper.publish_outbox_event"):
        result = sweep_stale_jobs(db, settings=settings)

    assert result.requeued == 3
