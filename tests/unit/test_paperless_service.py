import logging

from cryptography.fernet import Fernet
from pytest import LogCaptureFixture, MonkeyPatch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.config.settings import get_settings
from core.db.base import Base
from core.models.paperless_instance import PaperlessInstance
from core.paperless.service import find_enabled_instance_by_webhook_secret
from core.security.credentials import encrypt_credential


def test_corrupt_webhook_credential_does_not_hide_valid_instance(
    monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    try:
        with Session(engine) as db:
            db.add_all(
                [
                    PaperlessInstance(
                        name="Corrupt",
                        slug="corrupt-instance",
                        base_url="https://corrupt.example.test",
                        api_token_encrypted="unused",
                        webhook_secret_encrypted="not-a-fernet-token",
                    ),
                    PaperlessInstance(
                        name="Valid",
                        slug="valid-instance",
                        base_url="https://valid.example.test",
                        api_token_encrypted="unused",
                        webhook_secret_encrypted=encrypt_credential("valid-webhook-secret"),
                    ),
                ]
            )
            db.commit()

            with caplog.at_level(logging.WARNING, logger="core.paperless.service"):
                result = find_enabled_instance_by_webhook_secret(db, "valid-webhook-secret")

            assert result is not None
            assert result.slug == "valid-instance"
            warning_message = "Skipping Paperless instance with unreadable webhook credential"
            warning = next(
                record for record in caplog.records if record.message == warning_message
            )
            assert warning.__dict__["instance_slug"] == "corrupt-instance"
    finally:
        get_settings.cache_clear()
