from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PaperlessInstance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "paperless_instances"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    api_token_encrypted: Mapped[str] = mapped_column(String(4096), nullable=False)
    webhook_secret_encrypted: Mapped[str] = mapped_column(String(4096), nullable=False)
    verify_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
