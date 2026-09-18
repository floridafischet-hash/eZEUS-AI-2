import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DOCUMENT_ID_PATTERN = re.compile(r"^[1-9][0-9]{0,11}$")
_CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


class PaperlessWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_id: str
    event_id: str | None = Field(default=None, max_length=200)

    @field_validator("document_id", mode="before")
    @classmethod
    def validate_document_id(cls, value: object) -> str:
        if isinstance(value, bool):
            raise ValueError("document_id must be a positive integer")
        if isinstance(value, int):
            text = str(value)
        elif isinstance(value, str):
            text = value.strip()
        else:
            raise ValueError("document_id must be a positive integer")
        if not _DOCUMENT_ID_PATTERN.fullmatch(text):
            raise ValueError("document_id must be a positive integer")
        return text

    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if _CONTROL_CHARACTER_PATTERN.search(value):
            raise ValueError("event_id must not contain control characters")
        return value
