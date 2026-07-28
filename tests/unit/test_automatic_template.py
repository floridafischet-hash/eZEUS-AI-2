from connectors.base.interface import ConnectorCustomField
from core.templates.automatic import config_from_custom_fields


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
