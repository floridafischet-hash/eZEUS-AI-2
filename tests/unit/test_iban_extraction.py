import pytest
import regex

from connectors.base.interface import ConnectorCustomField
from core.field_config.profiles import EXTRACTION_PROFILES
from core.field_config.service import STANDARD_PATTERNS
from core.templates.automatic import config_from_custom_fields
from core.validation.engine import ValidationEngine
from plugins.base.interfaces import ExtractionCandidate
from plugins.extraction.regex import RegexExtractionProvider


async def _valid_ibans(text: str) -> list[str]:
    candidates = await RegexExtractionProvider().extract(
        text,
        {"patterns": EXTRACTION_PROFILES["iban"]["patterns"]},
    )
    validator = ValidationEngine()
    valid: list[str] = []
    for candidate in candidates:
        accepted, normalized, _ = validator.validate(candidate, [{"type": "iban"}])
        if accepted:
            valid.append(str(normalized))
    return valid


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("IBAN: DE89 3704 0044 0532 0130 00", "DE89370400440532013000"),
        ("IBAN-Nr.\u00a0AT61\u00a01904\u00a03002\u00a03457\u00a03201", "AT611904300234573201"),
        ("IBAN/BIC | CH93 0076 2011 6238 5295 7 | POFICHBEXXX", "CH9300762011623852957"),
        ("Kontonummer (IBAN): NL91 ABNA 0417 1643 00", "NL91ABNA0417164300"),
        ("IBAN: gb82 west 1234 5698 7654 32", "GB82WEST12345698765432"),
        ("IBAN: DE89370400440532013000 BIC: COBADEFFXXX", "DE89370400440532013000"),
        ("Bankverbindung\nDE89 3704 0044 0532 0130 00", "DE89370400440532013000"),
        ("| IBAN | DE89 3704 0044 0532 0130 00 |", "DE89370400440532013000"),
        (
            "<table><tr><td>IBAN</td><td>DE89 3704 0044 0532 0130 00</td>"
            "<td>BIC</td><td>COBADEFFXXX</td></tr></table>",
            "DE89370400440532013000",
        ),
        ("Rechnung Seite 1\fIBAN: DE89 3704 0044 0532 0130 00", "DE89370400440532013000"),
    ],
)
async def test_iban_profile_extracts_and_normalizes_supported_layouts(
    text: str, expected: str
) -> None:
    assert await _valid_ibans(text) == [expected]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "IBAN: DE90 3704 0044 0532 0130 00",
        "IBAN: DE89 3704 0044 0532",
        "IBAN: DE89 3704 0044 0532 0130 001",
        "IBAN:",
        "Kontonummer: 370400440532013000",
        "Rechnungsnummer: 89370400440532013000",
        "Lastschrift von Ihrem Konto, IBAN: DE89 3704 0044 0532 0130 00",
        "SEPA-Mandat\nIBAN: DE89 3704 0044 0532 0130 00",
    ],
)
async def test_iban_profile_rejects_invalid_or_payer_values(text: str) -> None:
    assert await _valid_ibans(text) == []


@pytest.mark.asyncio
async def test_bic_and_bank_name_never_run_into_iban() -> None:
    text = "IBAN: DE89 3704 0044 0532 0130 00 BIC: COBADEFFXXX"
    candidates = await RegexExtractionProvider().extract(
        text, {"patterns": EXTRACTION_PROFILES["iban"]["patterns"]}
    )
    assert [candidate.value for candidate in candidates] == ["DE89 3704 0044 0532 0130 00"]


@pytest.mark.asyncio
async def test_iban_profile_keeps_multiple_valid_values_ambiguous() -> None:
    assert EXTRACTION_PROFILES["iban"]["selection_strategy"] == "unique"
    values = await _valid_ibans("IBAN: DE89 3704 0044 0532 0130 00\nIBAN: AT61 1904 3002 3457 3201")
    assert values == ["DE89370400440532013000", "AT611904300234573201"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field_name",
    ["Rechnungsnummer", "Rechnungsbetrag", "Kundennummer", "Baustellennummer"],
)
async def test_existing_field_patterns_do_not_extract_iban_fragments(field_name: str) -> None:
    if field_name in {"Rechnungsnummer", "Rechnungsbetrag"}:
        field = ConnectorCustomField(
            "99", field_name, "monetary" if field_name == "Rechnungsbetrag" else "string"
        )
        config = config_from_custom_fields([field])
        assert config is not None
        patterns = (
            next(iter(config.fields.values())).providers[0].model_dump(exclude={"type"})["patterns"]
        )
    else:
        key = "customer_number" if field_name == "Kundennummer" else "construction_site_number"
        patterns = STANDARD_PATTERNS[key]
    candidates = await RegexExtractionProvider().extract(
        "Bankverbindung\nIBAN: DE89 3704 0044 0532 0130 00\nBIC: COBADEFFXXX",
        {"patterns": patterns},
    )
    assert candidates == []


def test_profile_patterns_use_capture_group_one() -> None:
    assert STANDARD_PATTERNS.get("iban") is None
    for pattern in EXTRACTION_PROFILES["iban"]["patterns"]:
        assert regex.compile(pattern).groups == 1
    candidate = ExtractionCandidate(
        value="DE89 3704 0044 0532 0130 00", confidence=0.95, provider="regex"
    )
    valid, normalized, _ = ValidationEngine().validate(candidate, [{"type": "iban"}])
    assert valid is True
    assert normalized == "DE89370400440532013000"
