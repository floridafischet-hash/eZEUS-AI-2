"""Add per-instance processing delay.

Revision ID: 0018_processing_delay
Revises: 0017_configurable_marker_tags
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0018_processing_delay"
down_revision = "0017_configurable_marker_tags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("paperless_instances")
    }
    if "processing_delay_hours" not in columns:
        op.add_column(
            "paperless_instances",
            sa.Column(
                "processing_delay_hours",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("paperless_instances")
    }
    if "processing_delay_hours" in columns:
        op.drop_column("paperless_instances", "processing_delay_hours")
