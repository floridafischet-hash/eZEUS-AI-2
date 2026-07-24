from pydantic import BaseModel, Field


class PaperlessWebhookPayload(BaseModel):
    document_id: int | str
    event_id: str | None = None
    document: dict[str, object] = Field(default_factory=dict)
