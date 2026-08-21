import pytest

from plugins.extraction.keyword import KeywordExtractionProvider
from plugins.extraction.regex import RegexExtractionProvider


@pytest.mark.asyncio
async def test_regex_uses_capture_group_and_multiple_patterns() -> None:
    candidates = await RegexExtractionProvider().extract(
        "Rechnungsnummer: R-4711\nInvoice: EN-9",
        {"patterns": [r"Rechnungsnummer:\s*(\S+)", r"Invoice:\s*(\S+)"]},
    )
    assert [candidate.value for candidate in candidates] == ["R-4711", "EN-9"]


@pytest.mark.asyncio
async def test_regex_interrupts_a_running_catastrophic_pattern() -> None:
    with pytest.raises(TimeoutError, match="hard time limit"):
        await RegexExtractionProvider().extract(
            "a" * 20_000 + "!",
            {"pattern": r"(a|aa)+$", "timeout_ms": 5},
        )


@pytest.mark.asyncio
async def test_keyword_returns_every_occurrence_with_context() -> None:
    candidates = await KeywordExtractionProvider().extract(
        "Start\nGesamtbetrag\n10,00 EUR\nText\nZahlbetrag\n20,00 EUR",
        {
            "keywords": ["Gesamtbetrag"],
            "synonyms": ["Zahlbetrag"],
            "context_before": 0,
            "context_after": 1,
        },
    )
    assert len(candidates) == 2
    assert "10,00 EUR" in candidates[0].value
    assert "20,00 EUR" in candidates[1].value
