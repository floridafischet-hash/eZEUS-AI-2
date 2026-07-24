from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("connector", "external_document_id", name="uq_document_source"),
    )

    connector: Mapped[str] = mapped_column(String(64), nullable=False)
    external_document_id: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(1024))
    mime_type: Mapped[str | None] = mapped_column(String(255))
    document_type_external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    page_count: Mapped[int | None] = mapped_column(Integer)

    jobs = relationship("Job", back_populates="document", cascade="all, delete-orphan")
