from core.validation.engine import ValidationEngine
from plugins.base.interfaces import ExtractionCandidate


def test_validation_normalizes_amount() -> None:
    accepted, value, reason = ValidationEngine().validate(
        ExtractionCandidate("1.234,56 EUR", 0.9, "regex"),
        [{"type": "monetary_amount", "currency": "EUR"}],
    )
    assert accepted is True
    assert value == "1234.56"
    assert reason is None


def test_validation_rejects_pattern_mismatch() -> None:
    accepted, _, reason = ValidationEngine().validate(
        ExtractionCandidate("invalid value", 0.9, "regex"),
        [{"type": "required_pattern", "pattern": r"^[A-Z0-9-]+$"}],
    )
    assert accepted is False
    assert reason
