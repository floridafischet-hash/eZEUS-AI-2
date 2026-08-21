"""Add a transactional queue outbox."""

import sqlalchemy as sa
from alembic import op

revision = "0009_queue_outbox"
down_revision = "0008_cleanup_job_phase_enum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("queue_outbox"):
        return
    op.create_table(
        "queue_outbox",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_queue_outbox_job_id_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_queue_outbox")),
    )
    op.create_index(
        "ix_queue_outbox_dispatch",
        "queue_outbox",
        ["status", "available_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_queue_outbox_job_id"),
        "queue_outbox",
        ["job_id"],
        unique=False,
    )


def downgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("queue_outbox"):
        return
    op.drop_index(op.f("ix_queue_outbox_job_id"), table_name="queue_outbox")
    op.drop_index("ix_queue_outbox_dispatch", table_name="queue_outbox")
    op.drop_table("queue_outbox")
