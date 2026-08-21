"""Drop ocr_artifacts table and remove legacy OCR phase records."""

import sqlalchemy as sa
from alembic import op

revision = "0007_remove_ocr_artifacts"
down_revision = "0006_admin_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DELETE FROM job_phases WHERE phase::text IN ('RUN_OCR', 'WRITE_OCR')"))
        op.execute(
            sa.text(
                "DO $$ BEGIN "
                "IF EXISTS ("
                "SELECT 1 FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
                "WHERE pg_type.typname = 'jobphase' "
                "AND pg_enum.enumlabel = 'DOWNLOAD_DOCUMENT'"
                ") THEN "
                "ALTER TYPE jobphase RENAME VALUE "
                "'DOWNLOAD_DOCUMENT' TO 'READ_DOCUMENT_TEXT'; "
                "END IF; END $$"
            )
        )
    else:
        op.execute(sa.text("DELETE FROM job_phases WHERE phase IN ('RUN_OCR', 'WRITE_OCR')"))
        op.execute(
            sa.text(
                "UPDATE job_phases SET phase = 'READ_DOCUMENT_TEXT' "
                "WHERE phase = 'DOWNLOAD_DOCUMENT'"
            )
        )

    # Drop the ocr_artifacts table if it still exists
    if inspector.has_table("ocr_artifacts"):
        op.drop_index(op.f("ix_ocr_artifacts_job_id"), table_name="ocr_artifacts")
        op.drop_table("ocr_artifacts")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text("ALTER TYPE jobphase RENAME VALUE 'READ_DOCUMENT_TEXT' TO 'DOWNLOAD_DOCUMENT'")
        )
    else:
        op.execute(
            sa.text(
                "UPDATE job_phases SET phase = 'DOWNLOAD_DOCUMENT' "
                "WHERE phase = 'READ_DOCUMENT_TEXT'"
            )
        )
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
