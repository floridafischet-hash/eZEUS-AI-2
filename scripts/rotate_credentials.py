"""Re-encrypt stored credentials with the primary configured Fernet key."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.db.session import SessionLocal
from core.models.paperless_instance import PaperlessInstance
from core.security.credentials import rotate_credential


def rotate_all_credentials(db: Session) -> int:
    instances = db.scalars(select(PaperlessInstance)).all()
    rotated = 0
    for instance in instances:
        instance.api_token_encrypted = rotate_credential(instance.api_token_encrypted)
        instance.webhook_secret_encrypted = rotate_credential(instance.webhook_secret_encrypted)
        rotated += 2
    return rotated


def main() -> None:
    with SessionLocal.begin() as db:
        rotated = rotate_all_credentials(db)
    print(f"Rotated {rotated} encrypted credential values.")


if __name__ == "__main__":
    main()
