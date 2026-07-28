from cryptography.fernet import Fernet, InvalidToken

from core.config.settings import get_settings


class CredentialEncryptionError(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = get_settings().credential_encryption_key.strip()
    if not key:
        raise CredentialEncryptionError("CREDENTIAL_ENCRYPTION_KEY is not configured")
    try:
        return Fernet(key.encode())
    except (TypeError, ValueError) as exc:
        raise CredentialEncryptionError("CREDENTIAL_ENCRYPTION_KEY is invalid") from exc


def encrypt_credential(value: str) -> str:
    if not value:
        raise ValueError("Credential must not be empty")
    return _fernet().encrypt(value.encode()).decode()


def decrypt_credential(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise CredentialEncryptionError("Stored credential cannot be decrypted") from exc
