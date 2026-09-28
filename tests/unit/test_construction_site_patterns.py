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
        ("KST 26008", ["26008"]),
        ("KST: 260012", ["260012"]),
        ("KST-Nr. 25043", ["25043"]),
        ("Kostenstelle KST Nummer 25090", ["25090"]),
        ("Projekt / KST 25139, Stade", ["25139"]),
        ("BV. 26078, Oerel", ["26078"]),
        ("BV. 26073, Lamstedt", ["26073"]),
        ("Bstr. Nr. 25139", ["25139"]),
        ("BV-Nr.: 25412", ["25412"]),
        ("BV 99999", ["99999"]),
        ("Kostenstelle 24980", ["24980"]),
        ("Baustelle: 26054", ["26054"]),
        ("Baustellennummer:# 26082, Selsingen", ["26082"]),
        ("Kundenauftragsnr. : 25139", ["25139"]),
        ("Lieferanschrift: Grundschule\n# 26054\nHauptstraße 1", ["26054"]),
        (
            "Kunden-Nr.: 1000101\n"
            "Baustelle : 18570 25113 Finanzamt, Am Staatsarchiv, Stade\n"
            "Artikel Menge ME Preis Gesamt",
            ["25113"],
        ),
        ("Baustelle: 18570 24000 Gültige Untergrenze", ["24000"]),
        ("Baustelle: 18570 99999 Gültige Obergrenze", ["99999"]),
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
        "Baustelle: 18570 23999 Unterhalb des gültigen Bereichs",
        "Baustelle: 18570 100000 Oberhalb des gültigen Bereichs",
        "BV. 2513, Stade",
        "BV 23999",
        "KST 1234",
        "KST 1234567",
        "KST Baustelle Stade",
        "KW 26",
        "21682 Stade",
        "Telefon 04761 26054",
        "8 Stunden 26054",
        "Artikel-Nr. 26054",
        "Auftrags-Nr. 260541234",
    ],
)
async def test_construction_site_patterns_reject_names(text: str) -> None:
    assert await _extract(text) == []
