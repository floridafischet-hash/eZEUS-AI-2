from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from connectors.base.interface import (
    ConnectorCorrespondent,
    ConnectorCustomField,
    ConnectorDocument,
    DocumentConnector,
)
from core.db.base import Base
from core.models.document import Document
from core.models.enums import JobStatus
from core.models.job import Job
from core.orchestration.orchestrator import Orchestrator


class FailingMetadataConnector(DocumentConnector):
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def close(self) -> None:
        return None

    async def health_check(self) -> bool:
        return True

    async def get_document(self, external_document_id: str) -> ConnectorDocument:
        return ConnectorDocument(
            external_id=external_document_id,
            filename="rechnung.pdf",
            mime_type="application/pdf",
            content=("Alpha Service Nord\nRechnungsnummer: RE-123\nGesamtbetrag: 123,45 EUR"),
            custom_fields={"10": None, "11": None},
        )

    async def list_custom_fields(self) -> list[ConnectorCustomField]:
        return [
            ConnectorCustomField("10", "Rechnungsnummer", "string"),
            ConnectorCustomField("11", "Rechnungsbetrag", "monetary"),
        ]

    async def list_correspondents(self) -> list[ConnectorCorrespondent]:
        return [
            ConnectorCorrespondent("7", "Alpha Service", "Alpha Service Nord", 3, True),
            ConnectorCorrespondent("99", "(noch nicht angelegt)", "", 0, True),
        ]

    async def write_correspondent_if_empty(
        self, document: ConnectorDocument, correspondent_id: str
    ) -> bool:
        self.calls.append(f"correspondent:{correspondent_id}")
        if correspondent_id == "7":
            raise RuntimeError("matched correspondent rejected")
        return True

    async def write_title(self, document: ConnectorDocument, title: str) -> bool:
        self.calls.append("title")
        raise RuntimeError("title rejected")

    async def write_empty_fields(
        self, document: ConnectorDocument, values: dict[str, object]
    ) -> dict[str, object]:
        field_id, value = next(iter(values.items()))
        self.calls.append(f"field:{field_id}")
        if field_id == "10":
            raise RuntimeError("first field rejected")
        return {field_id: value}


@pytest.mark.asyncio
async def test_metadata_writes_keep_order_and_continue_after_failures() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        document = Document(
            connector="paperless:test",
            external_document_id=str(uuid4()),
            filename="rechnung.pdf",
        )
        job = Job(document=document, status=JobStatus.QUEUED)
        db.add(job)
        db.commit()

        connector = FailingMetadataConnector()
        orchestrator = Orchestrator(db)
        orchestrator.connector = connector

        await orchestrator.process(job.id)

        assert connector.calls == [
            "correspondent:7",
            "correspondent:99",
            "title",
            "field:10",
            "field:11",
        ]
        db.refresh(job)
        assert job.status == JobStatus.COMPLETED
