"""Add title_template to paperless_instances.

Revision ID: 0015_title_template
Revises: 0014_field_extraction_profile
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0015_title_template"
down_revision = "0014_field_extraction_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("paperless_instances")
    }
    if "title_template" in columns:
        return
    op.add_column(
        "paperless_instances",
        sa.Column("title_template", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("paperless_instances")
    }
    if "title_template" not in columns:
        return
    op.drop_column("paperless_instances", "title_template")
