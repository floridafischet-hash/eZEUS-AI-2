from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from core.models.enums import JobPhase, PhaseStatus


class JobPhaseEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_phases"

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    phase: Mapped[JobPhase] = mapped_column(Enum(JobPhase))
    status: Mapped[PhaseStatus] = mapped_column(Enum(PhaseStatus))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
