from typing import Final, Literal, NotRequired, TypedDict

VEHICLE_IDENTIFICATION_NUMBER_FIELD_E: Final = "vehicle_identification_number_field_e"
IBAN: Final = "iban"


class ExtractionProfile(TypedDict):
    """Shape of a profile entry.

    Was `dict[str, object]`, which made every lookup return `object` — so
    `field_type not in profile["field_types"]` in schemas.py did not type-check.
    """

    label: str
    field_types: frozenset[str]
    patterns: list[str]
    validators: list[dict[str, object]]
    selection_strategy: NotRequired[Literal["unique", "first", "highest"]]


EXTRACTION_PROFILES: dict[str, ExtractionProfile] = {
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
        "label": "IBAN (Rechnungssteller)",
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
        "validators": [{"type": "iban"}],
        "selection_strategy": "unique",
    },
}


def extraction_profile(profile_key: str | None) -> ExtractionProfile | None:
    if profile_key is None:
        return None
    return EXTRACTION_PROFILES.get(profile_key)
