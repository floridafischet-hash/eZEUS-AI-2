"""Add allow_title_overwrite to paperless_instances."""

import sqlalchemy as sa
from alembic import op

revision = "0010_allow_title_overwrite"
down_revision = "0009_queue_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "paperless_instances",
        sa.Column("allow_title_overwrite", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("paperless_instances", "allow_title_overwrite")
