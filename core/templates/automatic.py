import unicodedata

from connectors.base.interface import ConnectorCustomField
from core.templates.schema import TemplateConfig


def _normalized_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(character for character in decomposed if character.isalnum()).casefold()


FIELD_DEFINITIONS: dict[str, dict[str, object]] = {
    "rechnungsnummer": {
        "key": "invoice_number",
        "validators": [{"type": "not_empty"}, {"type": "length", "min": 1, "max": 100}],
        "patterns": [
            r"(?i)(?:Rechnungsnummer|Rechnung(?:s)?[\s.-]*(?:Nr|Nummer)\.?)"
            r"\s*[:.]?\s*([A-Z0-9][A-Z0-9./_-]*)"
        ],
    },
    "rechnungsbetrag": {
        "key": "invoice_amount",
        "validators": [{"type": "not_empty"}, {"type": "monetary_amount"}],
        "patterns": [
            r"(?i)(?:Brutto[\s.-]*Rechnungsbetrag|Bruttobetrag|Gesamtbetrag|Rechnungsbetrag)"
            r"\s*[:.]?\s*([\d.]+,\d{2}\s*(?:EUR|€)?)"
        ],
    },
    "lieferscheinnummer": {
        "key": "delivery_note_number",
        "validators": [{"type": "not_empty"}, {"type": "length", "min": 1, "max": 100}],
        "patterns": [
            r"(?i)(?:Lieferscheinnummer|Lieferschein[\s.-]*(?:Nr|Nummer)\.?)"
            r"\s*[:.]?\s*([A-Z0-9][A-Z0-9./_-]*)"
        ],
    },
}


def config_from_custom_fields(fields: list[ConnectorCustomField]) -> TemplateConfig | None:
    configured: dict[str, object] = {}
    for field in fields:
        definition = FIELD_DEFINITIONS.get(_normalized_name(field.name))
        if definition is None:
            continue
        configured[str(definition["key"])] = {
            "target_field_id": int(field.external_id),
            "providers": [
                {
                    "type": "regex",
                    "patterns": definition["patterns"],
                }
            ],
            "validators": definition["validators"],
            "minimum_confidence": 0.55,
        }
    if not configured:
        return None
    return TemplateConfig.model_validate({"fields": configured})
