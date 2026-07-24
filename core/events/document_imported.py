from pydantic import BaseModel, Field


class DocumentImportedEvent(BaseModel):
    connector: str = "paperless"
    external_document_id: str
    source_event_id: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
