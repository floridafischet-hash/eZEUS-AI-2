"""Add an index for stable job log pagination."""

import sqlalchemy as sa
from alembic import op

revision = "0011_jobs_created_at_index"
down_revision = "0010_allow_title_overwrite"
branch_labels = None
depends_on = None


def upgrade() -> None:
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("jobs")}
    if "ix_jobs_created_at_id" in indexes:
        return
    op.create_index("ix_jobs_created_at_id", "jobs", ["created_at", "id"])


def downgrade() -> None:
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("jobs")}
    if "ix_jobs_created_at_id" not in indexes:
        return
    op.drop_index("ix_jobs_created_at_id", table_name="jobs")
