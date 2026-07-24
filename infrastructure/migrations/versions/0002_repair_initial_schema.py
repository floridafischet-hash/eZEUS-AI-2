"""Create model tables for installations affected by the empty metadata migration."""

from alembic import op

from core import models
from core.db.base import Base

revision = "0002_repair_initial_schema"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not models.__all__:
        raise RuntimeError("Database models are not registered")
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
