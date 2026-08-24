from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PaperlessInstance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "paperless_instances"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    api_token_encrypted: Mapped[str] = mapped_column(String(4096), nullable=False)
    webhook_secret_encrypted: Mapped[str] = mapped_column(String(4096), nullable=False)
    webhook_secret_hmac: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    verify_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_title_overwrite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    field_configs = relationship(
        "InstanceFieldConfig",
        back_populates="instance",
        cascade="all, delete-orphan",
        order_by="InstanceFieldConfig.sort_order",
    )
