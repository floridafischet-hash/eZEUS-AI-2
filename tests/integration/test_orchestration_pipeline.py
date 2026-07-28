from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from connectors.base.interface import ConnectorDocument
from core.db.base import Base
from core.models.audit import AuditEntry
from core.models.document import Document
from core.models.enums import JobPriority, JobStatus
from core.models.extraction import ExtractionResult
from core.models.job import Job
from core.models.ocr_artifact import OCRArtifact
from core.models.template import Template
from core.orchestration.orchestrator import Orchestrator
from plugins.ocr.adapter import OCRAdapter
from plugins.ocr.interfaces import OCRProvider
from plugins.ocr.models import BoundingBox, OCRDocument, OCRPage, OCRWord


class FakeOCR(OCRProvider):
    id = "fake"

    def recognize(self, document_path: Path) -> OCRDocument:
        assert document_path.name == "invoice.png"
        assert document_path.parent.name.startswith("ezeus-")
        words = (
            OCRWord("Rechnungsnummer: R-4711", 0.99, BoundingBox(1, 1, 20, 2)),
            OCRWord("Gesamtbetrag: 900,00 EUR", 0.98, BoundingBox(1, 2, 20, 3)),
            OCRWord("Gesamtbetrag: 1.234,56 EUR", 0.98, BoundingBox(1, 3, 20, 4)),
        )
        return OCRDocument(document_path, self.id, (OCRPage(1, words),))


class FailingOCR(OCRProvider):
    id = "must-not-run"

    def recognize(self, document_path: Path) -> OCRDocument:
        raise AssertionError("OCR must not run when Paperless content is available")


class FakePaperless:
    def __init__(self) -> None:
        self.content: str | None = None
        self.title = "Imported invoice"
        self.fields: dict[str, object] = {"99": "manual"}

    async def get_document(self, external_document_id: str) -> ConnectorDocument:
        return ConnectorDocument(
            external_id=external_document_id,
            title=self.title,
            filename="../../invoice.png",
            mime_type="image/png",
            document_type_id="7",
            content=self.content,
            custom_fields=dict(self.fields),
        )

    async def download_original(self, external_document_id: str) -> bytes:
        return b"image"

    async def list_custom_fields(self) -> list[object]:
        return []

    async def write_content(self, external_document_id: str, content: str) -> bool:
        if self.content:
            return False
        self.content = content
        return True

    async def write_title(self, external_document_id: str, title: str) -> bool:
        if self.title == title:
            return False
        self.title = title
        return True

    async def write_empty_fields(
        self, external_document_id: str, values: dict[str, object]
    ) -> dict[str, object]:
        changed = {
            field_id: value
            for field_id, value in values.items()
            if self.fields.get(field_id) in (None, "", [])
        }
        self.fields.update(changed)
        return changed


@pytest.mark.asyncio
async def test_document_pipeline_persists_results_and_audit(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'pipeline.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        document = Document(connector="paperless", external_document_id="128")
        template = Template(
            name="Invoice",
            document_type_external_id="7",
            is_default=True,
            config={
                "fields": {
                    "invoice_number": {
                        "target_field_id": 14,
                        "providers": [
                            {
                                "type": "regex",
                                "patterns": [r"Rechnungsnummer:\s*([A-Z0-9-]+)"],
                            }
                        ],
                        "validators": [{"type": "required_pattern", "pattern": r"^[A-Z0-9-]+$"}],
                    },
                    "total": {
                        "target_field_id": 15,
                        "selection_strategy": "highest",
                        "providers": [
                            {
                                "type": "regex",
                                "patterns": [r"Gesamtbetrag:\s*([\d.,]+\s*EUR)"],
                            }
                        ],
                        "validators": [{"type": "monetary_amount", "currency": "EUR"}],
                    },
                }
            },
        )
        db.add_all([document, template])
        db.flush()
        job = Job(document_id=document.id, status=JobStatus.QUEUED, priority=JobPriority.NORMAL)
        db.add(job)
        db.commit()

        connector = FakePaperless()
        orchestrator = Orchestrator(db)
        orchestrator.connector = connector
        orchestrator.ocr = OCRAdapter(FakeOCR())
        await orchestrator.process(job.id)

        db.refresh(job)
        assert job.status == JobStatus.COMPLETED
        assert connector.fields["14"] == "R-4711"
        assert connector.fields["15"] == "1234.56"
        assert connector.fields["99"] == "manual"
        assert connector.title == "R-4711"
        results = db.scalars(select(ExtractionResult)).all()
        assert len(results) == 3
        total_results = [result for result in results if result.field_key == "total"]
        assert [result.normalized_value for result in total_results] == [
            "900.00",
            "1234.56",
        ]
        assert [result.accepted for result in total_results] == [False, True]
        assert total_results[0].reason == "Lower validated total candidate"
        assert len(db.scalars(select(AuditEntry)).all()) == 4
        artifact = db.scalar(select(OCRArtifact))
        assert artifact is not None
        assert artifact.raw_text == connector.content
        assert artifact.cleaned_text is None
        assert artifact.cleanup_accepted is False


@pytest.mark.asyncio
async def test_pipeline_uses_existing_paperless_content_without_ocr(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'existing-content.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        document = Document(connector="paperless", external_document_id="129")
        template = Template(
            name="Invoice keywords",
            document_type_external_id="7",
            is_default=True,
            config={
                "fields": {
                    "invoice_number": {
                        "target_field_id": 14,
                        "providers": [
                            {
                                "type": "regex",
                                "patterns": [r"Rechnung-Nr\.\s*([A-Z0-9-]+)"],
                            }
                        ],
                        "validators": [{"type": "not_empty"}],
                    }
                }
            },
        )
        db.add_all([document, template])
        db.flush()
        job = Job(document_id=document.id, status=JobStatus.QUEUED, priority=JobPriority.NORMAL)
        db.add(job)
        db.commit()

        connector = FakePaperless()
        connector.content = "Rechnung-Nr. R-5007"
        orchestrator = Orchestrator(db)
        orchestrator.connector = connector
        orchestrator.ocr = OCRAdapter(FailingOCR())
        await orchestrator.process(job.id)

        db.refresh(job)
        assert job.status == JobStatus.COMPLETED
        assert connector.fields["14"] == "R-5007"
