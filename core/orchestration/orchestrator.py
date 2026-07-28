from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from uuid import UUID

from sqlalchemy.orm import Session

from connectors.paperless.connector import PaperlessConnector
from core.models.audit import AuditEntry
from core.models.enums import JobPhase, JobStatus, PhaseStatus
from core.models.extraction import ExtractionResult
from core.models.job import Job
from core.models.job_phase import JobPhaseEntry
from core.templates.service import TemplateService
from core.validation.engine import ValidationEngine
from plugins.base.interfaces import ExtractionCandidate
from plugins.extraction.keyword import KeywordExtractionProvider
from plugins.extraction.regex import RegexExtractionProvider
from plugins.llm.ollama import OllamaExtractionProvider
from plugins.ocr.factory import create_ocr_adapter

PROVIDERS = {
    "regex": RegexExtractionProvider,
    "keyword": KeywordExtractionProvider,
    "ollama": OllamaExtractionProvider,
}


class Orchestrator:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.connector = PaperlessConnector()
        self.ocr = create_ocr_adapter()
        self.templates = TemplateService(db)
        self.validator = ValidationEngine()

    def _start_phase(self, job: Job, phase: JobPhase) -> JobPhaseEntry:
        job.phase = phase
        entry = JobPhaseEntry(
            job_id=job.id,
            phase=phase,
            status=PhaseStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        self.db.add(entry)
        self.db.commit()
        return entry

    def _finish_phase(
        self,
        entry: JobPhaseEntry,
        error: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        entry.status = PhaseStatus.FAILED if error else PhaseStatus.COMPLETED
        entry.finished_at = datetime.now(UTC)
        entry.error = error
        entry.metadata_json = metadata or {}
        self.db.commit()

    async def process(self, job_id: UUID) -> None:
        job = self.db.get(Job, job_id)
        if job is None:
            raise ValueError(f"Unknown job: {job_id}")
        job.status = JobStatus.RUNNING
        job.started_at = job.started_at or datetime.now(UTC)
        job.error_type = None
        job.error_message = None
        self.db.commit()

        active_phase: JobPhaseEntry | None = None
        try:
            active_phase = self._start_phase(job, JobPhase.LOAD_DOCUMENT)
            remote = await self.connector.get_document(job.document.external_document_id)
            document = job.document
            document.filename = remote.filename
            document.mime_type = remote.mime_type
            document.document_type_external_id = remote.document_type_id
            self._finish_phase(active_phase)

            active_phase = self._start_phase(job, JobPhase.DOWNLOAD_DOCUMENT)
            with TemporaryDirectory(prefix="ezeus-") as temp_dir:
                content = await self.connector.download_original(document.external_document_id)
                remote_filename = (document.filename or "").replace("\\", "/")
                safe_filename = Path(remote_filename).name
                if safe_filename in {"", ".", ".."}:
                    safe_filename = "document.bin"
                original = Path(temp_dir) / safe_filename
                original.write_bytes(content)
                self._finish_phase(active_phase, metadata={"bytes": len(content)})

                active_phase = self._start_phase(job, JobPhase.RUN_OCR)
                started = monotonic()
                ocr_result = self.ocr.recognize(original)
                runtime_ms = int((monotonic() - started) * 1000)
                document.page_count = len(ocr_result.pages)
                self._finish_phase(
                    active_phase,
                    metadata={"provider": ocr_result.provider, "runtime_ms": runtime_ms},
                )

                active_phase = self._start_phase(job, JobPhase.WRITE_OCR)
                wrote_content = await self.connector.write_content(
                    document.external_document_id, ocr_result.text
                )
                if wrote_content:
                    self._audit(job, "WRITE_CONTENT", "content", None, "[OCR content]")
                self._finish_phase(active_phase)

                active_phase = self._start_phase(job, JobPhase.SELECT_TEMPLATE)
                selected = self.templates.select_for_document_type(
                    document.document_type_external_id
                )
                if selected is None:
                    self._finish_phase(active_phase, metadata={"selected": False})
                    job.status = JobStatus.COMPLETED_WITH_WARNINGS
                    job.finished_at = datetime.now(UTC)
                    self.db.commit()
                    return
                template, config = selected
                job.selected_template_id = template.id
                job.selected_template_version = template.version
                self._finish_phase(active_phase, metadata={"template_id": str(template.id)})

                active_phase = self._start_phase(job, JobPhase.EXTRACT_FIELDS)
                candidates_by_field: dict[
                    str, list[tuple[ExtractionCandidate, ExtractionResult]]
                ] = {}
                for field_key, field in config.fields.items():
                    persisted: list[tuple[ExtractionCandidate, ExtractionResult]] = []
                    for provider_config in field.providers:
                        provider_data = provider_config.model_dump(exclude={"type"})
                        for candidate in await PROVIDERS[provider_config.type]().extract(
                            ocr_result.text, provider_data
                        ):
                            result = ExtractionResult(
                                job_id=job.id,
                                field_key=field_key,
                                target_field_id=str(field.target_field_id),
                                provider=candidate.provider,
                                raw_value=candidate.value,
                                normalized_value=None,
                                confidence=candidate.confidence,
                                accepted=False,
                                validation_status="PENDING",
                                metadata_json=candidate.metadata,
                            )
                            self.db.add(result)
                            persisted.append((candidate, result))
                    candidates_by_field[field_key] = persisted
                self.db.commit()
                self._finish_phase(active_phase)

                active_phase = self._start_phase(job, JobPhase.VALIDATE_RESULTS)
                extracted_values: dict[str, object] = {}
                for field_key, field in config.fields.items():
                    valid: list[tuple[float, object, ExtractionResult]] = []
                    validators = [item.model_dump() for item in field.validators]
                    for candidate, result in candidates_by_field[field_key]:
                        accepted, normalized, reason = self.validator.validate(
                            candidate, validators
                        )
                        result.normalized_value = normalized
                        result.validation_status = "VALID" if accepted else "INVALID"
                        result.reason = reason
                        if accepted and candidate.confidence >= field.minimum_confidence:
                            valid.append((candidate.confidence, normalized, result))
                    distinct = {str(item[1]) for item in valid}
                    if valid and len(distinct) == 1:
                        winner = max(valid, key=lambda item: item[0])
                        winner[2].accepted = True
                        extracted_values[str(field.target_field_id)] = winner[1]
                    elif len(distinct) > 1:
                        for _, _, result in valid:
                            result.reason = "Conflicting validated candidates"
                self.db.commit()
                self._finish_phase(active_phase)

                active_phase = self._start_phase(job, JobPhase.RELOAD_METADATA)
                before_write = await self.connector.get_document(document.external_document_id)
                self._finish_phase(active_phase)

                active_phase = self._start_phase(job, JobPhase.WRITE_METADATA)
                changed = await self.connector.write_empty_fields(
                    document.external_document_id, extracted_values
                )
                for field_id, value in changed.items():
                    self._audit(
                        job,
                        "WRITE_CUSTOM_FIELD",
                        field_id,
                        before_write.custom_fields.get(field_id),
                        value,
                    )
                self._finish_phase(active_phase, metadata={"fields_written": len(changed)})

            active_phase = self._start_phase(job, JobPhase.CLEANUP)
            self._finish_phase(active_phase)
            active_phase = self._start_phase(job, JobPhase.COMPLETE)
            job.status = JobStatus.COMPLETED
            job.finished_at = datetime.now(UTC)
            self._finish_phase(active_phase)
        except Exception as exc:
            if active_phase and active_phase.status == PhaseStatus.RUNNING:
                self._finish_phase(active_phase, error=type(exc).__name__)
            job.status = JobStatus.FAILED
            job.error_type = type(exc).__name__
            job.error_message = str(exc)[:4000]
            job.finished_at = datetime.now(UTC)
            self.db.commit()
            raise

    def _audit(
        self, job: Job, action: str, field: str, old_value: object, new_value: object
    ) -> None:
        self.db.add(
            AuditEntry(
                job_id=job.id,
                actor="system",
                action=action,
                entity_type="document",
                entity_id=job.document.external_document_id,
                target_system="paperless",
                field=field,
                old_value=old_value,
                new_value=new_value,
                status="SUCCESS",
            )
        )
        self.db.commit()
