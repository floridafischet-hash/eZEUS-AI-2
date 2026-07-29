from uuid import UUID

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class InstanceFieldConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "instance_field_configs"
    __table_args__ = (
        UniqueConstraint("instance_id", "field_key", name="uq_instance_field_config_key"),
    )

    instance_id: Mapped[UUID] = mapped_column(
        ForeignKey("paperless_instances.id", ondelete="CASCADE"), index=True
    )
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    field_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_standard: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ocr_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    external_field_id: Mapped[str | None] = mapped_column(String(255))
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    extraction_instructions: Mapped[str | None] = mapped_column(String(2000))

    instance = relationship("PaperlessInstance", back_populates="field_configs")
