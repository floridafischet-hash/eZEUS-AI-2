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
