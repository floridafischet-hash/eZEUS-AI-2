import pytest
from pydantic import ValidationError

from core.templates.schema import TemplateConfig


def test_template_rejects_unknown_provider() -> None:
    with pytest.raises(ValidationError):
        TemplateConfig.model_validate(
            {
                "fields": {
                    "invoice": {
                        "target_field_id": 14,
                        "providers": [{"type": "unknown"}],
                    }
                }
            }
        )


def test_minimal_template_is_valid() -> None:
    template = TemplateConfig.model_validate(
        {
            "fields": {
                "invoice": {
                    "target_field_id": 14,
                    "providers": [{"type": "regex", "patterns": ["Invoice: (\\w+)"]}],
                    "validators": [{"type": "not_empty"}],
                }
            }
        }
    )
    assert template.fields["invoice"].target_field_id == 14


def test_ollama_template_is_valid() -> None:
    template = TemplateConfig.model_validate(
        {
            "fields": {
                "invoice_number": {
                    "target_field_id": 1,
                    "providers": [
                        {
                            "type": "ollama",
                            "field_name": "Rechnungsnummer",
                            "value_hint": "Text",
                        }
                    ],
                }
            }
        }
    )
    assert template.fields["invoice_number"].providers[0].type == "ollama"
