import pytest

from core.field_config.profiles import DELIVERY_NOTE_NUMBER, extraction_profile
from plugins.extraction.regex import RegexExtractionProvider


async def _values(text: str) -> list[str]:
    profile = extraction_profile(DELIVERY_NOTE_NUMBER)
    assert profile is not None
    candidates = await RegexExtractionProvider().extract(
        text,
        {"patterns": profile["patterns"]},
    )
    return [candidate.value for candidate in candidates]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Lieferscheinnummer 12345678", "12345678"),
        ("Lieferschein-Nr.: LI-2026/0042 Datum 04.11.2026", "LI-2026/0042"),
        ("Lieferschein 123456789", "123456789"),
        ("Lieferungsnummer LS_778899", "LS_778899"),
        ("Lieferung 778899", "778899"),
        ("LS 778899", "778899"),
        ("Lieferung 778899 Kunde 10042", "778899"),
        ("LS 778899", "778899"),
        ("Lieferauftrag 10042 LS-778899", "778899"),
        ("Kunde 100471 LI-123456789 Blatt 1", "123456789"),
        ("Lieferauftrag 888471 LI 2026-0042 Blatt 2", "2026-0042"),
        ("Lieferscheinnummer\n\n12345678", "12345678"),
        ("Lieferschetin 12345678", "12345678"),
        ("<td>Lieferscheinnummer</td><td>12345678</td>", "12345678"),
    ],
)
async def test_delivery_note_layouts(text: str, expected: str) -> None:
    assert await _values(text) == [expected]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "Lieferauftrag 888471",
        "Lieferanschrift Hauptstraße 12",
        "Bestellnummer 12345678",
        "Rechnungsnummer 12345678",
        "LI DE89370400440532013000",
        "Lieferscheinnummer AB",
        "Lieferscheinnummer 04.11.2026",
        "Lieferung vom 04.11.2026",
        "Unsere Lieferung erfolgt frei Haus",
        "Inhalt LS 778899 ohne Lieferkontext",
    ],
)
async def test_delivery_note_excludes_ambiguous_or_invalid_contexts(text: str) -> None:
    assert await _values(text) == []


@pytest.mark.asyncio
async def test_two_different_delivery_note_numbers_remain_ambiguous() -> None:
    values = await _values("Lieferscheinnummer 12345678\nLieferscheinnummer 87654321")

    assert values == ["12345678", "87654321"]
