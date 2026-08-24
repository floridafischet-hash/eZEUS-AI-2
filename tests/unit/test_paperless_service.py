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
from core.security.webhook_lookup import webhook_secret_hmac


def test_corrupt_webhook_credential_does_not_hide_valid_instance(
    monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    try:
        with Session(engine) as db:
            matching_hmac = webhook_secret_hmac("valid-webhook-secret")
            db.add_all(
                [
                    PaperlessInstance(
                        name="Corrupt",
                        slug="corrupt-instance",
                        base_url="https://corrupt.example.test",
                        api_token_encrypted="unused",
                        webhook_secret_encrypted="not-a-fernet-token",
                        webhook_secret_hmac=matching_hmac,
                    ),
                    PaperlessInstance(
                        name="Valid",
                        slug="valid-instance",
                        base_url="https://valid.example.test",
                        api_token_encrypted="unused",
                        webhook_secret_encrypted=encrypt_credential("valid-webhook-secret"),
                        webhook_secret_hmac=matching_hmac,
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


def test_webhook_lookup_does_not_decrypt_nonmatching_instances(
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
                        name="Unrelated corrupt",
                        slug="unrelated-corrupt",
                        base_url="https://unrelated.example.test",
                        api_token_encrypted="unused",
                        webhook_secret_encrypted="not-a-fernet-token",
                        webhook_secret_hmac=webhook_secret_hmac("different-secret"),
                    ),
                    PaperlessInstance(
                        name="Matching",
                        slug="matching",
                        base_url="https://matching.example.test",
                        api_token_encrypted="unused",
                        webhook_secret_encrypted=encrypt_credential("matching-secret"),
                        webhook_secret_hmac=webhook_secret_hmac("matching-secret"),
                    ),
                ]
            )
            db.commit()

            with caplog.at_level(logging.WARNING, logger="core.paperless.service"):
                result = find_enabled_instance_by_webhook_secret(db, "matching-secret")

            assert result is not None
            assert result.slug == "matching"
            assert caplog.records == []
    finally:
        get_settings.cache_clear()


def test_webhook_lookup_verifies_plaintext_after_hmac_match(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    try:
        with Session(engine) as db:
            db.add(
                PaperlessInstance(
                    name="Stale lookup",
                    slug="stale-lookup",
                    base_url="https://stale.example.test",
                    api_token_encrypted="unused",
                    webhook_secret_encrypted=encrypt_credential("actual-secret"),
                    webhook_secret_hmac=webhook_secret_hmac("provided-secret"),
                )
            )
            db.commit()

            assert find_enabled_instance_by_webhook_secret(db, "provided-secret") is None
    finally:
        get_settings.cache_clear()
