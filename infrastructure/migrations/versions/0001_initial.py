"""Create the initial eZEUS schema."""

from alembic import op

from core import models
from core.db.base import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not models.__all__:
        raise RuntimeError("Database models are not registered")
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
