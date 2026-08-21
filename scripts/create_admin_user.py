"""Create the first administrator account from an interactive shell."""

import argparse
import getpass
import re

from sqlalchemy import select

from core.db.session import SessionLocal
from core.models.admin_user import AdminUser
from core.security.passwords import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an eZEUS administrator account")
    parser.add_argument("username", help="Login name (3-64 characters)")
    args = parser.parse_args()

    username = args.username.strip()
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{2,63}", username):
        parser.error("username must contain 3-64 supported characters")

    password = getpass.getpass("Password (at least 12 characters): ")
    confirmation = getpass.getpass("Repeat password: ")
    if password != confirmation:
        parser.error("passwords do not match")
    if len(password) < 12:
        parser.error("password must contain at least 12 characters")

    with SessionLocal.begin() as db:
        existing = db.scalar(select(AdminUser.id).where(AdminUser.username == username))
        if existing is not None:
            parser.error(f"user {username!r} already exists")
        db.add(
            AdminUser(
                username=username,
                password_hash=hash_password(password),
                role="admin",
                enabled=True,
            )
        )

    print(f"Administrator {username!r} created.")


if __name__ == "__main__":
    main()
