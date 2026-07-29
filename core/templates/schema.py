from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

KNOWN_PROVIDERS = {"regex", "keyword", "ollama"}
KNOWN_VALIDATORS = {
    "not_empty",
    "required_pattern",
    "date",
    "monetary_amount",
    "iban",
    "allowed_values",
    "length",
    "numeric_range",
}


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str

    @field_validator("type")
    @classmethod
    def known_provider(cls, value: str) -> str:
        if value not in KNOWN_PROVIDERS:
            raise ValueError(f"Unknown extraction provider: {value}")
        return value


class ValidatorConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str

    @field_validator("type")
    @classmethod
    def known_validator(cls, value: str) -> str:
        if value not in KNOWN_VALIDATORS:
            raise ValueError(f"Unknown validator: {value}")
        return value


class FieldConfig(BaseModel):
    target_field_id: int | None = None
    providers: list[ProviderConfig] = Field(default_factory=list)
    validators: list[ValidatorConfig] = Field(default_factory=list)
    minimum_confidence: float = Field(default=0.8, ge=0, le=1)
    selection_strategy: Literal["unique", "first", "highest"] = "unique"
    required: bool = True


class TemplateConfig(BaseModel):
    fields: dict[str, FieldConfig] = Field(min_length=1)
