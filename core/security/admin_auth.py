from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.db.session import get_db
from core.models.admin_user import AdminUser
from core.security.passwords import verify_password

basic_auth = HTTPBasic(auto_error=False)


@dataclass(frozen=True)
class AdminPrincipal:
    user_id: UUID
    username: str
    role: str


def require_admin_user(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPBasicCredentials | None, Depends(basic_auth)],
    x_ezeus_admin_user: str | None = Header(default=None),
    x_ezeus_admin_password: str | None = Header(default=None),
) -> AdminPrincipal:
    username = x_ezeus_admin_user or (credentials.username if credentials else None)
    password = x_ezeus_admin_password or (credentials.password if credentials else None)
    if not username or not password:
        raise HTTPException(
            status_code=401,
            detail="Administrative authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    user = db.scalar(
        select(AdminUser).where(
            AdminUser.username == username,
            AdminUser.enabled.is_(True),
        )
    )
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid administrative credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return AdminPrincipal(user.id, user.username, user.role)


def require_admin_secret(
    principal: Annotated[AdminPrincipal, Depends(require_admin_user)],
) -> AdminPrincipal:
    if principal.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator role required")
    return principal
