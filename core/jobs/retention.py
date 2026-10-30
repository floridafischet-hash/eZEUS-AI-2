from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from core.models.audit import AuditEntry
from core.models.document import Document
from core.models.enums import JobStatus
from core.models.extraction import ExtractionResult
from core.models.job import Job
from core.models.job_phase import JobPhaseEntry
from core.models.queue_outbox import QueueOutbox

TERMINAL_STATUSES = frozenset(
    {
        JobStatus.COMPLETED,
        JobStatus.COMPLETED_WITH_WARNINGS,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    }
)


def delete_jobs(db: Session, job_ids: list[UUID]) -> int:
    if not job_ids:
        return 0
    document_ids = list(db.scalars(select(Job.document_id).where(Job.id.in_(job_ids))))
    db.execute(update(AuditEntry).where(AuditEntry.job_id.in_(job_ids)).values(job_id=None))
    db.execute(delete(ExtractionResult).where(ExtractionResult.job_id.in_(job_ids)))
    db.execute(delete(JobPhaseEntry).where(JobPhaseEntry.job_id.in_(job_ids)))
    db.execute(delete(QueueOutbox).where(QueueOutbox.job_id.in_(job_ids)))
    db.execute(delete(Job).where(Job.id.in_(job_ids)))
    if document_ids:
        remaining_document_ids = select(Job.document_id).where(Job.document_id.in_(document_ids))
        db.execute(
            delete(Document).where(
                Document.id.in_(document_ids),
                Document.id.not_in(remaining_document_ids),
            )
        )
    return len(document_ids)


def purge_expired_logs(db: Session, *, retention_days: int = 20) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    job_ids = list(
        db.scalars(
            select(Job.id).where(
                Job.status.in_(TERMINAL_STATUSES),
                Job.finished_at.is_not(None),
                Job.finished_at < cutoff,
            )
        )
    )
    deleted = delete_jobs(db, job_ids)
    db.commit()
    return deleted
