from uuid import UUID

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Template(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "templates"
    __table_args__ = (
        UniqueConstraint(
            "document_type_external_id",
            "name",
            "version",
            name="uq_template_type_name_version",
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type_external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("templates.id"), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    cloud_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
