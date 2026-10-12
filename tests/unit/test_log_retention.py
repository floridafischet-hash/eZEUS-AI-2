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
        old = Job(
            document=Document(connector="paperless:test", external_document_id="old"),
            status=JobStatus.COMPLETED,
            finished_at=now - timedelta(days=21),
        )
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
        db.add_all([old, recent, active])
        db.commit()
        old_id, recent_id, active_id = old.id, recent.id, active.id

        assert purge_expired_logs(db, retention_days=20) == 1
        assert db.get(Job, old_id) is None
        assert db.get(Job, recent_id) is not None
        assert db.get(Job, active_id) is not None
