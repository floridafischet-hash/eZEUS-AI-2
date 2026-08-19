from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_entries"

    actor: Mapped[str] = mapped_column(String(255), default="system")
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), index=True)
    instance_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("paperless_instances.id"), index=True
    )
    target_system: Mapped[str | None] = mapped_column(String(128))
    field: Mapped[str | None] = mapped_column(String(255))
    old_value: Mapped[object | None] = mapped_column(JSON)
    new_value: Mapped[object | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(64), default="SUCCESS")
