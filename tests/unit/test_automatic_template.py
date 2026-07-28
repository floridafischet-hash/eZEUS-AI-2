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
    assert [candidate.value for candidate in amount] == ["480,76 €"]
