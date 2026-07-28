"""Add encrypted Paperless instance configuration."""

import sqlalchemy as sa
from alembic import op

revision = "0003_paperless_instances"
down_revision = "0002_repair_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("paperless_instances"):
        return
    op.create_table(
        "paperless_instances",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=False),
        sa.Column("api_token_encrypted", sa.String(length=4096), nullable=False),
        sa.Column("webhook_secret_encrypted", sa.String(length=4096), nullable=False),
        sa.Column("verify_tls", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paperless_instances")),
        sa.UniqueConstraint("slug", name=op.f("uq_paperless_instances_slug")),
    )
    op.create_index(
        op.f("ix_paperless_instances_slug"),
        "paperless_instances",
        ["slug"],
        unique=True,
    )


def downgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("paperless_instances"):
        return
    op.drop_index(op.f("ix_paperless_instances_slug"), table_name="paperless_instances")
    op.drop_table("paperless_instances")
