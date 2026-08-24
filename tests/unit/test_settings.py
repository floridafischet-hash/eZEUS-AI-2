import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from core.config.settings import Settings


@pytest.mark.parametrize("app_env", ["production", "PRODUCTION"])
def test_production_rejects_example_credentials(app_env: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env=app_env,
            database_url=(
                "postgresql+psycopg://ezeus:example-postgres-password-change-me@postgres:5432/ezeus"
            ),
            paperless_api_token="example-paperless-api-token",
            paperless_webhook_secret="example-webhook-secret",
        )


def test_postgres_components_are_encoded_without_changing_credentials() -> None:
    settings = Settings(
        postgres_host="postgres",
        postgres_user="user name",
        postgres_password="p a+/@:ss",
        postgres_database="database/name",
    )
    parsed = make_url(settings.database_url)
    assert parsed.username == "user name"
    assert parsed.password == "p a+/@:ss"
    assert parsed.database == "database/name"


def test_production_accepts_valid_fernet_key() -> None:
    settings = Settings(
        app_env="production",
        database_url="postgresql+psycopg://ezeus:strong-password@postgres:5432/ezeus",
        paperless_api_token="strong-api-token",
        paperless_webhook_secret="strong-webhook-secret",
        credential_encryption_key=Fernet.generate_key().decode(),
        webhook_lookup_hmac_key="a-strong-independent-hmac-key-123456",
    )
    assert settings.app_env == "production"


def test_celery_hard_time_limit_is_independently_configurable() -> None:
    settings = Settings(
        ollama_timeout_seconds=10,
        celery_task_time_limit_seconds=123,
    )
    assert settings.celery_task_time_limit_seconds == 123


def test_celery_hard_time_limit_must_exceed_soft_limit() -> None:
    with pytest.raises(ValidationError, match="must exceed the Celery soft time limit"):
        Settings(
            ollama_timeout_seconds=300,
            celery_task_time_limit_seconds=360,
        )


def test_database_pool_settings_are_configurable() -> None:
    settings = Settings(
        db_pool_size=8,
        db_max_overflow=3,
        db_pool_timeout_seconds=12.5,
    )
    assert settings.db_pool_size == 8
    assert settings.db_max_overflow == 3
    assert settings.db_pool_timeout_seconds == 12.5


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"db_pool_size": 0}, "DB_POOL_SIZE must be positive"),
        ({"db_max_overflow": -1}, "DB_MAX_OVERFLOW must not be negative"),
        ({"db_pool_timeout_seconds": 0}, "DB_POOL_TIMEOUT_SECONDS must be positive"),
    ],
)
def test_database_pool_settings_reject_invalid_values(
    override: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        Settings(**override)


def test_instance_job_limit_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="MAX_CONCURRENT_JOBS_PER_INSTANCE"):
        Settings(max_concurrent_jobs_per_instance=0)
