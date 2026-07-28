import unicodedata

from connectors.base.interface import ConnectorCustomField
from core.templates.schema import TemplateConfig


def _normalized_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(character for character in decomposed if character.isalnum()).casefold()


FIELD_DEFINITIONS: dict[str, dict[str, object]] = {
    "rechnungsnummer": {
        "key": "invoice_number",
        "field_name": "Rechnungsnummer",
        "value_hint": "Exakter alphanumerischer Wert ohne Label",
        "instructions": (
            "Bevorzuge Rechnungsnummer, Rechnungs-Nr. oder Belegnummer. "
            "Nicht Kunden-, Bestell- oder Lieferscheinnummer verwenden."
        ),
        "validators": [{"type": "not_empty"}, {"type": "length", "min": 1, "max": 100}],
        "patterns": [
            r"(?i)(?:Rechnungsnummer|Rechnung(?:s)?[\s.-]*(?:Nr|Nummer)\.?)"
            r"\s*[:.]?\s*([A-Z0-9][A-Z0-9./_-]*)"
        ],
    },
    "rechnungsbetrag": {
        "key": "invoice_amount",
        "field_name": "Rechnungsbetrag",
        "value_hint": "Deutscher Dezimalbetrag ohne Währung, zum Beispiel 1234,56",
        "instructions": (
            "Extrahiere den zu zahlenden Brutto-Endbetrag, nicht Netto, Steuer oder Einzelposition."
        ),
        "validators": [{"type": "not_empty"}, {"type": "monetary_amount"}],
        "patterns": [
            r"(?i)(?:Bruttobetrag|Gesamtbetrag|Rechnungsbetrag)"
            r"\s*[:.]?\s*([\d.]+,\d{2}\s*(?:EUR|€)?)"
        ],
    },
    "lieferscheinnummer": {
        "key": "delivery_note_number",
        "field_name": "Lieferscheinnummer",
        "value_hint": "Exakter alphanumerischer Wert ohne Label",
        "instructions": (
            "Bevorzuge Lieferscheinnummer oder Lieferschein-Nr. "
            "Nicht Bestell- oder Rechnungsnummer verwenden."
        ),
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
                },
                {
                    "type": "ollama",
                    "field_name": definition["field_name"],
                    "value_hint": definition["value_hint"],
                    "instructions": definition["instructions"],
                },
            ],
            "validators": definition["validators"],
            "minimum_confidence": 0.55,
        }
    if not configured:
        return None
    return TemplateConfig.model_validate({"fields": configured})
