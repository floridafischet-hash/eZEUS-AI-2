"""Make workflow marker tag names configurable per instance.

Revision ID: 0017_configurable_marker_tags
Revises: 0016_optional_workflow_features
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0017_configurable_marker_tags"
down_revision = "0016_optional_workflow_features"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("paperless_instances")
    }
    additions = (
        sa.Column(
            "ocr_pending_tag_name",
            sa.String(length=128),
            nullable=False,
            server_default="ezeus-ai-2-ocr-pending",
        ),
        sa.Column(
            "ocr_triggered_tag_name",
            sa.String(length=128),
            nullable=False,
            server_default="ezeus-ai-2-ocr-triggered",
        ),
    )
    for column in additions:
        if column.name not in columns:
            op.add_column("paperless_instances", column)


def downgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("paperless_instances")
    }
    for name in ("ocr_triggered_tag_name", "ocr_pending_tag_name"):
        if name in columns:
            op.drop_column("paperless_instances", name)
