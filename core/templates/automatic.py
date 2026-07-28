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
        "selection_strategy": "first",
        "patterns": [
            r"(?im)^\s*Datum\s*:\s+"
            r"(?:Rechnungsnummer|Rechnung(?:s)?[\s.-]*(?:Nr|Nummer)\.?)\s*:\s+"
            r"(?:Kundennummer|Kunden[\s.-]*(?:Nr|Nummer)\.?)\s*:\s*$"
            r"\s*^\s*\d{1,2}\.\d{1,2}\.\d{4}\s+"
            r"([A-Z0-9][A-Z0-9./_-]*)\s+"
            r"[A-Z0-9][A-Z0-9./_-]*\s*$",
            r"(?i)(?:Rechnungsnummer|Rechnung(?:s)?[\s.-]*(?:Nr|Nummer)\.?)"
            r"\s*[:.]?[ \t]*"
            r"(?!Kunden(?:nummer|[\s.-]*(?:Nr|Nummer)\.?))"
            r"([A-Z0-9][A-Z0-9./_-]*)",
            r"(?i)(?:Kundennummer|Kunden[\s.-]*(?:Nr|Nummer)\.?)"
            r"\s*[:.]?[ \t]*([A-Z0-9][A-Z0-9./_-]*)",
        ],
    },
    "rechnungsbetrag": {
        "key": "invoice_amount",
        "validators": [{"type": "not_empty"}, {"type": "monetary_amount"}],
        "selection_strategy": "highest",
        "patterns": [
            r"(?im)^\s*Gesamt\s+"
            r"(?:[\d.]+,\d{2}\s*(?:EUR|€)?\s+)?"
            r"([\d.]+,\d{2})\s*(?:EUR|€)?\s*$",
            r"(?im)^\s*Übertrag\s*:\s*"
            r"(?:EUR|€)?\s*([\d.]+,\d{2})\s*(?:EUR|€|Euro)?\s*$",
            r"(?i)(?:"
            r"Brutto[\s.-]*Rechnungsbetrag|"
            r"Bruttobetrag|"
            r"Gesamtbetrag|"
            r"Gesamtsumme|"
            r"Rechnungswert\s*\(\s*brutto\s*\)|"
            r"Zahlbetrag|"
            r"Endbetrag|"
            r"Zu\s+zahlen|"
            r"(?<!Netto[ -])(?<![\w-])Rechnungsbetrag"
            r")\s*[:.]?\s*(?:EUR|€)?\s*([\d.]+,\d{2})\s*(?:EUR|€)?",
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
            "selection_strategy": definition.get("selection_strategy", "unique"),
        }
    if not configured:
        return None
    return TemplateConfig.model_validate({"fields": configured})
