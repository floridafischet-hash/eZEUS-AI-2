"""Reset the password of an administrator account from an interactive shell."""

import argparse
import getpass
import os
from datetime import UTC, datetime

from sqlalchemy import select

from core.db.session import SessionLocal
from core.models.admin_user import AdminUser
from core.models.audit import AuditEntry
from core.security.passwords import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset an eZEUS administrator password")
    parser.add_argument("username", help="Login name of the existing account")
    parser.add_argument(
        "--password-env",
        metavar="VARIABLE",
        help="read the new password from an environment variable for non-interactive recovery",
    )
    parser.add_argument(
        "--enable",
        action="store_true",
        help="re-enable the account if it is currently disabled",
    )
    args = parser.parse_args()

    username = args.username.strip()

    if args.password_env:
        password = os.environ.get(args.password_env, "")
        confirmation = password
    else:
        password = getpass.getpass("New password (at least 12 characters): ")
        confirmation = getpass.getpass("Repeat new password: ")
    if password != confirmation:
        parser.error("passwords do not match")
    if len(password) < 12:
        parser.error("password must contain at least 12 characters")

    with SessionLocal.begin() as db:
        user = db.scalar(select(AdminUser).where(AdminUser.username == username))
        if user is None:
            parser.error(f"user {username!r} does not exist")
        was_enabled = user.enabled
        user.password_hash = hash_password(password)
        if args.enable:
            user.enabled = True
        user.updated_at = datetime.now(UTC)
        db.add(
            AuditEntry(
                actor="cli",
                action="RESET_ADMIN_PASSWORD",
                entity_type="admin_user",
                entity_id=str(user.id),
                target_system="ezeus",
                field="password_hash",
                old_value={"enabled": was_enabled},
                new_value={"enabled": user.enabled},
            )
        )

    print(f"Password for administrator {username!r} reset.")
    if not was_enabled and not args.enable:
        print(
            f"Warning: account {username!r} is disabled and cannot log in. "
            "Re-run with --enable to reactivate it."
        )


if __name__ == "__main__":
    main()
