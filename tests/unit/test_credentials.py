from cryptography.fernet import Fernet
from pytest import MonkeyPatch
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from core.config.settings import get_settings
from core.db.base import Base
from core.models.paperless_instance import PaperlessInstance
from core.security.credentials import decrypt_credential, encrypt_credential
from scripts.rotate_credentials import rotate_all_credentials


def _set_keys(monkeypatch: MonkeyPatch, *, keys: str, legacy_key: str = "") -> None:
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEYS", keys)
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", legacy_key)
    get_settings.cache_clear()


def test_legacy_single_key_remains_supported(monkeypatch: MonkeyPatch) -> None:
    legacy_key = Fernet.generate_key().decode()
    _set_keys(monkeypatch, keys="", legacy_key=legacy_key)
    try:
        encrypted = encrypt_credential("legacy-secret")
        assert decrypt_credential(encrypted) == "legacy-secret"
        assert Fernet(legacy_key.encode()).decrypt(encrypted.encode()) == b"legacy-secret"
    finally:
        get_settings.cache_clear()


def test_keyring_encrypts_with_first_key_and_decrypts_old_key(
    monkeypatch: MonkeyPatch,
) -> None:
    new_key = Fernet.generate_key().decode()
    old_key = Fernet.generate_key().decode()
    old_token = Fernet(old_key.encode()).encrypt(b"old-secret").decode()
    _set_keys(monkeypatch, keys=f"{new_key},{old_key}")
    try:
        assert decrypt_credential(old_token) == "old-secret"
        new_token = encrypt_credential("new-secret")
        assert Fernet(new_key.encode()).decrypt(new_token.encode()) == b"new-secret"
    finally:
        get_settings.cache_clear()


def test_rotation_reencrypts_every_paperless_credential_with_primary_key(
    monkeypatch: MonkeyPatch,
) -> None:
    new_key = Fernet.generate_key().decode()
    old_key = Fernet.generate_key().decode()
    old_fernet = Fernet(old_key.encode())
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            PaperlessInstance(
                name="Rotating",
                slug="rotating",
                base_url="https://paperless.example.test",
                api_token_encrypted=old_fernet.encrypt(b"api-token").decode(),
                webhook_secret_encrypted=old_fernet.encrypt(b"webhook-secret").decode(),
            )
        )
        db.commit()

        _set_keys(monkeypatch, keys=f"{new_key},{old_key}")
        try:
            assert rotate_all_credentials(db) == 2
            db.commit()
            instance = db.scalar(select(PaperlessInstance))
            assert instance is not None
            new_fernet = Fernet(new_key.encode())
            assert new_fernet.decrypt(instance.api_token_encrypted.encode()) == b"api-token"
            assert (
                new_fernet.decrypt(instance.webhook_secret_encrypted.encode())
                == b"webhook-secret"
            )
        finally:
            get_settings.cache_clear()
