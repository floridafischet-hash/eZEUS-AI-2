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
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("instance_field_configs")
    }
    if "extraction_profile" in columns:
        return
    op.add_column(
        "instance_field_configs",
        sa.Column("extraction_profile", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("instance_field_configs")
    }
    if "extraction_profile" not in columns:
        return
    op.drop_column("instance_field_configs", "extraction_profile")
