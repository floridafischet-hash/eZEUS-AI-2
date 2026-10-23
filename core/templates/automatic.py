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
            r"(?im)^\s*[^\n]{0,80}\bRechnungsnr\.?\s+Datum\s+Seite\s*$"
            r"\s*^\s*[A-Z0-9][A-Z0-9./_-]*\s+"
            r"(?=[A-Z0-9./_-]*\d)([A-Z0-9][A-Z0-9./_-]*)\s+"
            r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s+\d{1,3}\.?\s+\d{1,3}\s*$",
            r"(?im)^\s*[^\n]{0,40}\s+Seite\s+Datum\s+"
            r"[A-ZÄÖÜ][A-ZÄÖÜa-zäöüß]*[\s.-]*(?:Nr|Nummer)\.?\s+"
            r"Rechnung\s+(?:Nr|Nummer)\.?\s*$"
            r"\s*^\s*\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s+\d{1,3}\s+"
            r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s+"
            r"[A-Z0-9][A-Z0-9./_-]*\s+"
            r"(?=[A-Z0-9./_-]*\d)([A-Z0-9][A-Z0-9./_-]*)\s*$",
            r"(?im)^\s*(?:KD-Nr\.?\s+)?Rechn\.?Nr\.?\s+Datum\s+Blatt\s*$"
            r"\s*^\s*[A-Z0-9./_-]+\s+[A-Z0-9./_-]+\s+"
            r"(?=\d{5,12}\b)(\d{5,12})\s+\d{1,2}[./-]\d{1,2}[./-]\d{2,4}"
            r"(?:\s+\d{1,3})?\s*$",
            r"(?im)^\s*Kundennummer\s+Belegnummer\s+Belegdatum"
            r"(?:\s+Seite\s+\d+)?\s*$"
            r"\s*^\s*(?:Rechnung\s+)?"
            r"[A-Z0-9][A-Z0-9./_-]*\s+"
            r"(?=[A-Z0-9./_-]*\d)([A-Z0-9][A-Z0-9./_-]*)\s+"
            r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s*$",
            r"(?im)^\s*Kunden[\s.-]*(?:Nr|Nummer)\.?\s+Rechnung\s+Datum\s*$"
            r"\s*^\s*[A-Z0-9][A-Z0-9./_-]*\s+"
            r"(?=[A-Z0-9./_-]*\d)([A-Z0-9][A-Z0-9./_-]*)\s+"
            r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s*$",
            r"(?im)^\s*Datum\s*:\s+"
            r"(?:Rechnungsnummer|Rechnung(?:s)?[\s.-]*(?:Nr|Nummer)\.?)\s*:\s+"
            r"(?:Kundennummer|Kunden[\s.-]*(?:Nr|Nummer)\.?)\s*:\s*$"
            r"\s*^\s*\d{1,2}\.\d{1,2}\.\d{4}\s+"
            r"([A-Z0-9][A-Z0-9./_-]*)\s+"
            r"[A-Z0-9][A-Z0-9./_-]*\s*$",
            r"(?i)\bRe\s*-\s*Nr\.?\s*:\s*"
            r"(?=[A-Z0-9./_-]*\d)([A-Z0-9][A-Z0-9./_-]*)",
            r"(?i)(?:Rechnungsnummer|Rechnung(?:s)?[\s.-]*(?:Nr|Nummer)\.?)"
            r"[ \t]*[:.]?[ \t]*"
            r"(?!Kunden(?:nummer|[\s.-]*(?:Nr|Nummer)\.?))"
            r"(?=[A-Z0-9./_-]*\d)"
            r"([A-Z0-9][A-Z0-9./_-]*)",
            r"(?im)^\s*(?:#{1,6}\s*)?Rechnung(?:\s+Nr\.?)?\s*[:;]?\s*"
            r"(?=[A-Z0-9./_-]*\d)([A-Z0-9][A-Z0-9./_-]*)"
            r"(?:\s+vom\s+\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\s+Seite\s*:?\s*\d+)?\s*$",
            r"(?im)^\s*RG[.\s-]*NR\.?\s*[:.]?\s*\.?\s*"
            r"(?=[A-Z0-9./_-]*\d)([A-Z0-9][A-Z0-9./_-]*)\s*$",
            r"(?im)^\s*Bon[\s.-]*(?:Nr|Nummer)\.?\s*:\s*"
            r"([A-Z0-9][A-Z0-9./_-]*)\s*$",
            r"(?i)Beleg(?:s)?[\s.-]*(?:Nr|Nummer)\.?"
            r"\s*[:.]?\s*"
            r"(?=[A-Z0-9./_-]*\d)"
            r"([A-Z0-9][A-Z0-9./_-]*)",
        ],
    },
    "rechnungsbetrag": {
        "key": "invoice_amount",
        "validators": [{"type": "not_empty"}, {"type": "monetary_amount"}],
        "selection_strategy": "highest",
        "patterns": [
            r"(?im)^\s*Netto\s+MwSt\.?\s+\d{1,2}(?:[.,]\d{2})?\s*%\s+"
            r"Gesamtbetrag\s*$"
            r"\s*^\s*[\d.,]+\d{2}\s+[\d.,]+\d{2}\s+"
            r"(?:EUR|€)\s+([\d.,]+\d{2})\s*$",
            r"(?im)^\s*Nettowarenwert\s+MwSt\s+MwSt\s+Betrag\s+"
            r"Total\s+inkl\.?\s*MwSt\.?\s*$"
            r"\s*^\s*[\d.,]+\d{2}\s+"
            r"\d{1,2}(?:[.,]\d{2})?\s*%\s+"
            r"[\d.,]+\d{2}\s+"
            r"([\d.,]+\d{2})\s*(?:EUR|€)?\s*$",
            r"(?im)^\s*Total\s+(?:EUR|€)\s+inkl\.?\s*(?:MwSt|USt)\.?\s*[:.]?\s*"
            r"([\d.,]+\d{2})\s*(?:EUR|€)?\s*$",
            r"(?im)^\s*Gesamt\s+"
            r"(?:[\d.,]+\d{2}\s*(?:EUR|€)?\s+)?"
            r"([\d.,]+\d{2})\s*(?:EUR|€)?\s*$",
            r"(?im)^\s*Gesamt\s*:\s*(?:EUR|€)?\s*"
            r"([\d.,]+\d{2})\s*(?:EUR|€)?\s*$",
            r"(?im)^\s*Fälligkeitsdatum\s*:\s*\d{1,2}[./-]\d{1,2}[./-]\d{2,4}"
            r"\s+Summe\s*:\s*(?:EUR|€)?\s*([\d.,]+\d{2})\s*(?:EUR|€)?\s*$",
            r"(?im)^\s*Artikel\s*:\s*\d+\s+Total\s*:\s*"
            r"(?:EUR|€)?\s*([\d.,]+\d{2})\s*(?:EUR|€)?\s*$",
            r"(?im)^\s*(?:Endsumme|Summe\s+Brutto)\s+(?:EUR|Euro|€)\s+"
            r"([\d.,]+\d{2})\s*$",
            r"(?im)^\s*Summe\s+([\d.,]+\d{2})\s*(?:EUR|€)\s*$",
            r"(?im)^\s*Gesamtpreis(?!\s*\(\s*netto\s*\))\s*[:.]?\s*"
            r"([\d.,]+\d{2})\s*(?:EUR|€)\s*$",
            r"(?im)^\s*\d+\s+Tage\s+ohne\s+Abzug\s+bis\s+"
            r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s+([\d.,]+\d{2})\s*(?:EUR|€)\s*$",
            r"(?im)^\s*[^\n]{0,80}\bNettobetrag\s+MwSt\.?\s+\d{1,2}(?:[.,]\d{2})?\s*%\s+"
            r"(?:Zu\s+zahlender\s+Betrag|Gesamtbetrag)\s*$"
            r"\s*^\s*(?:[^\n]{0,120}\bEUR\s+)?[\d.,]+\d{2}\s+"
            r"(?:EUR\s+)?[\d.,]+\d{2}\s+"
            r"(?:EUR\s+)?([\d.,]+\d{2})\s*(?:EUR)?\s*$",
            r"(?i)\bGesamtbetrag\s+in\s+(?:EUR|€)\s+"
            r"inkl\.?\s*(?:MwSt|USt)\.?\s*[:.=]?\s*"
            r"([\d.,]+\d{2})\s*(?:EUR|€)?",
            r"(?i)(?:"
            r"Brutto[\s.-]*Rechnungsbetrag|"
            r"Bruttobetrag|"
            r"Bruttosumme|"
            r"Endsumme\s+brutto|"
            r"Gesamtbetrag|"
            r"Gesamtbetrag\s+brutto|"
            r"Gesamtsumme|"
            r"Gesamtrechnungsbetrag|"
            r"Erstattungsbetrag|"
            r"Zahlungsbetrag|"
            r"Zahlbetrag(?:\s+Rechnung\s+[A-Z0-9./_-]+)?|"
            r"Gesamt\s+Brutto|"
            r"Rechnungssumme\s+brutto|"
            r"Rechnungssumme|"
            r"Rechnungswert\s*\(\s*brutto\s*\)|"
            r"Verbleibende\s+Restzahlung(?:\s+des\s+\d+\.\s*Abschlag\.?)?|"
            r"Endbetrag|"
            r"(?<!Netto[ -])(?<![\w-])Rechnungsbetrag"
            r")[ \t]*(?:EUR|€)?[ \t]*[:.=]?[ \t]*(?:EUR|€)?[ \t]*"
            r"([\d.,]+\d{2})[ \t]*(?:EUR|€)?",
            r"(?im)^\s*(?:Bruttosumme|Endsumme\s+brutto|Gesamtbetrag|Gesamtsumme|"
            r"Gesamtrechnungsbetrag|Rechnungssumme(?:\s+brutto)?|Endbetrag)\s*$"
            r"\s*^\s*(?:EUR|€)?\s*([\d.,]+\d{2})\s*(?:EUR|€)?\s*$",
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
