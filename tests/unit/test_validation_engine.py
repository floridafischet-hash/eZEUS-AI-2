from decimal import Decimal

import pytest

from core.validation.engine import ValidationEngine
from plugins.base.interfaces import ExtractionCandidate


def _run(value: str, validators: list[dict[str, object]]) -> tuple[bool, object, str | None]:
    return ValidationEngine().validate(
        ExtractionCandidate(value=value, confidence=1.0, provider="test"),
        validators,
    )


# ---------------------------------------------------------------------------
# monetary_amount
# ---------------------------------------------------------------------------


def _validate_amount(value: str) -> object:
    valid, normalized, error = _run(value, [{"type": "monetary_amount"}])
    assert valid is True
    assert error is None
    return normalized


def test_monetary_amount_accepts_decimal_comma() -> None:
    assert _validate_amount("1.304,48") == "1304.48"


def test_monetary_amount_accepts_decimal_point() -> None:
    assert _validate_amount("1304.48") == "1304.48"


def test_monetary_amount_accepts_english_thousands_separator() -> None:
    assert _validate_amount("1,304.48") == "1304.48"


def test_monetary_amount_strips_currency_symbol_and_whitespace() -> None:
    assert _validate_amount("EUR 1.234,56") == "1234.56"
    assert _validate_amount("  99,00 €  ") == "99.00"


def test_monetary_amount_quantizes_to_two_decimals() -> None:
    # Decimal.quantize sollte auf zwei Nachkommastellen runden
    assert _validate_amount("10") == "10.00"
    assert _validate_amount("10.1") == "10.10"


def test_monetary_amount_rejects_non_numeric_value() -> None:
    valid, _, error = _run("keine Zahl", [{"type": "monetary_amount"}])
    assert valid is False
    assert error


# ---------------------------------------------------------------------------
# IBAN
# ---------------------------------------------------------------------------

# Bekannter valider deutscher Test-IBAN aus der ISO-13616-Dokumentation.
VALID_IBAN_DE = "DE89370400440532013000"
VALID_IBAN_GB = "GB82WEST12345698765432"


def test_iban_accepts_valid_iban() -> None:
    valid, value, error = _run(VALID_IBAN_DE, [{"type": "iban"}])
    assert valid is True
    assert value == VALID_IBAN_DE
    assert error is None


def test_iban_normalizes_whitespace_and_lowercase() -> None:
    valid, value, error = _run("de89 3704 0044 0532 0130 00", [{"type": "iban"}])
    assert valid is True
    assert value == VALID_IBAN_DE
    assert error is None


def test_iban_accepts_second_country_code() -> None:
    valid, value, _ = _run(VALID_IBAN_GB, [{"type": "iban"}])
    assert valid is True
    assert value == VALID_IBAN_GB


def test_iban_rejects_bad_checksum() -> None:
    # Prüfziffer von 89 auf 90 verfälscht
    valid, _, error = _run("DE90370400440532013000", [{"type": "iban"}])
    assert valid is False
    assert error


def test_iban_rejects_too_short() -> None:
    valid, _, error = _run("DE8937040044", [{"type": "iban"}])
    assert valid is False
    assert error


def test_iban_rejects_too_long() -> None:
    valid, _, error = _run("DE89" + "3" * 40, [{"type": "iban"}])
    assert valid is False
    assert error


# ---------------------------------------------------------------------------
# vehicle_identification_number
# ---------------------------------------------------------------------------


def test_vin_rejects_short_string() -> None:
    valid, _, error = _run("ABC123", [{"type": "vehicle_identification_number"}])
    assert valid is False
    assert error


def test_vin_rejects_forbidden_letter_I() -> None:
    # Der Buchstabe "I" ist im VIN-Zeichensatz nicht zulässig
    valid, _, error = _run("1HGCM82633AI04352", [{"type": "vehicle_identification_number"}])
    assert valid is False
    assert error


# ---------------------------------------------------------------------------
# numeric_range
# ---------------------------------------------------------------------------


def test_numeric_range_accepts_value_within_bounds() -> None:
    valid, value, error = _run("42", [{"type": "numeric_range", "min": 0, "max": 100}])
    assert valid is True
    assert value == "42"
    assert error is None


def test_numeric_range_accepts_decimal_comma() -> None:
    valid, value, _ = _run("3,14", [{"type": "numeric_range", "min": 0, "max": 10}])
    assert valid is True
    assert Decimal(str(value)) == Decimal("3.14")


def test_numeric_range_rejects_below_min() -> None:
    valid, _, error = _run("-1", [{"type": "numeric_range", "min": 0, "max": 100}])
    assert valid is False
    assert error


def test_numeric_range_rejects_above_max() -> None:
    valid, _, error = _run("101", [{"type": "numeric_range", "min": 0, "max": 100}])
    assert valid is False
    assert error


def test_numeric_range_without_bounds_is_permissive() -> None:
    valid, value, _ = _run("999999", [{"type": "numeric_range"}])
    assert valid is True
    assert value == "999999"


def test_numeric_range_rejects_non_numeric() -> None:
    valid, _, error = _run("abc", [{"type": "numeric_range", "min": 0, "max": 10}])
    assert valid is False
    assert error


# ---------------------------------------------------------------------------
# not_empty / length / allowed_values
# ---------------------------------------------------------------------------


def test_not_empty_rejects_whitespace_only() -> None:
    valid, _, error = _run("   ", [{"type": "not_empty"}])
    assert valid is False
    assert error


def test_not_empty_accepts_content() -> None:
    valid, _, error = _run("Rechnung", [{"type": "not_empty"}])
    assert valid is True
    assert error is None


def test_length_enforces_min_and_max() -> None:
    validators: list[dict[str, object]] = [{"type": "length", "min": 3, "max": 5}]
    assert _run("abc", validators)[0] is True
    assert _run("abcdef", validators)[0] is False
    assert _run("ab", validators)[0] is False


def test_allowed_values_accepts_and_rejects() -> None:
    validators: list[dict[str, object]] = [{"type": "allowed_values", "values": ["A", "B", "C"]}]
    assert _run("A", validators)[0] is True
    assert _run("Z", validators)[0] is False


# ---------------------------------------------------------------------------
# date
# ---------------------------------------------------------------------------


def test_date_default_formats() -> None:
    valid, value, _ = _run("31.12.2026", [{"type": "date"}])
    assert valid is True
    assert value == "2026-12-31"


def test_date_custom_format() -> None:
    valid, value, _ = _run("12/31/2026", [{"type": "date", "formats": ["%m/%d/%Y"]}])
    assert valid is True
    assert value == "2026-12-31"


def test_date_rejects_unparseable() -> None:
    valid, _, error = _run("kein datum", [{"type": "date"}])
    assert valid is False
    assert error


# ---------------------------------------------------------------------------
# Chained validators
# ---------------------------------------------------------------------------


def test_validators_are_applied_in_order_and_pass_normalized_value() -> None:
    # Erst monetary_amount normalisiert "1.234,50" -> "1234.50",
    # anschließend prüft numeric_range gegen 0..2000 auf dem normalisierten Wert.
    valid, value, error = _run(
        "1.234,50 EUR",
        [
            {"type": "monetary_amount"},
            {"type": "numeric_range", "min": 0, "max": 2000},
        ],
    )
    assert valid is True
    assert error is None
    assert value == "1234.50"


def test_second_validator_rejects_normalized_value() -> None:
    valid, _, error = _run(
        "5.000,00 EUR",
        [
            {"type": "monetary_amount"},
            {"type": "numeric_range", "min": 0, "max": 2000},
        ],
    )
    assert valid is False
    assert error


@pytest.mark.parametrize(
    ("pattern", "value", "expected"),
    [
        (r"^[A-Z]{2}\d{4}$", "AB1234", True),
        (r"^[A-Z]{2}\d{4}$", "ab1234", False),
        (r"^[A-Z]{2}\d{4}$", "AB12345", False),
    ],
)
def test_required_pattern(pattern: str, value: str, expected: bool) -> None:
    valid, _, _ = _run(value, [{"type": "required_pattern", "pattern": pattern}])
    assert valid is expected
