"""Remove retired OCR values from the PostgreSQL job phase enum."""

import sqlalchemy as sa
from alembic import op

revision = "0008_cleanup_job_phase_enum"
down_revision = "0007_remove_ocr_artifacts"
branch_labels = None
depends_on = None

CURRENT_PHASES = (
    "RECEIVE_EVENT",
    "LOAD_DOCUMENT",
    "READ_DOCUMENT_TEXT",
    "SELECT_TEMPLATE",
    "EXTRACT_FIELDS",
    "VALIDATE_RESULTS",
    "RELOAD_METADATA",
    "WRITE_METADATA",
    "CLEANUP",
    "COMPLETE",
)

LEGACY_PHASES = (
    "RECEIVE_EVENT",
    "LOAD_DOCUMENT",
    "DOWNLOAD_DOCUMENT",
    "RUN_OCR",
    "WRITE_OCR",
    "SELECT_TEMPLATE",
    "EXTRACT_FIELDS",
    "VALIDATE_RESULTS",
    "RELOAD_METADATA",
    "WRITE_METADATA",
    "CLEANUP",
    "COMPLETE",
)


def _recreate_postgresql_enum(
    values: tuple[str, ...], *, columns_are_varchar: bool = False
) -> None:
    quoted_values = ", ".join(f"'{value}'" for value in values)
    if not columns_are_varchar:
        op.execute(sa.text("ALTER TABLE jobs ALTER COLUMN phase TYPE varchar USING phase::text"))
        op.execute(
            sa.text("ALTER TABLE job_phases ALTER COLUMN phase TYPE varchar USING phase::text")
        )
    op.execute(sa.text("DROP TYPE jobphase"))
    op.execute(sa.text(f"CREATE TYPE jobphase AS ENUM ({quoted_values})"))
    op.execute(sa.text("ALTER TABLE jobs ALTER COLUMN phase TYPE jobphase USING phase::jobphase"))
    op.execute(
        sa.text("ALTER TABLE job_phases ALTER COLUMN phase TYPE jobphase USING phase::jobphase")
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(sa.text("ALTER TABLE jobs ALTER COLUMN phase TYPE varchar USING phase::text"))
    op.execute(sa.text("ALTER TABLE job_phases ALTER COLUMN phase TYPE varchar USING phase::text"))
    op.execute(
        sa.text(
            "UPDATE jobs SET phase = 'READ_DOCUMENT_TEXT' "
            "WHERE phase::text IN ('RUN_OCR', 'WRITE_OCR', 'DOWNLOAD_DOCUMENT')"
        )
    )
    _recreate_postgresql_enum(CURRENT_PHASES, columns_are_varchar=True)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(sa.text("ALTER TABLE jobs ALTER COLUMN phase TYPE varchar USING phase::text"))
    op.execute(sa.text("ALTER TABLE job_phases ALTER COLUMN phase TYPE varchar USING phase::text"))
    op.execute(
        sa.text(
            "UPDATE jobs SET phase = 'DOWNLOAD_DOCUMENT' WHERE phase::text = 'READ_DOCUMENT_TEXT'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE job_phases SET phase = 'DOWNLOAD_DOCUMENT' "
            "WHERE phase::text = 'READ_DOCUMENT_TEXT'"
        )
    )
    _recreate_postgresql_enum(LEGACY_PHASES, columns_are_varchar=True)
