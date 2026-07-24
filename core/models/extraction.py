from uuid import UUID

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExtractionResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "extraction_results"

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    field_key: Mapped[str] = mapped_column(String(255))
    target_field_id: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(128))
    raw_value: Mapped[object] = mapped_column(JSON)
    normalized_value: Mapped[object | None] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_status: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    bounding_box: Mapped[dict[str, object] | None] = mapped_column(JSON)
    runtime_ms: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
