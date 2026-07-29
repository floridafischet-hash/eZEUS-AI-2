"""Add individual administrative accounts and roles."""

import sqlalchemy as sa
from alembic import op

revision = "0006_admin_users"
down_revision = "0005_instance_field_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("admin_users"):
        return
    op.create_table(
        "admin_users",
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_users")),
        sa.UniqueConstraint("username", name=op.f("uq_admin_users_username")),
    )
    op.create_index(
        op.f("ix_admin_users_username"),
        "admin_users",
        ["username"],
        unique=True,
    )


def downgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("admin_users"):
        return
    op.drop_index(op.f("ix_admin_users_username"), table_name="admin_users")
    op.drop_table("admin_users")
