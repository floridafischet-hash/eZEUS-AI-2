from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OCRArtifact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ocr_artifacts"

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(128))
    model: Mapped[str | None] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text)
    cleaned_text: Mapped[str | None] = mapped_column(Text)
    cleanup_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
