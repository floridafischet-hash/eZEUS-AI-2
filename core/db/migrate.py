from alembic import command
from alembic.config import Config
from sqlalchemy import text

from core.db.session import engine

# Stable, application-specific PostgreSQL advisory lock id.  Every pod may run
# this command safely; only one migration process enters Alembic at a time.
MIGRATION_LOCK_ID = 2_025_072_700_2


def run_migrations() -> None:
    config = Config("alembic.ini")
    if engine.dialect.name != "postgresql":
        command.upgrade(config, "head")
        engine.dispose()
        return

    with engine.connect() as connection:
        connection.execute(
            text("SELECT pg_advisory_lock(:lock_id)"),
            {"lock_id": MIGRATION_LOCK_ID},
        )
        connection.commit()
        try:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        finally:
            # A failed migration may leave the connection in an aborted
            # transaction. Roll it back before issuing the explicit unlock so
            # that the original error is not masked by PostgreSQL's failed-
            # transaction state.
            if connection.in_transaction():
                connection.rollback()
            connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": MIGRATION_LOCK_ID},
            )
            connection.commit()
    engine.dispose()


if __name__ == "__main__":
    run_migrations()
