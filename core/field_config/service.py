import re
import unicodedata
from hashlib import sha256
from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from connectors.base.interface import ConnectorCustomField, DocumentConnector
from core.field_config.schemas import FieldConfigurationInput
from core.models.audit import AuditEntry
from core.models.instance_field_config import InstanceFieldConfig
from core.models.paperless_instance import PaperlessInstance
from core.templates.automatic import FIELD_DEFINITIONS
from core.templates.schema import TemplateConfig

STANDARD_FIELDS: tuple[dict[str, object], ...] = (
    {
        "field_key": "correspondent",
        "label": "Korrespondent",
        "field_type": "text",
        "sort_order": 10,
        "required": False,
    },
    {
        "field_key": "invoice_number",
        "label": "Rechnungsnummer",
        "field_type": "text",
        "sort_order": 20,
        "required": True,
    },
    {
        "field_key": "invoice_date",
        "label": "Rechnungsdatum",
        "field_type": "date",
        "sort_order": 30,
        "required": False,
    },
    {
        "field_key": "invoice_amount",
        "label": "Rechnungsbetrag",
        "field_type": "money",
        "sort_order": 40,
        "required": True,
    },
    {
        "field_key": "customer_number",
        "label": "Kundennummer",
        "field_type": "text",
        "sort_order": 50,
        "required": False,
    },
    {
        "field_key": "construction_site_number",
        "label": "Baustellennummer",
        "field_type": "text",
        "sort_order": 60,
        "required": False,
    },
)

STANDARD_PATTERNS: dict[str, list[str]] = {
    "invoice_number": cast(list[str], FIELD_DEFINITIONS["rechnungsnummer"]["patterns"]),
    "invoice_amount": cast(list[str], FIELD_DEFINITIONS["rechnungsbetrag"]["patterns"]),
    "invoice_date": [
        r"(?i)(?:Rechnungsdatum|Datum)\s*[:.]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})"
    ],
    "customer_number": [
        r"(?i)(?:Kundennummer|Kunden[\s.-]*(?:Nr|Nummer)\.?)"
        r"\s*[:.]?\s*([A-Z0-9][A-Z0-9./_-]*)"
    ],
    "construction_site_number": [
        r"(?i)(?:BV(?:[\s.-]*(?:Nr|Nummer))?\.?|"
        r"Baustellen?(?:[\s.-]*(?:Nr|Nummer))\.?)"
        r"\s*[:.]?\s*([A-Z0-9][A-Z0-9./_-]*)"
    ],
}

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "invoice_number": ("rechnungsnummer",),
    "invoice_date": ("rechnungsdatum",),
    "invoice_amount": ("rechnungsbetrag",),
    "customer_number": ("kundennummer",),
    "construction_site_number": ("baustellennummer", "baustellennr", "bvnummer"),
}

PAPERLESS_FIELD_TYPES = {
    "text": "string",
    "number": "float",
    "money": "monetary",
    "date": "date",
    "boolean": "boolean",
    "select": "select",
    "textarea": "longtext",
}

PAPERLESS_COMPATIBLE_TYPES: dict[str, frozenset[str]] = {
    "text": frozenset({"string", "url", "documentlink"}),
    "number": frozenset({"float", "integer"}),
    "money": frozenset({"monetary"}),
    "date": frozenset({"date"}),
    "boolean": frozenset({"boolean"}),
    "select": frozenset({"select"}),
    "textarea": frozenset({"longtext", "string"}),
}

FIELD_TYPE_BY_PAPERLESS_TYPE = {
    "string": "text",
    "url": "text",
    "documentlink": "text",
    "integer": "number",
    "float": "number",
    "monetary": "money",
    "date": "date",
    "boolean": "boolean",
    "select": "select",
    "longtext": "textarea",
}


@dataclass(frozen=True)
class RuntimeFieldConfiguration:
    template: TemplateConfig
    enabled_keys: frozenset[str]
    required_keys: frozenset[str]
    correspondent_enabled: bool
    correspondent_required: bool


def normalized_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(character for character in decomposed if character.isalnum()).casefold()


class FieldConfigurationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def instance_by_slug(self, slug: str) -> PaperlessInstance | None:
        return self.db.scalar(select(PaperlessInstance).where(PaperlessInstance.slug == slug))

    def ensure_defaults(self, instance: PaperlessInstance) -> list[InstanceFieldConfig]:
        existing = self.list_fields(instance.id)
        if existing:
            return existing
        for definition in STANDARD_FIELDS:
            self.db.add(
                InstanceFieldConfig(
                    instance_id=instance.id,
                    field_key=str(definition["field_key"]),
                    label=str(definition["label"]),
                    field_type=str(definition["field_type"]),
                    sort_order=int(str(definition["sort_order"])),
                    is_standard=True,
                    enabled=True,
                    required=bool(definition["required"]),
                    ocr_enabled=True,
                    ai_enabled=False,
                    options=[],
                )
            )
        self.db.commit()
        return self.list_fields(instance.id)

    def list_fields(self, instance_id: UUID) -> list[InstanceFieldConfig]:
        return list(
            self.db.scalars(
                select(InstanceFieldConfig)
                .where(InstanceFieldConfig.instance_id == instance_id)
                .order_by(InstanceFieldConfig.sort_order, InstanceFieldConfig.created_at)
            )
        )

    @staticmethod
    def serialize(field: InstanceFieldConfig) -> dict[str, object]:
        return {
            "id": str(field.id),
            "field_key": field.field_key,
            "label": field.label,
            "field_type": field.field_type,
            "sort_order": field.sort_order,
            "is_standard": field.is_standard,
            "enabled": field.enabled,
            "required": field.required,
            "ocr_enabled": field.ocr_enabled,
            "ai_enabled": field.ai_enabled,
            "external_field_id": field.external_field_id,
            "options": field.options or [],
            "extraction_instructions": field.extraction_instructions,
        }

    def save(
        self,
        instance: PaperlessInstance,
        payloads: list[FieldConfigurationInput],
        *,
        actor: str,
    ) -> list[InstanceFieldConfig]:
        existing = {field.field_key: field for field in self.ensure_defaults(instance)}
        standard_keys = {str(item["field_key"]) for item in STANDARD_FIELDS}
        seen: set[str] = set()
        for payload in payloads:
            key = payload.field_key or f"custom_{uuid4().hex[:12]}"
            if key in seen:
                raise ValueError(f"Duplicate field key: {key}")
            seen.add(key)
            field = existing.get(key)
            if field is None:
                if key in standard_keys:
                    raise ValueError(f"Standard field cannot be recreated: {key}")
                field = InstanceFieldConfig(
                    instance_id=instance.id,
                    field_key=key,
                    label=payload.label,
                    field_type=payload.field_type,
                    sort_order=payload.sort_order,
                    is_standard=False,
                    enabled=payload.enabled,
                    required=payload.required,
                    ocr_enabled=payload.ocr_enabled,
                    ai_enabled=payload.ai_enabled,
                    external_field_id=payload.external_field_id,
                    options=payload.options,
                    extraction_instructions=payload.extraction_instructions,
                )
                self.db.add(field)
                old_value: object = None
            else:
                old_value = self.serialize(field)
                field.label = payload.label
                field.field_type = payload.field_type
                field.sort_order = payload.sort_order
                field.enabled = payload.enabled
                field.required = payload.required
                field.ocr_enabled = payload.ocr_enabled
                field.ai_enabled = payload.ai_enabled
                field.external_field_id = payload.external_field_id
                field.options = payload.options
                field.extraction_instructions = payload.extraction_instructions
            self.db.flush()
            new_value = self.serialize(field)
            if old_value != new_value:
                self.db.add(
                    AuditEntry(
                        actor=actor,
                        action="UPDATE_FIELD_CONFIGURATION",
                        entity_type="instance_field_config",
                        entity_id=str(field.id),
                        instance_id=instance.id,
                        target_system="ezeus",
                        field=key,
                        old_value=old_value,
                        new_value=new_value,
                        details={"tenant_slug": instance.slug},
                    )
                )
        missing_standard = standard_keys - seen
        if missing_standard:
            raise ValueError(
                f"Standard fields must remain in the configuration: {sorted(missing_standard)}"
            )
        self.db.commit()
        return self.list_fields(instance.id)

    async def import_paperless_fields(
        self,
        instance: PaperlessInstance,
        connector: DocumentConnector,
        *,
        actor: str,
    ) -> list[InstanceFieldConfig]:
        remote_fields = await connector.list_custom_fields()
        configured = self.ensure_defaults(instance)
        by_external_id = {
            field.external_field_id: field
            for field in configured
            if field.external_field_id is not None
        }
        by_name = {normalized_name(field.label): field for field in configured}
        used_keys = {field.field_key for field in configured}
        next_sort_order = max((field.sort_order for field in configured), default=0) + 10

        for remote in remote_fields:
            field = by_external_id.get(remote.external_id)
            if field is None:
                field = by_name.get(normalized_name(remote.name))
            if field is not None:
                if field.external_field_id is None:
                    field.external_field_id = remote.external_id
                    self.db.add(
                        AuditEntry(
                            actor=actor,
                            action="LINK_PAPERLESS_CUSTOM_FIELD",
                            entity_type="instance_field_config",
                            entity_id=str(field.id),
                            instance_id=instance.id,
                            target_system="paperless",
                            field=field.field_key,
                            old_value=None,
                            new_value=remote.external_id,
                            details={"tenant_slug": instance.slug, "source": "paperless_import"},
                        )
                    )
                continue

            field_key = self._paperless_field_key(remote.external_id, used_keys)
            options = self._paperless_options(remote)
            field = InstanceFieldConfig(
                instance_id=instance.id,
                field_key=field_key,
                label=remote.name,
                field_type=FIELD_TYPE_BY_PAPERLESS_TYPE.get(remote.data_type, "text"),
                sort_order=next_sort_order,
                is_standard=False,
                enabled=False,
                required=False,
                ocr_enabled=True,
                ai_enabled=False,
                external_field_id=remote.external_id,
                options=options,
                extraction_instructions=None,
            )
            self.db.add(field)
            self.db.flush()
            self.db.add(
                AuditEntry(
                    actor=actor,
                    action="IMPORT_PAPERLESS_CUSTOM_FIELD",
                    entity_type="instance_field_config",
                    entity_id=str(field.id),
                    instance_id=instance.id,
                    target_system="paperless",
                    field=field.field_key,
                    old_value=None,
                    new_value=self.serialize(field),
                    details={
                        "tenant_slug": instance.slug,
                        "paperless_data_type": remote.data_type,
                    },
                )
            )
            by_external_id[remote.external_id] = field
            by_name[normalized_name(remote.name)] = field
            used_keys.add(field_key)
            next_sort_order += 10

        self.db.commit()
        return self.list_fields(instance.id)

    def runtime_config(
        self,
        instance: PaperlessInstance,
        paperless_fields: list[ConnectorCustomField],
    ) -> RuntimeFieldConfiguration:
        configured = self.ensure_defaults(instance)
        external_by_name = {
            normalized_name(field.name): int(field.external_id) for field in paperless_fields
        }
        external_by_id = {int(field.external_id): field for field in paperless_fields}
        template_fields: dict[str, object] = {}
        enabled_keys: set[str] = set()
        required_keys: set[str] = set()
        correspondent_enabled = False
        correspondent_required = False
        for field in configured:
            if not field.enabled:
                continue
            enabled_keys.add(field.field_key)
            if field.required:
                required_keys.add(field.field_key)
            if field.field_key == "correspondent":
                correspondent_enabled = field.ocr_enabled or field.ai_enabled
                correspondent_required = field.required
                continue
            target_id = self._target_id(field, external_by_name)
            value_mapping: dict[str, object] = {}
            remote_field = external_by_id.get(target_id) if target_id is not None else None
            if field.field_type == "select" and remote_field is not None:
                remote_options = remote_field.extra_data.get("select_options", [])
                if isinstance(remote_options, list):
                    value_mapping = {
                        str(option["label"]): option["id"]
                        for option in remote_options
                        if isinstance(option, dict)
                        and option.get("label") is not None
                        and option.get("id") is not None
                    }
            providers: list[dict[str, object]] = []
            if field.ocr_enabled:
                patterns = STANDARD_PATTERNS.get(field.field_key)
                if patterns is None:
                    escaped = re.escape(field.label)
                    patterns = [rf"(?im)^\s*{escaped}\s*[:.]?\s*(.+?)\s*$"]
                providers.append({"type": "regex", "patterns": patterns})
            if field.ai_enabled:
                providers.append(
                    {
                        "type": "ollama",
                        "field_name": field.label,
                        "value_hint": field.field_type,
                        "instructions": field.extraction_instructions or "",
                    }
                )
            template_fields[field.field_key] = {
                "target_field_id": target_id,
                "providers": providers,
                "validators": self._validators(field),
                "minimum_confidence": 0.55,
                "selection_strategy": (
                    "highest" if field.field_type == "money" else "first"
                ),
                "required": field.required,
                "value_mapping": value_mapping,
            }
        return RuntimeFieldConfiguration(
            template=TemplateConfig.model_validate({"fields": template_fields}),
            enabled_keys=frozenset(enabled_keys),
            required_keys=frozenset(required_keys),
            correspondent_enabled=correspondent_enabled,
            correspondent_required=correspondent_required,
        )

    async def synchronize_paperless_fields(
        self,
        instance: PaperlessInstance,
        connector: DocumentConnector,
        *,
        actor: str,
    ) -> list[InstanceFieldConfig]:
        remote_fields = await connector.list_custom_fields()
        remote_by_name = {normalized_name(field.name): field for field in remote_fields}
        for field in self.ensure_defaults(instance):
            if not field.enabled or field.field_key == "correspondent":
                continue
            expected_type = PAPERLESS_FIELD_TYPES[field.field_type]
            remote = None
            if field.external_field_id:
                remote = next(
                    (
                        item
                        for item in remote_fields
                        if item.external_id == field.external_field_id
                    ),
                    None,
                )
            if remote is None:
                remote = remote_by_name.get(normalized_name(field.label))
            compatible_types = PAPERLESS_COMPATIBLE_TYPES[field.field_type]
            if remote is not None and remote.data_type not in compatible_types:
                raise ValueError(
                    f"Paperless field '{field.label}' has type {remote.data_type}, "
                    f"expected {expected_type}"
                )
            if remote is None:
                remote = await connector.create_custom_field(
                    field.label,
                    expected_type,
                    field.options or None,
                )
                remote_fields.append(remote)
                remote_by_name[normalized_name(remote.name)] = remote
            elif remote.name != field.label or expected_type == "select":
                remote = await connector.update_custom_field(
                    remote.external_id,
                    field.label,
                    expected_type,
                    field.options or None,
                )
            if field.external_field_id != remote.external_id:
                old_value = field.external_field_id
                field.external_field_id = remote.external_id
                self.db.add(
                    AuditEntry(
                        actor=actor,
                        action="LINK_PAPERLESS_CUSTOM_FIELD",
                        entity_type="instance_field_config",
                        entity_id=str(field.id),
                        instance_id=instance.id,
                        target_system="paperless",
                        field=field.field_key,
                        old_value=old_value,
                        new_value=remote.external_id,
                        details={"tenant_slug": instance.slug},
                    )
                )
        self.db.commit()
        return self.list_fields(instance.id)

    @staticmethod
    def _paperless_field_key(external_id: str, used_keys: set[str]) -> str:
        safe_id = re.sub(r"[^a-z0-9]+", "_", external_id.casefold()).strip("_")
        base = f"paperless_{safe_id[:40]}" if safe_id else "paperless_field"
        if base not in used_keys:
            return base
        suffix = sha256(external_id.encode()).hexdigest()[:10]
        return f"{base[:53]}_{suffix}"

    @staticmethod
    def _paperless_options(field: ConnectorCustomField) -> list[str]:
        if field.data_type != "select":
            return []
        options = field.extra_data.get("select_options", [])
        if not isinstance(options, list):
            return []
        return [
            str(option["label"])
            for option in options
            if isinstance(option, dict) and option.get("label") is not None
        ]

    @staticmethod
    def _target_id(
        field: InstanceFieldConfig, external_by_name: dict[str, int]
    ) -> int | None:
        if field.external_field_id:
            try:
                return int(field.external_field_id)
            except ValueError:
                return None
        names = (normalized_name(field.label), *FIELD_ALIASES.get(field.field_key, ()))
        return next((external_by_name[name] for name in names if name in external_by_name), None)

    @staticmethod
    def _validators(field: InstanceFieldConfig) -> list[dict[str, object]]:
        validators: list[dict[str, object]] = []
        if field.required:
            validators.append({"type": "not_empty"})
        if field.field_type == "money":
            validators.append({"type": "monetary_amount"})
        elif field.field_type == "number":
            validators.append({"type": "numeric_range"})
        elif field.field_type == "date":
            validators.append({"type": "date"})
        elif field.field_type == "select":
            validators.append({"type": "allowed_values", "values": field.options or []})
        elif field.field_type == "boolean":
            validators.append(
                {
                    "type": "allowed_values",
                    "values": ["Ja", "Nein", "ja", "nein", "true", "false"],
                }
            )
        else:
            validators.append({"type": "length", "min": 1, "max": 4000})
        return validators
