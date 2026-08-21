from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.events.document_imported import DocumentImportedEvent
from core.models.document import Document
from core.models.enums import JobPhase, JobPriority, JobStatus, PhaseStatus
from core.models.job import Job
from core.models.job_phase import JobPhaseEntry
from core.models.queue_outbox import QueueOutbox
from core.queue.outbox import add_job_to_outbox


class JobService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_from_event(
        self, event: DocumentImportedEvent, priority: JobPriority = JobPriority.NORMAL
    ) -> tuple[Job, bool, QueueOutbox | None]:
        if event.source_event_id:
            existing = self.db.scalar(
                select(Job).where(Job.source_event_id == event.source_event_id)
            )
            if existing:
                if existing.status == JobStatus.RECEIVED:
                    outbox = add_job_to_outbox(self.db, existing)
                    self.db.commit()
                    self.db.refresh(existing)
                    self.db.refresh(outbox)
                    return existing, True, outbox
                return existing, False, None

        document = self.db.scalar(
            select(Document).where(
                Document.connector == event.connector,
                Document.external_document_id == event.external_document_id,
            )
        )
        if document is None:
            document = Document(
                connector=event.connector,
                external_document_id=event.external_document_id,
            )
            self.db.add(document)
            self.db.flush()

        active_job = self.db.scalar(
            select(Job).where(
                Job.document_id == document.id,
                Job.status.in_(
                    [
                        JobStatus.RECEIVED,
                        JobStatus.QUEUED,
                        JobStatus.RUNNING,
                        JobStatus.RETRY_WAITING,
                    ]
                ),
            )
        )
        if active_job:
            return active_job, False, None

        job = Job(
            document_id=document.id,
            priority=priority,
            status=JobStatus.RECEIVED,
            source_event_id=event.source_event_id,
        )
        self.db.add(job)
        self.db.flush()
        now = datetime.now(UTC)
        self.db.add(
            JobPhaseEntry(
                job_id=job.id,
                phase=JobPhase.RECEIVE_EVENT,
                status=PhaseStatus.COMPLETED,
                started_at=now,
                finished_at=now,
                metadata_json={"connector": event.connector},
            )
        )
        outbox = add_job_to_outbox(self.db, job)
        self.db.commit()
        self.db.refresh(job)
        self.db.refresh(outbox)
        return job, True, outbox
