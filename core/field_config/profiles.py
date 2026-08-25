from typing import Final

VEHICLE_IDENTIFICATION_NUMBER_FIELD_E: Final = "vehicle_identification_number_field_e"

EXTRACTION_PROFILES: dict[str, dict[str, object]] = {
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


def extraction_profile(profile_key: str | None) -> dict[str, object] | None:
    if profile_key is None:
        return None
    return EXTRACTION_PROFILES.get(profile_key)
