from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from core.models.enums import JobPhase, JobPriority, JobStatus


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index(
            "uq_active_job_document",
            "document_id",
            unique=True,
            postgresql_where=text("status IN ('RECEIVED', 'QUEUED', 'RUNNING', 'RETRY_WAITING')"),
            sqlite_where=text("status IN ('RECEIVED', 'QUEUED', 'RUNNING', 'RETRY_WAITING')"),
        ),
    )

    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.RECEIVED)
    phase: Mapped[JobPhase | None] = mapped_column(Enum(JobPhase), nullable=True)
    priority: Mapped[JobPriority] = mapped_column(Enum(JobPriority), default=JobPriority.NORMAL)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    error_type: Mapped[str | None] = mapped_column(String(255))
    worker_id: Mapped[str | None] = mapped_column(String(255))
    selected_template_id: Mapped[UUID | None] = mapped_column(ForeignKey("templates.id"))
    selected_template_version: Mapped[int | None] = mapped_column(Integer)
    source_event_id: Mapped[str | None] = mapped_column(String(255), unique=True)

    document = relationship("Document", back_populates="jobs")
