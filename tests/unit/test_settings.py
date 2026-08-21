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
    )
    assert settings.app_env == "production"
