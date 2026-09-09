from typing import Final, TypedDict

VEHICLE_IDENTIFICATION_NUMBER_FIELD_E: Final = "vehicle_identification_number_field_e"


class ExtractionProfile(TypedDict):
    """Shape of a profile entry.

    Was `dict[str, object]`, which made every lookup return `object` — so
    `field_type not in profile["field_types"]` in schemas.py did not type-check.
    """

    label: str
    field_types: frozenset[str]
    patterns: list[str]
    validators: list[dict[str, object]]


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
}


def extraction_profile(profile_key: str | None) -> ExtractionProfile | None:
    if profile_key is None:
        return None
    return EXTRACTION_PROFILES.get(profile_key)
