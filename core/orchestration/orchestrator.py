from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from connectors.base.interface import DocumentConnector
from core.correspondents.matcher import match_correspondent
from core.field_config.service import FieldConfigurationService, RuntimeFieldConfiguration
from core.models.audit import AuditEntry
from core.models.enums import JobPhase, JobStatus, PhaseStatus
from core.models.extraction import ExtractionResult
from core.models.job import Job
from core.models.job_phase import JobPhaseEntry
from core.paperless.service import (
    connector_for_document,
    get_enabled_instance,
    instance_slug_from_connector,
)
from core.security.documents import validate_paperless_document
from core.security.redaction import redact_sensitive_text
from core.templates.automatic import config_from_custom_fields
from core.templates.schema import TemplateConfig
from core.templates.service import TemplateService
from core.validation.engine import ValidationEngine
from plugins.base.interfaces import ExtractionCandidate
from plugins.extraction.keyword import KeywordExtractionProvider
from plugins.extraction.regex import RegexExtractionProvider
from plugins.llm.ollama import OllamaExtractionProvider

PROVIDERS = {
    "regex": RegexExtractionProvider,
    "keyword": KeywordExtractionProvider,
    "ollama": OllamaExtractionProvider,
}


class Orchestrator:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.connector: DocumentConnector | None = None
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
        connector = self.connector or connector_for_document(self.db, job.document.connector)
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        job.error_type = None
        job.error_message = None
        self.db.commit()

        active_phase: JobPhaseEntry | None = None
        try:
            active_phase = self._start_phase(job, JobPhase.LOAD_DOCUMENT)
            remote = await connector.get_document(job.document.external_document_id)
            validate_paperless_document(mime_type=remote.mime_type, content=remote.content)
            document = job.document
            document.filename = remote.filename
            document.mime_type = remote.mime_type
            document.document_type_external_id = remote.document_type_id
            self._finish_phase(
                active_phase,
                metadata={
                    "filename": remote.filename,
                    "mime_type": remote.mime_type,
                    "document_type_id": remote.document_type_id,
                },
            )

            active_phase = self._start_phase(job, JobPhase.READ_DOCUMENT_TEXT)
            paperless_text = (remote.content or "").strip()
            if paperless_text:
                extraction_text = paperless_text
                extraction_source = "paperless_content"
                self._finish_phase(
                    active_phase,
                    metadata={
                        "source": "paperless_content",
                        "characters": len(paperless_text),
                    },
                )
            else:
                extraction_text = ""
                extraction_source = "none"
                self._finish_phase(
                    active_phase,
                    metadata={"source": "none", "reason": "Kein Textinhalt in Paperless vorhanden"},
                )

            active_phase = self._start_phase(job, JobPhase.SELECT_TEMPLATE)
            paperless_fields = await connector.list_custom_fields()
            runtime_fields: RuntimeFieldConfiguration | None = None
            config: TemplateConfig | None
            instance_slug = instance_slug_from_connector(document.connector)
            instance = (
                get_enabled_instance(self.db, instance_slug) if instance_slug is not None else None
            )
            if instance is not None:
                runtime_fields = FieldConfigurationService(self.db).runtime_config(
                    instance, paperless_fields
                )
                config = runtime_fields.template
                self._finish_phase(
                    active_phase,
                    metadata={
                        "selected": True,
                        "source": "instance_field_configuration",
                        "instance": instance.slug,
                        "field_ids": [
                            field.target_field_id
                            for field in config.fields.values()
                            if field.target_field_id is not None
                        ],
                    },
                )
            else:
                config = config_from_custom_fields(paperless_fields)
            if instance is None and config is not None:
                self._finish_phase(
                    active_phase,
                    metadata={
                        "selected": True,
                        "source": "paperless_custom_fields",
                        "field_ids": [
                            field.target_field_id
                            for field in config.fields.values()
                            if field.target_field_id is not None
                        ],
                    },
                )
            elif instance is None:
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
            if config is None:
                raise RuntimeError("Field configuration could not be resolved")

            active_phase = self._start_phase(job, JobPhase.EXTRACT_FIELDS)
            candidates_by_field: dict[str, list[tuple[ExtractionCandidate, ExtractionResult]]] = {}
            for field_key, field in config.fields.items():
                persisted: list[tuple[ExtractionCandidate, ExtractionResult]] = []
                for provider_config in field.providers:
                    provider_data = provider_config.model_dump(exclude={"type"})
                    for candidate in await PROVIDERS[provider_config.type]().extract(
                        extraction_text, provider_data
                    ):
                        result = ExtractionResult(
                            job_id=job.id,
                            field_key=field_key,
                            target_field_id=(
                                str(field.target_field_id)
                                if field.target_field_id is not None
                                else field_key
                            ),
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
            self._finish_phase(
                active_phase,
                metadata={
                    "fields_configured": len(config.fields),
                    "candidates_found": sum(len(items) for items in candidates_by_field.values()),
                    "text_source": extraction_source,
                    "text_characters": len(extraction_text),
                },
            )

            active_phase = self._start_phase(job, JobPhase.VALIDATE_RESULTS)
            extracted_values: dict[str, object] = {}
            extracted_by_key: dict[str, object] = {}
            for field_key, field in config.fields.items():
                valid: list[tuple[float, object, ExtractionResult]] = []
                validators = [item.model_dump() for item in field.validators]
                for candidate, result in candidates_by_field[field_key]:
                    accepted, normalized, reason = self.validator.validate(candidate, validators)
                    result.normalized_value = normalized
                    result.validation_status = "VALID" if accepted else "INVALID"
                    result.reason = reason
                    if accepted and candidate.confidence >= field.minimum_confidence:
                        valid.append((candidate.confidence, normalized, result))
                distinct = {str(item[1]) for item in valid}
                if valid and field.selection_strategy == "first":
                    winner = valid[0]
                    winner[2].accepted = True
                    output_value = field.value_mapping.get(str(winner[1]), winner[1])
                    extracted_by_key[field_key] = output_value
                    if field.target_field_id is not None:
                        extracted_values[str(field.target_field_id)] = output_value
                    for _, _, result in valid[1:]:
                        result.reason = "Lower-priority validated candidate"
                elif valid and field.selection_strategy == "highest":
                    winner = max(
                        valid,
                        key=lambda item: (
                            Decimal(str(item[1])),
                            item[0],
                        ),
                    )
                    winner[2].accepted = True
                    output_value = field.value_mapping.get(str(winner[1]), winner[1])
                    extracted_by_key[field_key] = output_value
                    if field.target_field_id is not None:
                        extracted_values[str(field.target_field_id)] = output_value
                    for _, _, result in valid:
                        if result is not winner[2]:
                            result.reason = "Lower validated total candidate"
                elif valid and len(distinct) == 1:
                    winner = max(valid, key=lambda item: item[0])
                    winner[2].accepted = True
                    output_value = field.value_mapping.get(str(winner[1]), winner[1])
                    extracted_by_key[field_key] = output_value
                    if field.target_field_id is not None:
                        extracted_values[str(field.target_field_id)] = output_value
                elif len(distinct) > 1:
                    for _, _, result in valid:
                        result.reason = "Conflicting validated candidates"
            self.db.commit()
            missing_fields = [
                field_key
                for field_key, field in config.fields.items()
                if field.required
                and (field_key not in extracted_by_key or field.target_field_id is None)
            ]
            self._finish_phase(
                active_phase,
                metadata={
                    "fields_accepted": len(extracted_values),
                    "missing_fields": missing_fields,
                },
            )

            active_phase = self._start_phase(job, JobPhase.RELOAD_METADATA)
            before_write = await connector.get_document(document.external_document_id)
            self._finish_phase(
                active_phase,
                metadata={"metadata_reloaded": True},
            )

            active_phase = self._start_phase(job, JobPhase.WRITE_METADATA)
            changed = await connector.write_empty_fields(
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
            title_written = False
            invoice_number = extracted_by_key.get("invoice_number")
            if invoice_number is not None:
                title_written = await connector.write_title(
                    document.external_document_id,
                    str(invoice_number),
                )
                if title_written:
                    self._audit(
                        job,
                        "WRITE_TITLE",
                        "title",
                        before_write.title,
                        str(invoice_number),
                    )
            correspondent_written = False
            correspondent_match = None
            correspondent_enabled = (
                runtime_fields.correspondent_enabled if runtime_fields is not None else True
            )
            if correspondent_enabled and before_write.correspondent_id is None:
                correspondent_match = match_correspondent(
                    extraction_text,
                    await connector.list_correspondents(),
                )
                if correspondent_match is not None:
                    correspondent_written = await connector.write_correspondent_if_empty(
                        document.external_document_id,
                        correspondent_match.correspondent_id,
                    )
                    if correspondent_written:
                        self._audit(
                            job,
                            "WRITE_CORRESPONDENT",
                            "correspondent",
                            None,
                            correspondent_match.correspondent_id,
                        )
            if (
                runtime_fields is not None
                and runtime_fields.correspondent_required
                and before_write.correspondent_id is None
                and correspondent_match is None
            ):
                missing_fields.append("correspondent")
            all_fields_extracted = not missing_fields
            self._finish_phase(
                active_phase,
                metadata={
                    "fields_written": len(changed),
                    "title_written": title_written,
                    "correspondent_written": correspondent_written,
                    "correspondent_match": (
                        {
                            "id": correspondent_match.correspondent_id,
                            "name": correspondent_match.name,
                            "score": round(correspondent_match.score, 4),
                            "source": correspondent_match.source,
                        }
                        if correspondent_match is not None
                        else None
                    ),
                },
            )

            active_phase = self._start_phase(job, JobPhase.CLEANUP)
            self._finish_phase(active_phase)
            active_phase = self._start_phase(job, JobPhase.COMPLETE)
            job.status = (
                JobStatus.COMPLETED if all_fields_extracted else JobStatus.COMPLETED_WITH_WARNINGS
            )
            job.finished_at = datetime.now(UTC)
            self._finish_phase(active_phase)
        except Exception as exc:
            if active_phase and active_phase.status == PhaseStatus.RUNNING:
                self._finish_phase(active_phase, error=type(exc).__name__)
            job.status = JobStatus.FAILED
            job.error_type = type(exc).__name__
            job.error_message = redact_sensitive_text(exc)
            job.finished_at = datetime.now(UTC)
            self.db.commit()
            raise

    def _audit(
        self, job: Job, action: str, field: str, old_value: object, new_value: object
    ) -> None:
        slug = instance_slug_from_connector(job.document.connector)
        instance = get_enabled_instance(self.db, slug) if slug is not None else None
        self.db.add(
            AuditEntry(
                job_id=job.id,
                instance_id=instance.id if instance is not None else None,
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
