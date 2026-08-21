import pytest
from pydantic import ValidationError

from core.config.settings import Settings


def test_production_rejects_example_credentials() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url=(
                "postgresql+psycopg://ezeus:example-postgres-password-change-me@postgres:5432/ezeus"
            ),
            paperless_api_token="example-paperless-api-token",
            paperless_webhook_secret="example-webhook-secret",
        )
