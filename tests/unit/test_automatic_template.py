import pytest

from connectors.base.interface import ConnectorCustomField
from core.templates.automatic import config_from_custom_fields
from plugins.extraction.regex import RegexExtractionProvider


def test_config_uses_live_paperless_custom_field_ids() -> None:
    config = config_from_custom_fields(
        [
            ConnectorCustomField("93", "Rechnungsnummer", "string"),
            ConnectorCustomField("95", "Rechnungsbetrag", "monetary"),
            ConnectorCustomField("97", "Geprüft von Eins", "boolean"),
        ]
    )

    assert config is not None
    assert config.fields["invoice_number"].target_field_id == 93
    assert config.fields["invoice_amount"].target_field_id == 95
    assert config.fields["invoice_number"].providers[0].type == "regex"
    assert len(config.fields["invoice_number"].providers) == 1
    assert config.fields["invoice_number"].selection_strategy == "first"
    assert config.fields["invoice_amount"].selection_strategy == "highest"
    assert "Geprüft von Eins" not in config.fields


def test_config_normalizes_field_names_and_ignores_unknown_fields() -> None:
    config = config_from_custom_fields(
        [
            ConnectorCustomField("12", "Lieferschein-Nummer", "string"),
            ConnectorCustomField("13", "Interne Notiz", "string"),
        ]
    )

    assert config is not None
    assert list(config.fields) == ["delivery_note_number"]
    assert config.fields["delivery_note_number"].target_field_id == 12


def test_config_is_absent_without_supported_fields() -> None:
    assert (
        config_from_custom_fields([ConnectorCustomField("13", "Interne Notiz", "string")]) is None
    )


@pytest.mark.asyncio
async def test_invoice_patterns_extract_common_german_labels() -> None:
    config = config_from_custom_fields(
        [
            ConnectorCustomField("93", "Rechnungsnummer", "string"),
            ConnectorCustomField("95", "Rechnungsbetrag", "monetary"),
        ]
    )
    assert config is not None
    text = "Lieferung vom 04.01.2025 Rechnung-Nr. 5007\nBrutto-Rechnungsbetrag 480,76 €"

    number_provider = config.fields["invoice_number"].providers[0]
    amount_provider = config.fields["invoice_amount"].providers[0]
    number = await RegexExtractionProvider().extract(
        text, number_provider.model_dump(exclude={"type"})
    )
    amount = await RegexExtractionProvider().extract(
        text, amount_provider.model_dump(exclude={"type"})
    )

    assert [candidate.value for candidate in number] == ["5007"]
    assert [candidate.value for candidate in amount] == ["480,76"]


@pytest.mark.asyncio
async def test_customer_number_is_never_used_as_invoice_number() -> None:
    config = config_from_custom_fields([ConnectorCustomField("93", "Rechnungsnummer", "string")])
    assert config is not None
    provider = config.fields["invoice_number"].providers[0]

    candidates = await RegexExtractionProvider().extract(
        "Kundennummer: KD-8842", provider.model_dump(exclude={"type"})
    )

    assert candidates == []


@pytest.mark.asyncio
async def test_bv_number_is_used_when_customer_number_is_also_present() -> None:
    config = config_from_custom_fields([ConnectorCustomField("93", "Rechnungsnummer", "string")])
    assert config is not None
    provider = config.fields["invoice_number"].providers[0]

    candidates = await RegexExtractionProvider().extract(
        "Kundennummer: KD-8842\nBV-Nr.: 25142",
        provider.model_dump(exclude={"type"}),
    )

    assert [candidate.value for candidate in candidates] == ["25142"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label",
    ["BV", "BV-Nr.", "BV Nummer", "Baustellen-Nr.", "Baustellennummer"],
)
async def test_bv_number_accepts_supported_labels(label: str) -> None:
    config = config_from_custom_fields([ConnectorCustomField("93", "Rechnungsnummer", "string")])
    assert config is not None
    provider = config.fields["invoice_number"].providers[0]

    candidates = await RegexExtractionProvider().extract(
        f"{label}: 26123", provider.model_dump(exclude={"type"})
    )

    assert [candidate.value for candidate in candidates] == ["26123"]


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["23123", "27123", "2412", "251234"])
async def test_bv_number_rejects_invalid_number_ranges_and_lengths(invalid: str) -> None:
    config = config_from_custom_fields([ConnectorCustomField("93", "Rechnungsnummer", "string")])
    assert config is not None
    provider = config.fields["invoice_number"].providers[0]

    candidates = await RegexExtractionProvider().extract(
        f"BV-Nr.: {invalid}", provider.model_dump(exclude={"type"})
    )

    assert candidates == []


@pytest.mark.asyncio
async def test_invoice_number_is_used_when_customer_number_is_also_present() -> None:
    config = config_from_custom_fields([ConnectorCustomField("93", "Rechnungsnummer", "string")])
    assert config is not None
    provider = config.fields["invoice_number"].providers[0]

    candidates = await RegexExtractionProvider().extract(
        "Kundennummer: KD-8842\nRechnungsnummer: RE-2026-19",
        provider.model_dump(exclude={"type"}),
    )

    assert [candidate.value for candidate in candidates] == ["RE-2026-19"]


@pytest.mark.asyncio
async def test_invoice_number_precedes_bv_while_customer_number_is_ignored() -> None:
    config = config_from_custom_fields([ConnectorCustomField("93", "Rechnungsnummer", "string")])
    assert config is not None
    provider = config.fields["invoice_number"].providers[0]

    candidates = await RegexExtractionProvider().extract(
        "Kundennummer: KD-8842\nBV: 24123\nRechnungsnummer: RE-2026-19",
        provider.model_dump(exclude={"type"}),
    )

    assert [candidate.value for candidate in candidates] == [
        "RE-2026-19",
        "24123",
    ]


@pytest.mark.asyncio
async def test_invoice_number_is_extracted_from_collapsed_ocr_columns() -> None:
    config = config_from_custom_fields([ConnectorCustomField("93", "Rechnungsnummer", "string")])
    assert config is not None
    provider = config.fields["invoice_number"].providers[0]
    text = (
        "Rechnung\n"
        "Datum: Rechnungsnr.: Kunden-Nr.:\n"
        "22.07.2026 5799588 2011452\n"
        "\n"
        "Zahlungsdatum: 21.08.2026"
    )

    candidates = await RegexExtractionProvider().extract(
        text, provider.model_dump(exclude={"type"})
    )

    assert [candidate.value for candidate in candidates] == ["5799588"]


@pytest.mark.asyncio
async def test_document_3555_prefers_invoice_number_and_never_customer_number() -> None:
    config = config_from_custom_fields([ConnectorCustomField("93", "Rechnungsnummer", "string")])
    assert config is not None
    provider = config.fields["invoice_number"].providers[0]
    text = (
        "Rechnung\n"
        "Datum: Rechnungsnr.: Kunden-Nr.:\n"
        "22.07.2026 5799588 2011452\n"
        "BV 25164, Hechthausen, Marktplatz\n"
    )

    candidates = await RegexExtractionProvider().extract(
        text, provider.model_dump(exclude={"type"})
    )

    assert [candidate.value for candidate in candidates] == ["5799588", "25164"]
    assert "2011452" not in [candidate.value for candidate in candidates]
    assert "Kunden-Nr." not in [candidate.value for candidate in candidates]


@pytest.mark.asyncio
async def test_invoice_label_does_not_consume_value_from_next_ocr_line() -> None:
    config = config_from_custom_fields([ConnectorCustomField("93", "Rechnungsnummer", "string")])
    assert config is not None
    provider = config.fields["invoice_number"].providers[0]

    candidates = await RegexExtractionProvider().extract(
        "Rechnungsnr.:\n5799588", provider.model_dump(exclude={"type"})
    )

    assert candidates == []


@pytest.mark.asyncio
async def test_document_371_rejects_header_and_uses_actual_invoice_number() -> None:
    config = config_from_custom_fields([ConnectorCustomField("93", "Rechnungsnummer", "string")])
    assert config is not None
    provider = config.fields["invoice_number"].providers[0]
    text = (
        "Rechnungs-Nr.\n"
        "Rechnungsdatum\n"
        "Lieferdatum\n"
        "\n"
        "1001\n"
        "30.11.2025\n"
        "30.11.2025\n"
        "\n"
        "30.11.2025\n"
        "Rechnung Nr. 1001\n"
    )

    candidates = await RegexExtractionProvider().extract(
        text, provider.model_dump(exclude={"type"})
    )

    assert [candidate.value for candidate in candidates] == ["1001"]


@pytest.mark.asyncio
async def test_invoice_number_must_contain_a_digit() -> None:
    config = config_from_custom_fields([ConnectorCustomField("93", "Rechnungsnummer", "string")])
    assert config is not None
    provider = config.fields["invoice_number"].providers[0]

    candidates = await RegexExtractionProvider().extract(
        "Rechnungsnummer: Rechnungsdatum",
        provider.model_dump(exclude={"type"}),
    )

    assert candidates == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Rechnung R1803", "R1803"),
        ("Rechnung 184084", "184084"),
        ("Bon-Nr.: 300007321", "300007321"),
    ],
)
async def test_additional_invoice_identifier_formats(text: str, expected: str) -> None:
    config = config_from_custom_fields([ConnectorCustomField("93", "Rechnungsnummer", "string")])
    assert config is not None
    provider = config.fields["invoice_number"].providers[0]

    candidates = await RegexExtractionProvider().extract(
        text, provider.model_dump(exclude={"type"})
    )

    assert [candidate.value for candidate in candidates] == [expected]


@pytest.mark.asyncio
async def test_plain_invoice_heading_is_not_an_identifier() -> None:
    config = config_from_custom_fields([ConnectorCustomField("93", "Rechnungsnummer", "string")])
    assert config is not None
    provider = config.fields["invoice_number"].providers[0]

    candidates = await RegexExtractionProvider().extract(
        "Rechnung\nRechnungsdatum: 15.01.2015",
        provider.model_dump(exclude={"type"}),
    )

    assert candidates == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Nettosumme 1.357,00 €\nGesamtsumme 1.614,83 €", "1.614,83"),
        ("Nettosumme € 899,99\nGesamtsumme € 1.070,99", "1.070,99"),
        ("Rechnungswert (brutto) 1.233,88 €", "1.233,88"),
        (
            "Netto-Rechnungsbetrag 287,80 €\nBrutto-Rechnungsbetrag 342,48 €",
            "342,48",
        ),
        (
            "MwSt Netto MwSt Summe\n19% 19.576,35 € 3.719,51 € 23.295,86 €\n"
            "Gesamt 19.576,35 € 23.295,86 €",
            "23.295,86",
        ),
        ("19.00 % MwSt: 208.28 EUR\nGesamtsumme: 1304.48 EUR", "1304.48"),
        ("Fälligkeitsdatum: 27/02/2025 Summe: 6,66", "6,66"),
        ("ZWISCHENSUMME netto 3.455,00 €\nENDSUMME brutto 4.111,45 €", "4.111,45"),
        ("ENDSUMME brutto\n3.867,50 €", "3.867,50"),
        ("Gesamtbetrag brutto: 28.441,00 EUR", "28.441,00"),
        (
            "Zahlungsbedingung Zahlbar sofort rein netto. Netto 320,70 €\n"
            "Bindung Es gelten die AGB des Lieferanten Brutto 381,63 €",
            "381,63",
        ),
        ("Artikel: 2 Total: 98,70\nBargeld 98,70€", "98,70"),
    ],
)
async def test_invoice_amount_patterns_select_only_gross_total(text: str, expected: str) -> None:
    config = config_from_custom_fields([ConnectorCustomField("95", "Rechnungsbetrag", "monetary")])
    assert config is not None
    provider = config.fields["invoice_amount"].providers[0]

    candidates = await RegexExtractionProvider().extract(
        text, provider.model_dump(exclude={"type"})
    )

    assert [candidate.value for candidate in candidates] == [expected]


@pytest.mark.asyncio
async def test_invoice_amount_patterns_collect_totals_from_all_pages() -> None:
    config = config_from_custom_fields([ConnectorCustomField("95", "Rechnungsbetrag", "monetary")])
    assert config is not None
    provider = config.fields["invoice_amount"].providers[0]
    text = (
        "Seite 1 von 3\nZwischensumme 100,00 EUR\nÜbertrag: 119,00 EUR\n"
        "\fSeite 2 von 3\nÜbertrag: 250,00 Euro\n"
        "\fSeite 3 von 3\nGesamt 287,80 EUR 342,48 EUR"
    )

    candidates = await RegexExtractionProvider().extract(
        text, provider.model_dump(exclude={"type"})
    )

    assert [candidate.value for candidate in candidates] == [
        "342,48",
        "119,00",
        "250,00",
    ]
