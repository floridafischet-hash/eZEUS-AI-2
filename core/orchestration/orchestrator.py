import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from connectors.base.interface import ConnectorDocument, DocumentConnector
from core.correspondents.matcher import (
    DEFAULT_CORRESPONDENT_NAME,
    CorrespondentMatch,
    default_correspondent,
    match_correspondent,
)
from core.field_config.service import FieldConfigurationService, RuntimeFieldConfiguration
from core.logging import bind_log_context, describe_exception, log_context
from core.metrics import JOBS_TOTAL, PHASE_DURATION_SECONDS
from core.models.audit import AuditEntry
from core.models.enums import JobPhase, JobStatus, PhaseStatus
from core.models.extraction import ExtractionResult
from core.models.job import Job
from core.models.job_phase import JobPhaseEntry
from core.orchestration.exceptions import RetryableEmptyTextError
from core.paperless.service import (
    connector_for_document,
    get_enabled_instance,
    instance_slug_from_connector,
)
from core.paperless.title_template import render_title
from core.security.documents import validate_paperless_document
from core.security.redaction import redact_sensitive_text
from core.templates.automatic import config_from_custom_fields
from core.templates.schema import TemplateConfig
from core.templates.service import TemplateService
from core.validation.engine import ValidationEngine
from plugins.base.interfaces import ExtractionCandidate
from plugins.extraction.keyword import KeywordExtractionProvider
from plugins.extraction.regex import RegexExtractionProvider
from plugins.llm.metadata import OllamaMetadataProvider
from plugins.llm.ollama import OllamaExtractionProvider

logger = logging.getLogger(__name__)

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

    def _log_extra(self, job: Job, phase: str | None = None) -> dict[str, object]:
        extra: dict[str, object] = {"job_id": str(job.id)}
        slug = instance_slug_from_connector(job.document.connector)
        if slug:
            extra["instance_slug"] = slug
        if phase:
            extra["phase"] = phase
        return extra

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
        bind_log_context(phase=phase.value)
        logger.info(
            "Verarbeitungsschritt gestartet: %s",
            phase.value,
            extra=self._log_extra(job, phase.value),
        )
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
        duration = (entry.finished_at - entry.started_at).total_seconds()
        PHASE_DURATION_SECONDS.labels(phase=entry.phase.value, status=entry.status.value).observe(
            duration
        )
        job = self.db.get(Job, entry.job_id)
        extra = self._log_extra(job, entry.phase.value) if job else {"phase": entry.phase.value}
        if error:
            logger.warning(
                "Verarbeitungsschritt fehlgeschlagen: %s; Ursache=%s",
                entry.phase.value,
                error,
                extra=extra,
            )
        else:
            logger.info("Verarbeitungsschritt abgeschlossen: %s", entry.phase.value, extra=extra)

    def _note_problem(
        self,
        problems: list[dict[str, object]],
        step: str,
        message: str,
        exc: Exception,
        **fields: object,
    ) -> None:
        """Log a failure the job continues past, and keep it for the phase record."""

        description = redact_sensitive_text(describe_exception(exc), limit=500)
        error_type = type(exc).__name__
        logger.warning(
            "%s; Ursache: %s: %s",
            message,
            error_type,
            description,
            exc_info=exc,
            extra={"step": step, "error_type": error_type, **fields},
        )
        problems.append({"step": step, "error_type": error_type, "error": description, **fields})

    async def process(self, job_id: UUID) -> None:
        job = self.db.get(Job, job_id)
        if job is None:
            raise ValueError(f"Unknown job: {job_id}")
        with log_context(
            job_id=str(job.id),
            instance_slug=instance_slug_from_connector(job.document.connector),
            document_id=job.document.external_document_id,
        ):
            await self._process(job)

    async def _process(self, job: Job) -> None:
        connector: DocumentConnector | None = None
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        job.error_type = None
        job.error_message = None
        self.db.commit()
        logger.info("Dokumentenauftrag gestartet", extra=self._log_extra(job))

        active_phase: JobPhaseEntry | None = None
        current_field: str | None = None
        current_provider: str | None = None
        try:
            connector = self.connector or connector_for_document(self.db, job.document.connector)
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
                raise RetryableEmptyTextError(
                    "Paperless document text is empty; OCR may still be pending"
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
                    logger.warning(
                        "Keine Vorlage für Dokumenttyp %s gefunden; "
                        "Auftrag endet ohne Feldverarbeitung",
                        document.document_type_external_id,
                    )
                    slug = instance_slug_from_connector(job.document.connector) or ""
                    JOBS_TOTAL.labels(status=job.status.value, instance_slug=slug).inc()
                    return
                template, config = selected
                job.selected_template_id = template.id
                job.selected_template_version = template.version
                self._finish_phase(active_phase, metadata={"template_id": str(template.id)})
            if config is None:
                raise RuntimeError("Field configuration could not be resolved")

            active_phase = self._start_phase(job, JobPhase.EXTRACT_FIELDS)
            candidates_by_field: dict[str, list[tuple[ExtractionCandidate, ExtractionResult]]] = {}
            fields_outside_document_type: set[str] = set()
            scoped_document_type_name = ""
            document_type_lookup_failed = False
            extraction_problems: list[dict[str, object]] = []
            if (
                runtime_fields is not None
                and runtime_fields.field_document_type_names
                and remote.document_type_id
                and hasattr(connector, "get_document_type_name")
            ):
                try:
                    scoped_document_type_name = (
                        await connector.get_document_type_name(remote.document_type_id) or ""
                    )
                except Exception as exc:  # noqa: BLE001 -- scoped fields fail closed
                    scoped_document_type_name = ""
                    self._note_problem(
                        extraction_problems,
                        "document_type_lookup",
                        "Dokumenttyp konnte nicht geladen werden",
                        exc,
                        document_type_id=remote.document_type_id,
                    )
                if not scoped_document_type_name:
                    document_type_lookup_failed = True
                    logger.warning(
                        "Name des Dokumenttyps %s unbekannt; Felder mit Dokumenttyp-Beschränkung "
                        "werden für dieses Dokument übersprungen",
                        remote.document_type_id,
                    )
            for field_key, field in config.fields.items():
                current_field = field_key
                persisted: list[tuple[ExtractionCandidate, ExtractionResult]] = []
                allowed_document_types = (
                    runtime_fields.field_document_type_names.get(field_key)
                    if runtime_fields is not None
                    else None
                )
                if allowed_document_types and scoped_document_type_name.casefold() not in {
                    name.casefold() for name in allowed_document_types
                }:
                    fields_outside_document_type.add(field_key)
                    candidates_by_field[field_key] = persisted
                    continue
                for provider_config in field.providers:
                    current_provider = provider_config.type
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
            current_field = None
            current_provider = None
            self.db.commit()
            extraction_metadata: dict[str, object] = {
                "fields_configured": len(config.fields),
                "candidates_found": sum(len(items) for items in candidates_by_field.values()),
                "text_source": extraction_source,
                "text_characters": len(extraction_text),
            }
            if fields_outside_document_type:
                extraction_metadata["fields_outside_document_type"] = sorted(
                    fields_outside_document_type
                )
            if document_type_lookup_failed:
                extraction_metadata["document_type_lookup_failed"] = True
            if extraction_problems:
                extraction_metadata["problems"] = extraction_problems
            self._finish_phase(active_phase, metadata=extraction_metadata)

            active_phase = self._start_phase(job, JobPhase.VALIDATE_RESULTS)
            extracted_values: dict[str, object] = {}
            extracted_by_key: dict[str, object] = {}
            for field_key, field in config.fields.items():
                current_field = field_key
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
                elif valid and field.selection_strategy == "pattern_priority_highest":
                    priorities = [
                        int(str(result.metadata_json.get("pattern_index", 2**31)))
                        for _, _, result in valid
                    ]
                    highest_priority = min(priorities)
                    prioritized = [
                        item
                        for item in valid
                        if int(str(item[2].metadata_json.get("pattern_index", 2**31)))
                        == highest_priority
                    ]
                    winner = max(
                        prioritized,
                        key=lambda item: (
                            abs(Decimal(str(item[1]))),
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
                            result.reason = "Lower-priority invoice-total candidate"
                elif valid and field.selection_strategy == "pattern_priority_unique":
                    priorities = [
                        int(str(result.metadata_json.get("pattern_index", 2**31)))
                        for _, _, result in valid
                    ]
                    highest_priority = min(priorities)
                    prioritized = [
                        item
                        for item in valid
                        if int(str(item[2].metadata_json.get("pattern_index", 2**31)))
                        == highest_priority
                    ]
                    prioritized_distinct = {str(item[1]) for item in prioritized}
                    if len(prioritized_distinct) == 1:
                        winner = max(prioritized, key=lambda item: item[0])
                        winner[2].accepted = True
                        output_value = field.value_mapping.get(str(winner[1]), winner[1])
                        extracted_by_key[field_key] = output_value
                        if field.target_field_id is not None:
                            extracted_values[str(field.target_field_id)] = output_value
                        for _, _, result in valid:
                            if result is not winner[2]:
                                result.reason = "Lower-priority validated candidate"
                    else:
                        for _, _, result in prioritized:
                            result.reason = "Conflicting validated candidates at same priority"
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
            current_field = None
            self.db.commit()
            missing_fields = [
                field_key
                for field_key, field in config.fields.items()
                if field.required
                and field_key not in fields_outside_document_type
                and (field_key not in extracted_by_key or field.target_field_id is None)
            ]
            if missing_fields:
                logger.warning(
                    "Pflichtfelder ohne übernehmbaren Wert: %s",
                    ", ".join(
                        f"{field_key} (Kandidaten={len(candidates_by_field[field_key])})"
                        for field_key in missing_fields
                    ),
                )
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
            write_problems: list[dict[str, object]] = []
            correspondent_written = False
            correspondent_match = None
            correspondent_enabled = (
                runtime_fields.correspondent_enabled if runtime_fields is not None else True
            )
            if correspondent_enabled and before_write.correspondent_id is None:
                try:
                    correspondents = await connector.list_correspondents()
                except Exception as exc:  # noqa: BLE001 -- continue with remaining metadata
                    self._note_problem(
                        write_problems,
                        "correspondent_list",
                        "Korrespondentenliste konnte nicht geladen werden; "
                        "Zuordnung läuft ohne Liste weiter",
                        exc,
                    )
                    correspondents = []
                rule_enabled = (
                    runtime_fields.correspondent_rule_enabled
                    if runtime_fields is not None
                    else True
                )
                if rule_enabled:
                    try:
                        correspondent_match = match_correspondent(extraction_text, correspondents)
                    except Exception as exc:  # noqa: BLE001 -- use fallback and continue
                        self._note_problem(
                            write_problems,
                            "correspondent_match",
                            "Korrespondent konnte nicht zugeordnet werden; "
                            "Ersatzverfahren wird geprüft",
                            exc,
                        )
                ai_enabled = (
                    runtime_fields.correspondent_ai_enabled if runtime_fields is not None else False
                )
                if correspondent_match is None and ai_enabled:
                    correspondent_instructions = (
                        runtime_fields.correspondent_instructions
                        if runtime_fields is not None
                        else ""
                    )
                    try:
                        selected_correspondent = (
                            await OllamaMetadataProvider().select_correspondent(
                                extraction_text,
                                correspondents,
                                correspondent_instructions,
                            )
                        )
                    except Exception as exc:
                        self._note_problem(
                            write_problems,
                            "correspondent_ai",
                            "KI-Korrespondentenvorschlag fehlgeschlagen; "
                            "regelbasierter Ersatz wird verwendet",
                            exc,
                        )
                        selected_correspondent = None
                    if selected_correspondent is not None:
                        correspondent_match = CorrespondentMatch(
                            correspondent_id=selected_correspondent.external_id,
                            name=selected_correspondent.name,
                            score=1.0,
                            source="ollama",
                            line_number=-1,
                        )
                if correspondent_match is None:
                    fallback = default_correspondent(correspondents)
                    if fallback is None:
                        try:
                            fallback = await connector.ensure_correspondent(
                                DEFAULT_CORRESPONDENT_NAME,
                                correspondents,
                            )
                        except Exception as exc:  # noqa: BLE001 -- title and fields must still run
                            self._note_problem(
                                write_problems,
                                "correspondent_fallback",
                                "Ersatz-Korrespondent konnte nicht angelegt werden; "
                                "Feld bleibt unverändert",
                                exc,
                            )
                    if fallback is not None:
                        correspondent_match = CorrespondentMatch(
                            correspondent_id=fallback.external_id,
                            name=fallback.name,
                            score=1.0,
                            source="default_fallback",
                            line_number=-1,
                        )
                if correspondent_match is not None:
                    try:
                        correspondent_written = await connector.write_correspondent_if_empty(
                            before_write,
                            correspondent_match.correspondent_id,
                        )
                    except Exception as exc:  # noqa: BLE001 -- title and fields must still run
                        self._note_problem(
                            write_problems,
                            "correspondent_write",
                            "Korrespondent konnte nicht geschrieben werden; "
                            "übrige Metadaten werden fortgesetzt",
                            exc,
                            correspondent_id=correspondent_match.correspondent_id,
                        )
                        if correspondent_match.source != "default_fallback":
                            try:
                                fallback = default_correspondent(correspondents)
                                if fallback is None:
                                    fallback = await connector.ensure_correspondent(
                                        DEFAULT_CORRESPONDENT_NAME,
                                        correspondents,
                                    )
                                correspondent_written = (
                                    await connector.write_correspondent_if_empty(
                                        before_write,
                                        fallback.external_id,
                                    )
                                )
                                correspondent_match = CorrespondentMatch(
                                    correspondent_id=fallback.external_id,
                                    name=fallback.name,
                                    score=1.0,
                                    source="default_fallback",
                                    line_number=-1,
                                )
                            except Exception as fallback_exc:  # noqa: BLE001
                                self._note_problem(
                                    write_problems,
                                    "correspondent_fallback",
                                    "Ersatz-Korrespondent konnte nicht geschrieben werden; "
                                    "Feld bleibt unverändert",
                                    fallback_exc,
                                )
                    if correspondent_written:
                        self._audit(
                            job,
                            "WRITE_CORRESPONDENT",
                            "correspondent",
                            None,
                            correspondent_match.correspondent_id,
                        )
                        before_write.correspondent_id = correspondent_match.correspondent_id

            title_written = False
            invoice_number = extracted_by_key.get("invoice_number")
            title_values = dict(extracted_by_key)
            if runtime_fields is not None:
                for field_key, field in runtime_fields.template.fields.items():
                    target_id = field.target_field_id
                    if field_key not in title_values and target_id is not None:
                        existing_value = before_write.custom_fields.get(str(target_id))
                        if existing_value is not None:
                            title_values[field_key] = existing_value
                    title_values.setdefault(field_key, "")
                for profile_key, field_key in runtime_fields.profile_field_keys.items():
                    title_values[profile_key] = title_values.get(field_key, "")
            title_template = (instance.title_template or "").strip() if instance is not None else ""
            title_enabled = runtime_fields.title_enabled if runtime_fields is not None else True
            new_title: str | None = None
            if title_enabled and runtime_fields is not None and runtime_fields.title_ai_enabled:
                try:
                    new_title = await OllamaMetadataProvider().suggest_title(
                        extraction_text,
                        runtime_fields.title_instructions,
                    )
                except Exception as exc:
                    self._note_problem(
                        write_problems,
                        "title_ai",
                        "KI-Titelerzeugung fehlgeschlagen; Titelregel wird als Ersatz geprüft",
                        exc,
                    )
            title_rule_enabled = (
                runtime_fields.title_rule_enabled if runtime_fields is not None else True
            )
            if title_enabled and title_rule_enabled and not new_title and title_template:
                context = await self._build_title_context(connector, before_write, title_values)
                try:
                    new_title = render_title(title_template, context)
                except Exception as exc:  # noqa: BLE001 -- custom fields must still run
                    self._note_problem(
                        write_problems,
                        "title_template",
                        "Titelvorlage ist ungültig; Rechnungsnummer wird ersatzweise verwendet",
                        exc,
                        placeholder=getattr(exc, "name", None),
                    )
                    new_title = str(invoice_number) if invoice_number is not None else None
            elif (
                title_enabled
                and title_rule_enabled
                and not new_title
                and invoice_number is not None
            ):
                new_title = str(invoice_number)
            if new_title:
                try:
                    title_written = await connector.write_title(before_write, new_title)
                except Exception as exc:  # noqa: BLE001 -- custom fields must still run
                    self._note_problem(
                        write_problems,
                        "title_write",
                        "Dokumenttitel konnte nicht geschrieben werden; "
                        "benutzerdefinierte Felder laufen weiter",
                        exc,
                    )
                if title_written:
                    self._audit(
                        job,
                        "WRITE_TITLE",
                        "title",
                        before_write.title,
                        new_title,
                    )

            changed: dict[str, object] = {}
            for field_id, value in extracted_values.items():
                try:
                    field_changed = await connector.write_empty_fields(
                        before_write,
                        {field_id: value},
                    )
                except Exception as exc:  # noqa: BLE001 -- try every remaining field
                    self._note_problem(
                        write_problems,
                        "custom_field_write",
                        f"Benutzerdefiniertes Feld {field_id} konnte nicht geschrieben werden; "
                        "weitere Felder laufen weiter",
                        exc,
                        field_id=field_id,
                    )
                    continue
                for written_field_id, written_value in field_changed.items():
                    old_value = before_write.custom_fields.get(written_field_id)
                    changed[written_field_id] = written_value
                    self._audit(
                        job,
                        "WRITE_CUSTOM_FIELD",
                        written_field_id,
                        old_value,
                        written_value,
                    )
                    before_write.custom_fields[written_field_id] = written_value
            if (
                runtime_fields is not None
                and runtime_fields.correspondent_required
                and before_write.correspondent_id is None
                and correspondent_match is None
            ):
                missing_fields.append("correspondent")
            all_fields_extracted = not missing_fields
            write_metadata: dict[str, object] = {
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
            }
            if write_problems:
                write_metadata["problems"] = write_problems
            self._finish_phase(active_phase, metadata=write_metadata)

            active_phase = self._start_phase(job, JobPhase.CLEANUP)
            self._finish_phase(active_phase)
            active_phase = self._start_phase(job, JobPhase.COMPLETE)
            job.status = (
                JobStatus.COMPLETED if all_fields_extracted else JobStatus.COMPLETED_WITH_WARNINGS
            )
            job.finished_at = datetime.now(UTC)
            self._finish_phase(active_phase)
            slug = instance_slug_from_connector(job.document.connector) or ""
            JOBS_TOTAL.labels(status=job.status.value, instance_slug=slug).inc()
            if write_problems:
                logger.warning(
                    "Dokumentenauftrag mit Status %s abgeschlossen, aber %d Metadaten-Schritte "
                    "sind fehlgeschlagen: %s",
                    job.status.value,
                    len(write_problems),
                    ", ".join(str(problem["step"]) for problem in write_problems),
                    extra=self._log_extra(job),
                )
            else:
                logger.info(
                    "Dokumentenauftrag abgeschlossen: %s",
                    job.status.value,
                    extra=self._log_extra(job),
                )
        except Exception as exc:
            if current_field is not None:
                location = f"field={current_field}"
                if current_provider is not None:
                    location += f", provider={current_provider}"
                exc.add_note(location)
            error_type = type(exc).__name__
            error_message = redact_sensitive_text(describe_exception(exc))
            retryable = bool(getattr(exc, "retryable", False))
            # Logged first: recording the failure below can fail too, for example
            # when the database is the cause.
            logger.error(
                "Verarbeitungsversuch fehlgeschlagen: %s: %s; %s",
                error_type,
                error_message,
                (
                    "Worker prüft die automatische Wiederholung"
                    if retryable
                    else "keine automatische Wiederholung"
                ),
                exc_info=exc,
                extra={"error_type": error_type, "retryable": retryable},
            )
            try:
                if not self.db.is_active:
                    self.db.rollback()
                if active_phase and active_phase.status == PhaseStatus.RUNNING:
                    self._finish_phase(active_phase, error=error_type)
                job.status = JobStatus.FAILED
                job.error_type = error_type
                job.error_message = error_message
                job.finished_at = datetime.now(UTC)
                self.db.commit()
                slug = instance_slug_from_connector(job.document.connector) or ""
                JOBS_TOTAL.labels(status=JobStatus.FAILED.value, instance_slug=slug).inc()
            except Exception as record_exc:
                logger.error(
                    "Fehlerstatus konnte nicht gespeichert werden; Auftrag bleibt bis zur "
                    "Stillstandsprüfung im bisherigen Status",
                    exc_info=record_exc,
                )
            raise
        finally:
            if connector is not None:
                await connector.close()

    async def _build_title_context(
        self,
        connector: DocumentConnector,
        document: "ConnectorDocument",
        extracted_values: dict[str, object],
    ) -> dict[str, str]:
        created = document.created or ""
        filename = document.filename or ""
        filename_stem, separator, extension = filename.rpartition(".")
        context = {
            key: str(value) if value is not None else "" for key, value in extracted_values.items()
        }
        context.update(
            {
                "document_id": document.external_id,
                "title": document.title or "",
                "original_filename": filename,
                "filename_stem": filename_stem if separator else filename,
                "file_extension": extension if separator else "",
                "mime_type": document.mime_type or "",
                "created_date": created[:10] if len(created) >= 10 else created,
                "correspondent": "",
                "correspondent_id": document.correspondent_id or "",
                "document_type": "",
                "document_type_id": document.document_type_id or "",
                "created_year": created[:4] if len(created) >= 4 else "",
                "created_month": created[5:7] if len(created) >= 7 else "",
                "created_day": created[8:10] if len(created) >= 10 else "",
                "tag_ids": ", ".join(sorted(document.tag_ids, key=lambda value: int(value))),
            }
        )
        if document.correspondent_id and hasattr(connector, "get_correspondent_name"):
            try:
                name = await connector.get_correspondent_name(document.correspondent_id)
            except Exception as exc:  # noqa: BLE001 -- best-effort enrichment
                logger.warning(
                    "Korrespondentenname für Titel nicht verfügbar; Platzhalter bleibt leer",
                    exc_info=exc,
                )
                name = None
            context["correspondent"] = name or ""
        if document.document_type_id and hasattr(connector, "get_document_type_name"):
            try:
                name = await connector.get_document_type_name(document.document_type_id)
            except Exception as exc:  # noqa: BLE001 -- best-effort enrichment
                logger.warning(
                    "Dokumenttyp für Titel nicht verfügbar; Platzhalter bleibt leer",
                    exc_info=exc,
                )
                name = None
            context["document_type"] = name or ""
        return context

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
