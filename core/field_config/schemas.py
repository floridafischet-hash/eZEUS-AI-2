import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

FieldType = Literal["text", "number", "money", "date", "boolean", "select", "textarea"]
FIELD_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


class FieldConfigurationInput(BaseModel):
    field_key: str | None = None
    label: str = Field(min_length=1, max_length=128)
    field_type: FieldType
    sort_order: int = Field(ge=0, le=100_000)
    enabled: bool = True
    required: bool = False
    ocr_enabled: bool = True
    ai_enabled: bool = False
    external_field_id: str | None = Field(default=None, max_length=255)
    options: list[str] = Field(default_factory=list, max_length=100)
    extraction_instructions: str | None = Field(default=None, max_length=2000)

    @field_validator("field_key")
    @classmethod
    def validate_key(cls, value: str | None) -> str | None:
        if value is not None and not FIELD_KEY_PATTERN.fullmatch(value):
            raise ValueError("field_key must contain lowercase letters, numbers or underscores")
        return value

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if any(character in normalized for character in "<>{}"):
            raise ValueError("label contains unsupported characters")
        return normalized

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: list[str]) -> list[str]:
        normalized = [" ".join(item.split()) for item in value]
        if any(not item or len(item) > 255 for item in normalized):
            raise ValueError("selection options must contain 1 to 255 characters")
        if len(set(normalized)) != len(normalized):
            raise ValueError("selection options must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_type_options(self) -> "FieldConfigurationInput":
        if self.field_type == "select" and not self.options:
            raise ValueError("selection fields require at least one option")
        if self.field_type != "select" and self.options:
            raise ValueError("options are only supported for selection fields")
        if self.required and not self.enabled:
            raise ValueError("disabled fields cannot be required")
        return self


class FieldConfigurationSave(BaseModel):
    fields: list[FieldConfigurationInput] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_keys(self) -> "FieldConfigurationSave":
        keys = [field.field_key for field in self.fields if field.field_key is not None]
        if len(keys) != len(set(keys)):
            raise ValueError("field keys must be unique")
        return self
