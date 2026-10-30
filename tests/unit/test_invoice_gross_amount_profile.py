from decimal import Decimal

import pytest

from core.field_config.profiles import EXTRACTION_PROFILES, INVOICE_GROSS_AMOUNT
from core.validation.engine import ValidationEngine
from plugins.base.interfaces import ExtractionCandidate
from plugins.extraction.regex import RegexExtractionProvider


async def _selected_amount(text: str) -> str | None:
    profile = EXTRACTION_PROFILES[INVOICE_GROSS_AMOUNT]
    candidates = await RegexExtractionProvider().extract(
        text,
        {
            "patterns": profile["patterns"],
            "negative_context_patterns": profile["negative_context_patterns"],
            "negate_on_negative_context": profile["negate_on_negative_context"],
        },
    )
    validator = ValidationEngine()
    valid: list[tuple[int, str]] = []
    for candidate in candidates:
        accepted, normalized, _ = validator.validate(candidate, profile["validators"])
        if accepted:
            valid.append((int(str(candidate.metadata["pattern_index"])), str(normalized)))
    if not valid:
        return None
    priority = min(item[0] for item in valid)
    return max(
        (item[1] for item in valid if item[0] == priority),
        key=lambda value: abs(Decimal(value)),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Gesamtsumme 4.192,23 EUR\nSkonto 83,84 EUR\nSumme 28.462,00 EUR", "4192.23"),
        ("Gesamtsumme 4.529,84 EUR\nSkonto 90,60 EUR\nSumme 32.908,00 EUR", "4529.84"),
        ("Gesamtsumme 3.363,00 EUR\n2 % Skonto 67,26 EUR", "3363.00"),
        ("Summe 4.680,00 EUR", "4680.00"),
        ("Total EUR inkl. MwSt. 1.304,48", "1304.48"),
        ("Gesamtbetrag\nEUR 642,17", "642.17"),
        ("Grand Total: USD 1,234.56", "1234.56"),
        ("Brutto in EUR 1.825,40", "1825.40"),
        ("Zahlungsbetrag: 812,45 EUR Zahlungsziel 14 Tage", "812.45"),
        ("30 Tage ohne Abzug bis 31.12.2026 712,81 EUR", "712.81"),
        (
            "Nettowarenwert MwSt MwSt Betrag Total inkl. MwSt.\n1.000,00 19 % 190,00 1.190,00 EUR",
            "1190.00",
        ),
        (
            "Nettobetrag MwSt. 19 % Zu zahlender Betrag\nEUR 1.000,00 EUR 190,00 EUR 1.190,00 EUR",
            "1190.00",
        ),
    ],
)
async def test_invoice_gross_amount_profile_prefers_gross_total(
    text: str, expected: str | None
) -> None:
    assert await _selected_amount(text) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Gutschrift\nErstattungsbetrag 2.002,77 EUR", "-2002.77"),
        ("Stornorechnung\nGesamtsumme 3.014,27 EUR", "-3014.27"),
        ("Erstattungsbetrag −4.432,00 EUR", "-4432.00"),
        ("Gutschriftbetrag 211,82 EUR", "-211.82"),
    ],
)
async def test_invoice_gross_amount_profile_preserves_credit_sign(text: str, expected: str) -> None:
    assert await _selected_amount(text) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "Netto 62,00 EUR\nUSt 19 % 11,78 EUR",
        "Zwischensumme 500,00 EUR",
        "Bereits gezahlt 100,00 EUR",
        "Verbleibende Restzahlung 900,00 EUR",
        "2 % Skonto 67,26 EUR",
        "Rechnungsbetrag 31 10 2026 2,00 EUR",
    ],
)
async def test_invoice_gross_amount_profile_rejects_non_gross_amounts(text: str) -> None:
    assert await _selected_amount(text) is None


def test_monetary_validator_accepts_unicode_minus_and_parentheses() -> None:
    validator = ValidationEngine()
    for raw, expected in [("−42,00", "-42.00"), ("(42,00)", "-42.00")]:
        accepted, normalized, reason = validator.validate(
            ExtractionCandidate(value=raw, confidence=1.0, provider="test"),
            [{"type": "monetary_amount"}],
        )
        assert accepted, reason
        assert Decimal(str(normalized)) == Decimal(expected)
