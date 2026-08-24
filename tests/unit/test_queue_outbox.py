from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from apps.worker.tasks import _claim_job
from core.config.settings import Settings
from core.db.base import Base
from core.models.document import Document
from core.models.enums import JobPriority, JobStatus
from core.models.job import Job
from core.models.queue_outbox import QueueOutbox
from core.queue.outbox import PENDING, PUBLISHED, add_job_to_outbox, publish_outbox_event


class RecordingQueue:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[object, JobPriority]] = []

    def enqueue_document_job(self, job_id, priority: JobPriority) -> None:
        self.calls.append((job_id, priority))
        if self.fail:
            raise RuntimeError("broker password=do-not-store")


def _database() -> tuple[sessionmaker[Session], object, object]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session)
    with factory() as db:
        document = Document(connector="paperless", external_document_id=str(uuid4()))
        job = Job(document=document, status=JobStatus.RECEIVED, priority=JobPriority.HIGH)
        db.add(job)
        db.flush()
        outbox = add_job_to_outbox(db, job)
        db.commit()
        return factory, job.id, outbox.id


def test_outbox_publishes_durable_job() -> None:
    factory, job_id, event_id = _database()
    queue = RecordingQueue()

    with factory() as db:
        result = publish_outbox_event(
            db,
            event_id=event_id,
            adapter=queue,  # type: ignore[arg-type]
            settings=Settings(),
        )

    assert result.published == 1
    assert queue.calls == [(job_id, JobPriority.HIGH)]
    with factory() as db:
        assert db.get(Job, job_id).status == JobStatus.QUEUED  # type: ignore[union-attr]
        assert db.get(QueueOutbox, event_id).status == PUBLISHED  # type: ignore[union-attr]


def test_failed_publish_remains_pending_and_redacts_error() -> None:
    factory, _job_id, event_id = _database()
    queue = RecordingQueue(fail=True)

    with factory() as db:
        result = publish_outbox_event(
            db,
            event_id=event_id,
            adapter=queue,  # type: ignore[arg-type]
            settings=Settings(outbox_max_backoff_seconds=10),
        )

    assert result.failed == 1
    with factory() as db:
        event = db.scalar(select(QueueOutbox).where(QueueOutbox.id == event_id))
        assert event is not None
        assert event.status == PENDING
        assert "do-not-store" not in (event.last_error or "")
        assert "[REDACTED]" in (event.last_error or "")


def test_worker_claim_deduplicates_normal_delivery_and_recovers_redelivery() -> None:
    factory, job_id, _event_id = _database()

    with factory() as db:
        assert _claim_job(db, job_id, "worker-1") is True
    with factory() as db:
        assert _claim_job(db, job_id, "worker-2") is False
    with factory() as db:
        assert _claim_job(db, job_id, "worker-2", redelivered=True) is True
        job = db.get(Job, job_id)
        assert job is not None
        assert job.worker_id == "worker-2"


def test_busy_instance_is_downgraded_without_delaying_other_instance() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(max_concurrent_jobs_per_instance=2)
    queue = RecordingQueue()

    with Session(engine) as db:
        for document_id in ("a-1", "a-2"):
            db.add(
                Job(
                    document=Document(
                        connector="paperless:instance-a",
                        external_document_id=document_id,
                    ),
                    status=JobStatus.RUNNING,
                    priority=JobPriority.NORMAL,
                )
            )
        overloaded_job = Job(
            document=Document(
                connector="paperless:instance-a",
                external_document_id="a-new",
            ),
            status=JobStatus.RECEIVED,
            priority=JobPriority.NORMAL,
        )
        other_instance_job = Job(
            document=Document(
                connector="paperless:instance-b",
                external_document_id="b-new",
            ),
            status=JobStatus.RECEIVED,
            priority=JobPriority.NORMAL,
        )
        db.add_all([overloaded_job, other_instance_job])
        db.flush()

        overloaded_event = add_job_to_outbox(db, overloaded_job, settings=settings)
        other_event = add_job_to_outbox(db, other_instance_job, settings=settings)
        db.commit()

        assert overloaded_job.priority == JobPriority.LOW
        assert overloaded_event.priority == JobPriority.LOW.value
        assert other_instance_job.priority == JobPriority.NORMAL
        assert other_event.priority == JobPriority.NORMAL.value
        other_job_id = other_instance_job.id

        result = publish_outbox_event(
            db,
            event_id=other_event.id,
            adapter=queue,  # type: ignore[arg-type]
            settings=settings,
        )

    assert result.published == 1
    assert queue.calls == [(other_job_id, JobPriority.NORMAL)]
