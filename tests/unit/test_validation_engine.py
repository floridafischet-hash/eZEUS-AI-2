from core.validation.engine import ValidationEngine
from plugins.base.interfaces import ExtractionCandidate


def _validate_amount(value: str) -> object:
    valid, normalized, error = ValidationEngine().validate(
        ExtractionCandidate(value=value, confidence=1.0, provider="test"),
        [{"type": "monetary_amount"}],
    )
    assert valid is True
    assert error is None
    return normalized


def test_monetary_amount_accepts_decimal_comma() -> None:
    assert _validate_amount("1.304,48") == "1304.48"


def test_monetary_amount_accepts_decimal_point() -> None:
    assert _validate_amount("1304.48") == "1304.48"


def test_monetary_amount_accepts_english_thousands_separator() -> None:
    assert _validate_amount("1,304.48") == "1304.48"
