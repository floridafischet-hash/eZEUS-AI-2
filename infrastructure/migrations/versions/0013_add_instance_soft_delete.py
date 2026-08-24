"""Retain deleted Paperless instances so their slugs cannot be reused."""

import sqlalchemy as sa
from alembic import op

revision = "0013_instance_soft_delete"
down_revision = "0012_webhook_secret_hmac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("paperless_instances")
    }
    if "deleted_at" in columns:
        return
    with op.batch_alter_table("paperless_instances") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_paperless_instances_deleted_at", ["deleted_at"], unique=False)


def downgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("paperless_instances")
    }
    if "deleted_at" not in columns:
        return
    with op.batch_alter_table("paperless_instances") as batch:
        batch.drop_index("ix_paperless_instances_deleted_at")
        batch.drop_column("deleted_at")
