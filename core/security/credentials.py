from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from core.config.settings import get_settings


class CredentialEncryptionError(RuntimeError):
    pass


def _fernet() -> MultiFernet:
    keys = get_settings().effective_credential_encryption_keys
    if not keys:
        raise CredentialEncryptionError("Credential encryption key is not configured")
    try:
        return MultiFernet([Fernet(key.encode()) for key in keys])
    except (TypeError, ValueError) as exc:
        raise CredentialEncryptionError("Credential encryption key list is invalid") from exc


def encrypt_credential(value: str) -> str:
    if not value:
        raise ValueError("Credential must not be empty")
    return _fernet().encrypt(value.encode()).decode()


def decrypt_credential(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise CredentialEncryptionError("Stored credential cannot be decrypted") from exc


def rotate_credential(value: str) -> str:
    try:
        return _fernet().rotate(value.encode()).decode()
    except InvalidToken as exc:
        raise CredentialEncryptionError("Stored credential cannot be decrypted") from exc
