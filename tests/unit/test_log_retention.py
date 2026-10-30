from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from core.db.base import Base
from core.jobs.retention import purge_expired_logs
from core.models.document import Document
from core.models.enums import JobStatus
from core.models.job import Job


def test_retention_deletes_only_terminal_logs_older_than_twenty_days() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as db:
        old_jobs = [
            Job(
                document=Document(
                    connector="paperless:test", external_document_id=f"old-{status.value}"
                ),
                status=status,
                finished_at=now - timedelta(days=21),
            )
            for status in (
                JobStatus.COMPLETED,
                JobStatus.COMPLETED_WITH_WARNINGS,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
            )
        ]
        recent = Job(
            document=Document(connector="paperless:test", external_document_id="recent"),
            status=JobStatus.FAILED,
            finished_at=now - timedelta(days=19),
        )
        active = Job(
            document=Document(connector="paperless:test", external_document_id="active"),
            status=JobStatus.RUNNING,
            finished_at=now - timedelta(days=30),
        )
        db.add_all([*old_jobs, recent, active])
        db.commit()
        old_ids = [job.id for job in old_jobs]
        recent_id, active_id = recent.id, active.id

        assert purge_expired_logs(db, retention_days=20) == 4
        assert all(db.get(Job, job_id) is None for job_id in old_ids)
        assert db.get(Job, recent_id) is not None
        assert db.get(Job, active_id) is not None
