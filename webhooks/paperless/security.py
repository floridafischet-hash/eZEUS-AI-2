import hashlib
import hmac


def verify_shared_secret(provided: str | None, expected: str) -> bool:
    if not expected:
        return False
    if provided is None:
        return False
    return hmac.compare_digest(
        hashlib.sha256(provided.encode()).digest(),
        hashlib.sha256(expected.encode()).digest(),
    )
