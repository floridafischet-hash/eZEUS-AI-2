import os
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from core.config.settings import get_settings

DATABASE_URL = os.getenv("MIGRATION_TEST_DATABASE_URL")


@pytest.mark.skipif(not DATABASE_URL, reason="requires a disposable PostgreSQL database")
def test_legacy_phase_history_survives_upgrade_downgrade_upgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    get_settings.cache_clear()
    config = Config("alembic.ini")
    engine = create_engine(DATABASE_URL)
    document_id = UUID("00000000-0000-0000-0000-000000000101")
    job_id = UUID("00000000-0000-0000-0000-000000000102")

    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.downgrade(config, "0006_admin_users")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO documents "
                "(id, connector, external_document_id, filename, created_at, updated_at) "
                "VALUES (:id, 'paperless:legacy', '42', 'legacy.pdf', now(), now())"
            ),
            {"id": document_id},
        )
        connection.execute(
            text(
                "INSERT INTO jobs "
                "(id, document_id, status, phase, priority, retry_count, created_at, updated_at) "
                "VALUES (:id, :document_id, 'COMPLETED', 'DOWNLOAD_DOCUMENT', "
                "'NORMAL', 0, now(), now())"
            ),
            {"id": job_id, "document_id": document_id},
        )
        connection.execute(
            text(
                "INSERT INTO job_phases "
                "(id, job_id, phase, status, started_at, finished_at, metadata, "
                "created_at, updated_at) VALUES "
                "('00000000-0000-0000-0000-000000000103', :job_id, 'RUN_OCR', "
                "'COMPLETED', now(), now(), '{\"engine\":\"legacy\"}', now(), now()), "
                "('00000000-0000-0000-0000-000000000104', :job_id, 'WRITE_OCR', "
                "'COMPLETED', now(), now(), '{}', now(), now())"
            ),
            {"job_id": job_id},
        )

    command.upgrade(config, "head")
    with engine.connect() as connection:
        upgraded = connection.execute(
            text(
                "SELECT phase::text, metadata->>'legacy_phase', metadata->>'engine' "
                "FROM job_phases WHERE job_id = :job_id ORDER BY id"
            ),
            {"job_id": job_id},
        ).all()
    assert upgraded == [
        ("READ_DOCUMENT_TEXT", "RUN_OCR", "legacy"),
        ("READ_DOCUMENT_TEXT", "WRITE_OCR", None),
    ]

    command.downgrade(config, "0006_admin_users")
    with engine.connect() as connection:
        downgraded = connection.execute(
            text("SELECT phase::text, metadata FROM job_phases WHERE job_id = :job_id ORDER BY id"),
            {"job_id": job_id},
        ).all()
    assert downgraded == [("RUN_OCR", {"engine": "legacy"}), ("WRITE_OCR", {})]

    command.upgrade(config, "head")
    engine.dispose()
    get_settings.cache_clear()
