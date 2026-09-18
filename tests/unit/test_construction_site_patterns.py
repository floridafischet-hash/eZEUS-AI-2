import pytest

from core.field_config.service import STANDARD_PATTERNS
from plugins.extraction.regex import RegexExtractionProvider


async def _extract(text: str) -> list[object]:
    candidates = await RegexExtractionProvider().extract(
        text,
        {"patterns": STANDARD_PATTERNS["construction_site_number"]},
    )
    return [candidate.value for candidate in candidates]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Lieferanschrift: Grundschule\n# 26051\nRaakamp 6", ["26051"]),
        ("Ihre Referenz: #25180", ["25180"]),
        ("BV- 25095, Drochtersen", ["25095"]),
        ("BV. 2513, Stade", ["2513"]),
        (
            "Lieferdatum LS-Nr Bezeichnung Menge Rabatt Einzelpreis Gesamt\n\n"
            "26070 Kinderkrippe Mäusehöhle, Gnarrenburg\n"
            "Lieferwerk: Bremervörde",
            ["26070"],
        ),
    ],
)
async def test_construction_site_patterns_extract_supported_layouts(
    text: str, expected: list[str]
) -> None:
    assert await _extract(text) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "Ihre Referenz: BV. Buck, Jütlandstraße",
        "Lieferanschrift: BV. Behrmann\n#\nPotsdamer Weg 4",
        "Ihre Referenz: BV OHZ Benjamin Klose",
    ],
)
async def test_construction_site_patterns_reject_names(text: str) -> None:
    assert await _extract(text) == []
