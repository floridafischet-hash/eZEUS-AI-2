"""Add indexed HMAC lookup values for Paperless webhook secrets."""

import sqlalchemy as sa
from alembic import op

from core.security.credentials import decrypt_credential
from core.security.webhook_lookup import webhook_secret_hmac

revision = "0012_webhook_secret_hmac"
down_revision = "0011_jobs_created_at_index"
branch_labels = None
depends_on = None


def _column_names() -> set[str]:
    columns = sa.inspect(op.get_bind()).get_columns("paperless_instances")
    return {str(column["name"]) for column in columns}


def upgrade() -> None:
    if "webhook_secret_hmac" in _column_names():
        return
    with op.batch_alter_table("paperless_instances") as batch:
        batch.add_column(sa.Column("webhook_secret_hmac", sa.String(length=64), nullable=True))
        batch.create_index(
            "ix_paperless_instances_webhook_secret_hmac",
            ["webhook_secret_hmac"],
            unique=False,
        )

    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, webhook_secret_encrypted FROM paperless_instances")
    ).mappings()
    for row in rows:
        plaintext = decrypt_credential(str(row["webhook_secret_encrypted"]))
        connection.execute(
            sa.text(
                "UPDATE paperless_instances "
                "SET webhook_secret_hmac = :digest WHERE id = :instance_id"
            ),
            {
                "digest": webhook_secret_hmac(plaintext),
                "instance_id": row["id"],
            },
        )

    with op.batch_alter_table("paperless_instances") as batch:
        batch.alter_column(
            "webhook_secret_hmac",
            existing_type=sa.String(length=64),
            nullable=False,
        )


def downgrade() -> None:
    if "webhook_secret_hmac" not in _column_names():
        return
    with op.batch_alter_table("paperless_instances") as batch:
        batch.drop_index("ix_paperless_instances_webhook_secret_hmac")
        batch.drop_column("webhook_secret_hmac")
