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
async def test_customer_number_is_invoice_number_fallback() -> None:
    config = config_from_custom_fields([ConnectorCustomField("93", "Rechnungsnummer", "string")])
    assert config is not None
    provider = config.fields["invoice_number"].providers[0]

    candidates = await RegexExtractionProvider().extract(
        "Kundennummer: KD-8842", provider.model_dump(exclude={"type"})
    )

    assert [candidate.value for candidate in candidates] == ["KD-8842"]


@pytest.mark.asyncio
async def test_invoice_number_candidate_precedes_customer_number() -> None:
    config = config_from_custom_fields([ConnectorCustomField("93", "Rechnungsnummer", "string")])
    assert config is not None
    provider = config.fields["invoice_number"].providers[0]

    candidates = await RegexExtractionProvider().extract(
        "Kundennummer: KD-8842\nRechnungsnummer: RE-2026-19",
        provider.model_dump(exclude={"type"}),
    )

    assert [candidate.value for candidate in candidates] == [
        "RE-2026-19",
        "KD-8842",
    ]


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
