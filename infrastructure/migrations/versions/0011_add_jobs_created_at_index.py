"""Add an index for stable job log pagination."""

from alembic import op

revision = "0011_jobs_created_at_index"
down_revision = "0010_allow_title_overwrite"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_jobs_created_at_id", "jobs", ["created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_created_at_id", table_name="jobs")
