"""Store raw and verified OCR cleanup results."""

import sqlalchemy as sa
from alembic import op

revision = "0004_ocr_artifacts"
down_revision = "0003_paperless_instances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("ocr_artifacts"):
        return
    op.create_table(
        "ocr_artifacts",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("cleaned_text", sa.Text(), nullable=True),
        sa.Column("cleanup_accepted", sa.Boolean(), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_ocr_artifacts_job_id_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ocr_artifacts")),
    )
    op.create_index(
        op.f("ix_ocr_artifacts_job_id"),
        "ocr_artifacts",
        ["job_id"],
        unique=False,
    )


def downgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("ocr_artifacts"):
        return
    op.drop_index(op.f("ix_ocr_artifacts_job_id"), table_name="ocr_artifacts")
    op.drop_table("ocr_artifacts")
