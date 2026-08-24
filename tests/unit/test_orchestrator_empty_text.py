from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from connectors.base.errors import ConnectorError
from connectors.base.interface import ConnectorDocument, DocumentConnector
from core.db.base import Base
from core.models.document import Document
from core.models.enums import JobPhase, JobStatus, PhaseStatus
from core.models.job import Job
from core.models.job_phase import JobPhaseEntry
from core.orchestration.exceptions import RetryableEmptyTextError
from core.orchestration.orchestrator import Orchestrator


class EmptyTextConnector(DocumentConnector):
    closed = False

    async def close(self) -> None:
        self.closed = True

    async def health_check(self) -> bool:
        return True

    async def get_document(self, external_document_id: str) -> ConnectorDocument:
        return ConnectorDocument(
            external_id=external_document_id,
            filename="pending-ocr.pdf",
            mime_type="application/pdf",
            content="   ",
        )

    async def write_title(self, external_document_id: str, title: str) -> bool:
        raise AssertionError("write must not be reached")

    async def write_correspondent_if_empty(
        self, external_document_id: str, correspondent_id: str
    ) -> bool:
        raise AssertionError("write must not be reached")

    async def write_empty_fields(
        self, external_document_id: str, values: dict[str, object]
    ) -> dict[str, object]:
        raise AssertionError("write must not be reached")


@pytest.mark.asyncio
async def test_empty_paperless_text_raises_retryable_error() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        document = Document(
            connector="paperless:test",
            external_document_id=str(uuid4()),
            filename="pending-ocr.pdf",
        )
        job = Job(document=document, status=JobStatus.QUEUED)
        db.add(job)
        db.commit()

        orchestrator = Orchestrator(db)
        connector = EmptyTextConnector()
        orchestrator.connector = connector
        with pytest.raises(RetryableEmptyTextError, match="OCR may still be pending"):
            await orchestrator.process(job.id)

        db.refresh(job)
        assert job.status == JobStatus.FAILED
        assert job.error_type == "RetryableEmptyTextError"
        read_phase = db.scalar(
            select(JobPhaseEntry).where(
                JobPhaseEntry.job_id == job.id,
                JobPhaseEntry.phase == JobPhase.READ_DOCUMENT_TEXT,
            )
        )
        assert read_phase is not None
        assert read_phase.status == PhaseStatus.FAILED
        assert connector.closed is True


def test_empty_text_error_uses_worker_retry_contract() -> None:
    assert issubclass(RetryableEmptyTextError, ConnectorError)
    assert RetryableEmptyTextError.retryable is True
