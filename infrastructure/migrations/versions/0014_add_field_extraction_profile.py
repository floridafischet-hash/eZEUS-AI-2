"""Add an optional tenant field extraction profile.

Revision ID: 0014_field_extraction_profile
Revises: 0013_instance_soft_delete
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0014_field_extraction_profile"
down_revision = "0013_instance_soft_delete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_extraction_profile() -> bool:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("instance_field_configs")
    }
    return "extraction_profile" in columns


def upgrade() -> None:
    # 0002_repair_initial_schema runs Base.metadata.create_all(), which builds
    # the *current* model — so on a fresh database this column already exists by
    # the time this revision runs. Every migration from 0003 onwards guards
    # against that; this one did not, and `alembic upgrade head` failed against
    # an empty database with DuplicateColumn.
    if _has_extraction_profile():
        return
    op.add_column(
        "instance_field_configs",
        sa.Column("extraction_profile", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    if not _has_extraction_profile():
        return
    op.drop_column("instance_field_configs", "extraction_profile")
