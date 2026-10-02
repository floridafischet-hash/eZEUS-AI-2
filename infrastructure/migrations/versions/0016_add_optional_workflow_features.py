"""Add optional per-instance workflow features.

Revision ID: 0016_optional_workflow_features
Revises: 0015_title_template
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0016_optional_workflow_features"
down_revision = "0015_title_template"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("paperless_instances")
    }
    additions = (
        sa.Column("ocr_handoff_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ocr_request_tag_name", sa.String(length=128), nullable=True),
        sa.Column(
            "ocr_complete_tag_name",
            sa.String(length=128),
            nullable=False,
            server_default="paperless-gpt-auto-complete",
        ),
        sa.Column(
            "manual_reprocess_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "manual_reprocess_tag_name",
            sa.String(length=128),
            nullable=False,
            server_default="9",
        ),
    )
    for column in additions:
        if column.name not in columns:
            op.add_column("paperless_instances", column)


def downgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("paperless_instances")
    }
    for name in (
        "manual_reprocess_tag_name",
        "manual_reprocess_enabled",
        "ocr_complete_tag_name",
        "ocr_request_tag_name",
        "ocr_handoff_enabled",
    ):
        if name in columns:
            op.drop_column("paperless_instances", name)
