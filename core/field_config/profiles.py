from typing import Final, Literal, NotRequired, TypedDict

VEHICLE_IDENTIFICATION_NUMBER_FIELD_E: Final = "vehicle_identification_number_field_e"
IBAN: Final = "iban"
INVOICE_GROSS_AMOUNT: Final = "invoice_gross_amount"


class ExtractionProfile(TypedDict):
    """Shape of a profile entry.

    Was `dict[str, object]`, which made every lookup return `object` — so
    `field_type not in profile["field_types"]` in schemas.py did not type-check.
    """

    label: str
    field_types: frozenset[str]
    patterns: list[str]
    validators: list[dict[str, object]]
    selection_strategy: NotRequired[
        Literal["unique", "first", "highest", "pattern_priority_highest"]
    ]
    negative_context_patterns: NotRequired[list[str]]
    negate_on_negative_context: NotRequired[bool]


EXTRACTION_PROFILES: dict[str, ExtractionProfile] = {
    INVOICE_GROSS_AMOUNT: {
        "label": "Rechnungsbruttobetrag (priorisierte Summen und Gutschriften)",
        "field_types": frozenset({"money"}),
        "patterns": [
            # Strong gross-total labels win because the profile uses ordered
            # pattern priority and the highest absolute value within a tier.
            # The line is deliberately bounded so invoice numbers, payment
            # terms and neighbouring table cells cannot become the amount.
            r"(?im)^\s*(?![^\n]{0,80}\b(?:Netto|Skonto|Rabatt|Restzahlung|"
            r"bereits\s+gezahlt)\b)"
            r"(?:Brutto[\s.-]*Rechnungsbetrag|Bruttobetrag|Bruttosumme|"
            r"Summe\s+Brutto|Endsumme(?:\s+brutto)?|Gesamtbetrag(?:\s+brutto)?|"
            r"Gesamtsumme|Gesamtrechnungsbetrag|Rechnungssumme(?:\s+brutto)?|"
            r"Rechnungswert\s*\(\s*brutto\s*\)|Endbetrag|Erstattungsbetrag|"
            r"Grand\s+Total|Invoice\s+Total|Total\s+Amount|"
            r"(?<!Netto[ -])(?<![\w-])Rechnungsbetrag)"
            r"[ \t]*(?:EUR|Euro|€|CHF|USD)?[ \t]*[:.=]?[ \t]*"
            r"(?:EUR|Euro|€|CHF|USD)?[ \t]*"
            r"([-−]?\s*(?:\d{1,3}(?:[.,'’\u00a0 ]\d{3})+|\d+)[.,]\d{2})"
            r"[ \t]*(?:EUR|Euro|€|CHF|USD)?\s*$",
            # Paperless table/HTML normalization can put the label and value on
            # adjacent lines. Only one following value line is considered.
            r"(?im)^\s*(?:Brutto[\s.-]*Rechnungsbetrag|Bruttobetrag|Bruttosumme|"
            r"Summe\s+Brutto|Endsumme(?:\s+brutto)?|Gesamtbetrag(?:\s+brutto)?|"
            r"Gesamtsumme|Gesamtrechnungsbetrag|Rechnungssumme(?:\s+brutto)?|"
            r"Endbetrag|Erstattungsbetrag|Grand\s+Total|Invoice\s+Total|"
            r"Total\s+Amount|(?<!Netto[ -])Rechnungsbetrag)\s*$"
            r"\s*^\s*(?:EUR|Euro|€|CHF|USD)?\s*"
            r"([-−]?\s*(?:\d{1,3}(?:[.,'’\u00a0 ]\d{3})+|\d+)[.,]\d{2})"
            r"\s*(?:EUR|Euro|€|CHF|USD)?\s*$",
            # Explicit tax-inclusive totals are safe even when the word
            # "Total" is otherwise used for positions or subtotals.
            r"(?im)^\s*Total\s+(?:EUR|Euro|€|CHF|USD)\s+"
            r"(?:inkl\.?|incl\.?)\s*(?:MwSt|USt|VAT)\.?\s*[:.]?\s*"
            r"([-−]?\s*(?:\d{1,3}(?:[.,'’\u00a0 ]\d{3})+|\d+)[.,]\d{2})"
            r"\s*(?:EUR|Euro|€|CHF|USD)?\s*$",
            # Structured net/tax/gross table: capture only the final gross
            # column rather than the net or tax amount.
            r"(?im)^\s*[^\n]{0,160}\bNetto\b[^\n]{0,160}\b(?:MwSt|USt|VAT)\b"
            r"[^\n]{0,160}\bGesamtbetrag\b[^\n]*$"
            r"\s*^\s*[^\n]{0,200}\b(?:EUR|Euro|€|CHF|USD)\s+"
            r"([-−]?\s*\d[\d.,'’\u00a0 ]*[.,]\d{2})\s*$",
            # Common gross-only row. A discount or unit-price row is never a
            # valid invoice total, even when it also contains "Brutto".
            r"(?im)^(?![^\n]{0,240}(?:Skonto|Rabatt|Einzelpreis))"
            r"[^\n]{0,240}\bBrutto(?:\s+in\s+(?:EUR|Euro|€|CHF|USD))?\s+"
            r"([-−]?\s*\d[\d.,'’\u00a0 ]*[.,]\d{2})"
            r"\s*(?:EUR|Euro|€|CHF|USD)?\s*$",
            # Credit totals use distinct labels in several supplier layouts.
            r"(?im)^\s*Gutschrift(?:s)?(?:betrag|summe|wert)\s*"
            r"(?:EUR|Euro|€|CHF|USD)?\s*[:.=]?\s*(?:EUR|Euro|€|CHF|USD)?\s*"
            r"([-−]?\s*\d[\d.,'’\u00a0 ]*[.,]\d{2})"
            r"\s*(?:EUR|Euro|€|CHF|USD)?\s*$",
            # Structured goods/tax/gross table. Capture only the final total.
            r"(?im)^\s*Nettowarenwert\s+MwSt\s+MwSt\s+Betrag\s+"
            r"Total\s+inkl\.?\s*MwSt\.?\s*$"
            r"\s*^\s*\d[\d.,'’\u00a0 ]*[.,]\d{2}\s+"
            r"\d{1,2}(?:[.,]\d{2})?\s*%\s+"
            r"\d[\d.,'’\u00a0 ]*[.,]\d{2}\s+"
            r"([-−]?\s*\d[\d.,'’\u00a0 ]*[.,]\d{2})"
            r"\s*(?:EUR|Euro|€|CHF|USD)?\s*$",
            # Structured net/tax/payable table. Capture only the payable cell.
            r"(?im)^\s*[^\n]{0,80}\bNettobetrag\s+(?:MwSt|USt|VAT)\.?\s+"
            r"\d{1,2}(?:[.,]\d{2})?\s*%\s+"
            r"(?:Zu\s+zahlender\s+Betrag|Gesamtbetrag)\s*$"
            r"\s*^\s*(?:[^\n]{0,120}\b(?:EUR|Euro|€|CHF|USD)\s+)?"
            r"\d[\d.,'’\u00a0 ]*[.,]\d{2}\s+"
            r"(?:(?:EUR|Euro|€|CHF|USD)\s+)?\d[\d.,'’\u00a0 ]*[.,]\d{2}\s+"
            r"(?:(?:EUR|Euro|€|CHF|USD)\s+)?"
            r"([-−]?\s*\d[\d.,'’\u00a0 ]*[.,]\d{2})"
            r"\s*(?:EUR|Euro|€|CHF|USD)?\s*$",
            # Payment terms can repeat the undiscounted invoice total. This is
            # intentionally limited to "ohne Abzug" and a complete date.
            r"(?im)^\s*\d+\s+Tage\s+ohne\s+Abzug\s+bis\s+"
            r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s+"
            r"([-−]?\s*\d[\d.,'’\u00a0 ]*[.,]\d{2})"
            r"\s*(?:EUR|Euro|€|CHF|USD)\s*$",
            # Compatibility tier for OCR rows containing additional columns.
            # It only accepts an amount directly following a strong label;
            # all candidates in this tier compete by absolute value.
            r"(?i)(?<!Netto[ -])(?<!Skonto[ -])(?<!Rabatt[ -])(?:"
            r"Brutto[\s.-]*Rechnungsbetrag|Bruttobetrag|Bruttosumme|"
            r"Endsumme(?:\s+brutto)?|Gesamtsumme|Gesamtrechnungsbetrag|"
            r"Zahlungsbetrag|Zahlbetrag|Gesamt\s+Brutto|"
            r"Rechnungssumme(?:\s+brutto)?|Endbetrag)"
            r"[ \t]*(?:EUR|Euro|€|CHF|USD)?[ \t]*[:.=]?[ \t]*"
            r"(?:EUR|Euro|€|CHF|USD)?[ \t]*"
            r"([-−]?\s*\d[\d.,'’\u00a0]*[.,]\d{2})"
            r"[ \t]*(?:EUR|Euro|€|CHF|USD)?",
            # Conservative fallback for layouts that only expose "Summe" or
            # "Gesamtpreis". Strong labels above always win by priority.
            r"(?im)^\s*(?![^\n]{0,80}\b(?:Netto|Skonto|Rabatt|Zwischensumme|"
            r"Restbetrag|Restzahlung)\b)(?:Summe|Gesamtpreis)\s*[:.]?\s*"
            r"(?:EUR|Euro|€|CHF|USD)?\s*"
            r"([-−]?\s*(?:\d{1,3}(?:[.,'’\u00a0 ]\d{3})+|\d+)[.,]\d{2})"
            r"\s*(?:EUR|Euro|€|CHF|USD)\s*$",
        ],
        "validators": [{"type": "not_empty"}, {"type": "monetary_amount"}],
        "selection_strategy": "pattern_priority_highest",
        "negative_context_patterns": [
            r"(?im)^\s*(?:Gutschrift(?:s)?(?:betrag|summe|wert)?|Stornorechnung|"
            r"Credit\s+Note|Credit\s+Memo)\b",
            r"(?im)^\s*Erstattungsbetrag\b",
        ],
        "negate_on_negative_context": True,
    },
    VEHICLE_IDENTIFICATION_NUMBER_FIELD_E: {
        "label": "Fahrzeug-ID (FIN/VIN) aus Feld E",
        "field_types": frozenset({"text"}),
        "patterns": [
            r"(?im)^\s*\**E\**\s*[:.]?\s*\**"
            r"((?:[A-HJ-NPR-Z0-9][ \t-]?){16}[A-HJ-NPR-Z0-9])\**(?:\s|$)",
        ],
        "validators": [{"type": "vehicle_identification_number"}],
    },
    IBAN: {
        "label": "IBAN",
        "field_types": frozenset({"text"}),
        "patterns": [
            # Explicit IBAN labels, including common table headings. The bounded
            # payer-context guard prevents customer accounts from direct-debit
            # paragraphs being treated as the invoice issuer's account.
            r"(?im)^(?<!Lastschrift[^\n]{0,120}\n)(?<!abgebucht[^\n]{0,120}\n)"
            r"(?<!von[^\S\r\n]+Ihrem[^\S\r\n]+Konto[^\n]{0,120}\n)(?<!Mandat[^\n]{0,120}\n)"
            r"(?![^\n]{0,120}\b(?:Lastschrift|abgebucht|von[^\S\r\n]+Ihrem[^\S\r\n]+Konto|Mandat)\b)"
            r"[^\n]{0,120}?\b(?:IBAN[^\S\r\n]*/[^\S\r\n]*BIC|"
            r"Kontonummer[^\S\r\n]*\([^\S\r\n]*IBAN[^\S\r\n]*\)|"
            r"IBAN(?:[^\S\r\n.-]*[.-]?[^\S\r\n.-]*Nr\.?)?)"
            r"[^\S\r\n]*[:.]?[^\S\r\n|]*[|]?[^\S\r\n]*"
            r"([A-Z]{2}[ \t\u00a0\u202f]{0,4}\d{2}"
            r"(?:[ \t\u00a0\u202f]{0,4}[A-Z0-9]){11,30}?)"
            r"(?=[ \t\u00a0\u202f]*(?:\b(?:BIC|SWIFT|Bank(?:name)?)\b|[|;,]|$))",
            # Unlabelled account in a clearly named bank-details block. Only the
            # immediately following line is considered to keep the context tight.
            r"(?im)^(?<!Lastschrift[^\n]{0,120}\n)(?<!abgebucht[^\n]{0,120}\n)"
            r"(?<!von[^\S\r\n]+Ihrem[^\S\r\n]+Konto[^\n]{0,120}\n)(?<!Mandat[^\n]{0,120}\n)"
            r"(?![^\n]{0,120}\b(?:Lastschrift|abgebucht|von[^\S\r\n]+Ihrem[^\S\r\n]+Konto|Mandat)\b)"
            r"[^\n]{0,80}\b(?:Bankverbindung|Kontoverbindung)\b[^\n]{0,80}\n[ \t|]*"
            r"([A-Z]{2}[ \t\u00a0\u202f]{0,4}\d{2}"
            r"(?:[ \t\u00a0\u202f]{0,4}[A-Z0-9]){11,30}?)"
            r"(?=[ \t\u00a0\u202f]*(?:\b(?:BIC|SWIFT|Bank(?:name)?)\b|[|;,]|$))",
        ],
        "validators": [{"type": "iban_format"}],
        "selection_strategy": "unique",
    },
}


def extraction_profile(profile_key: str | None) -> ExtractionProfile | None:
    if profile_key is None:
        return None
    return EXTRACTION_PROFILES.get(profile_key)
