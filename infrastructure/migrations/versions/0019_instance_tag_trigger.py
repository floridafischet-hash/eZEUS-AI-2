"""Replace time delay with a per-instance Paperless tag trigger.

Revision ID: 0019_instance_tag_trigger
Revises: 0018_processing_delay
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0019_instance_tag_trigger"
down_revision = "0018_processing_delay"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("paperless_instances")
    }
    if "automatic_trigger_mode" not in columns:
        op.add_column(
            "paperless_instances",
            sa.Column(
                "automatic_trigger_mode",
                sa.String(length=32),
                nullable=False,
                server_default="document_added",
            ),
        )
    if "automatic_trigger_tag_name" not in columns:
        op.add_column(
            "paperless_instances",
            sa.Column("automatic_trigger_tag_name", sa.String(length=128), nullable=True),
        )
    if "processing_delay_hours" in columns:
        op.drop_column("paperless_instances", "processing_delay_hours")


def downgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("paperless_instances")
    }
    if "processing_delay_hours" not in columns:
        op.add_column(
            "paperless_instances",
            sa.Column("processing_delay_hours", sa.Integer(), nullable=False, server_default="0"),
        )
    for name in ("automatic_trigger_tag_name", "automatic_trigger_mode"):
        if name in columns:
            op.drop_column("paperless_instances", name)
