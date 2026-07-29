# ruff: noqa: E501

import re
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.db.session import get_db
from core.models.admin_user import AdminUser
from core.models.audit import AuditEntry
from core.security.admin_auth import AdminPrincipal, require_admin_secret
from core.security.passwords import hash_password

router = APIRouter(prefix="/api/admin-users", tags=["admin-users"])
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{2,63}$")


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=256)
    role: Literal["admin", "viewer"] = "admin"

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        if not USERNAME_PATTERN.fullmatch(value):
            raise ValueError("username contains unsupported characters")
        return value


class AdminUserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=12, max_length=256)
    role: Literal["admin", "viewer"] | None = None
    enabled: bool | None = None


def _serialize(user: AdminUser) -> dict[str, object]:
    return {
        "id": str(user.id),
        "username": user.username,
        "role": user.role,
        "enabled": user.enabled,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


@router.get("")
def list_admin_users(
    db: Annotated[Session, Depends(get_db)],
    _principal: Annotated[AdminPrincipal, Depends(require_admin_secret)],
) -> dict[str, object]:
    users = db.scalars(select(AdminUser).order_by(AdminUser.username)).all()
    return {"users": [_serialize(user) for user in users]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_admin_user(
    payload: AdminUserCreate,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[AdminPrincipal, Depends(require_admin_secret)],
) -> dict[str, object]:
    user = AdminUser(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        enabled=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists") from exc
    db.add(
        AuditEntry(
            actor=principal.username,
            action="CREATE_ADMIN_USER",
            entity_type="admin_user",
            entity_id=str(user.id),
            target_system="ezeus",
            old_value=None,
            new_value={"username": user.username, "role": user.role, "enabled": True},
        )
    )
    db.commit()
    db.refresh(user)
    return _serialize(user)


ADMIN_USERS_HTML = """<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Administratoren | eZEUS-AI-2</title>
  <style>
    :root { color-scheme:dark; --bg:#0b1020; --panel:#141b2d; --soft:#1a2338;
      --text:#f4f7ff; --muted:#9ca9c4; --accent:#65d6ad; --border:#2a3550;
      --error:#ff7b86; } * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text);
      font:15px/1.5 Inter,system-ui,sans-serif; }
    header { padding:1rem clamp(1rem,4vw,3rem); border-bottom:1px solid var(--border);
      display:flex; justify-content:space-between; } a { color:var(--accent); }
    main { width:min(1050px,calc(100% - 2rem)); margin:2rem auto; }
    .panel { background:var(--panel); border:1px solid var(--border); border-radius:1rem;
      padding:1.2rem; margin-bottom:1rem; } .grid { display:grid;
      grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem; }
    label { display:block; color:var(--muted); } input,select,button {
      width:100%; padding:.65rem; border:1px solid var(--border); border-radius:.55rem;
      background:var(--soft); color:var(--text); font:inherit; }
    button { cursor:pointer; } button.primary { background:var(--accent); color:#08111b;
      font-weight:700; } .user { display:grid; grid-template-columns:1fr 150px 100px 130px;
      gap:1rem; align-items:center; padding:.8rem 0; border-bottom:1px solid var(--border); }
    #message { color:var(--accent); min-height:1.5rem; } #message.error { color:var(--error); }
    @media(max-width:700px) { .grid,.user { grid-template-columns:1fr; } }
  </style>
</head>
<body>
<header><strong>Administratorkonten</strong><a href="/admin/instances">Instanzen</a></header>
<main>
  <section class="panel">
    <h1>Anmeldung</h1>
    <div class="grid">
      <div><label for="login-user">Benutzername</label>
        <input id="login-user" autocomplete="username"></div>
      <div><label for="login-password">Passwort</label>
        <input id="login-password" type="password" autocomplete="current-password"></div>
      <div><label for="legacy-secret">Bootstrap-Admin-Secret</label>
        <input id="legacy-secret" type="password"></div>
      <div><button id="load" type="button">Konten laden</button></div>
    </div>
    <div id="message"></div>
  </section>
  <section class="panel">
    <h2>Neues Konto</h2>
    <div class="grid">
      <div><label for="new-user">Benutzername</label><input id="new-user"></div>
      <div><label for="new-password">Passwort, mindestens 12 Zeichen</label>
        <input id="new-password" type="password" autocomplete="new-password"></div>
      <div><label for="new-role">Rolle</label><select id="new-role">
        <option value="admin">Administrator</option><option value="viewer">Nur Lesen</option>
      </select></div>
      <div><button id="create" class="primary" type="button">Konto anlegen</button></div>
    </div>
  </section>
  <section class="panel"><h2>Konten</h2><div id="users"></div></section>
</main>
<script>
  const message=document.getElementById("message");
  const usersRoot=document.getElementById("users");
  function headers(json=false) {
    const username=document.getElementById("login-user").value;
    const password=document.getElementById("login-password").value;
    const result={};
    if(username&&password) result.Authorization=`Basic ${btoa(`${username}:${password}`)}`;
    else result["X-EZEUS-Admin-Secret"]=document.getElementById("legacy-secret").value;
    if(json) result["Content-Type"]="application/json";
    return result;
  }
  function show(text,error=false){message.textContent=text;message.classList.toggle("error",error);}
  async function load() {
    const response=await fetch("/api/admin-users",{headers:headers()});
    const body=await response.json(); if(!response.ok){show(body.detail||`HTTP ${response.status}`,
      true);return;} usersRoot.replaceChildren();
    body.users.forEach(user=>{
      const row=document.createElement("div"); row.className="user";
      const name=document.createElement("div"); name.textContent=
        `${user.username} (${user.enabled?"aktiv":"deaktiviert"})`;
      const role=document.createElement("select");
      role.add(new Option("Administrator","admin")); role.add(new Option("Nur Lesen","viewer"));
      role.value=user.role;
      const enabled=document.createElement("input"); enabled.type="checkbox"; enabled.checked=user.enabled;
      const save=document.createElement("button"); save.textContent="Änderung speichern";
      save.addEventListener("click",async()=>{
        const result=await fetch(`/api/admin-users/${user.id}`,{method:"PATCH",headers:headers(true),
          body:JSON.stringify({role:role.value,enabled:enabled.checked})});
        const body=await result.json(); show(body.detail||
          (result.ok?"Konto aktualisiert.":`HTTP ${result.status}`),!result.ok); if(result.ok)load();
      });
      row.append(name,role,enabled,save); usersRoot.append(row);
    });
  }
  async function create() {
    const response=await fetch("/api/admin-users",{method:"POST",headers:headers(true),
      body:JSON.stringify({username:document.getElementById("new-user").value,
        password:document.getElementById("new-password").value,
        role:document.getElementById("new-role").value})});
    const body=await response.json(); show(body.detail||
      (response.ok?"Konto angelegt.":`HTTP ${response.status}`),!response.ok);
    if(response.ok)load();
  }
  document.getElementById("load").addEventListener("click",load);
  document.getElementById("create").addEventListener("click",create);
</script>
</body>
</html>"""


@router.get("/page", response_class=HTMLResponse, include_in_schema=False)
def admin_users_page() -> str:
    return ADMIN_USERS_HTML


@router.patch("/{user_id}")
def update_admin_user(
    user_id: UUID,
    payload: AdminUserUpdate,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[AdminPrincipal, Depends(require_admin_secret)],
) -> dict[str, object]:
    user = db.get(AdminUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Administrator account not found")
    changes = payload.model_dump(exclude_unset=True)
    if principal.user_id == user.id and (
        changes.get("enabled") is False or changes.get("role") == "viewer"
    ):
        raise HTTPException(status_code=409, detail="Administrators cannot revoke their own access")
    if user.role == "admin" and user.enabled and (
        changes.get("enabled") is False or changes.get("role") == "viewer"
    ):
        active_admins = db.scalar(
            select(func.count()).select_from(AdminUser).where(
                AdminUser.role == "admin",
                AdminUser.enabled.is_(True),
            )
        )
        if active_admins == 1:
            raise HTTPException(status_code=409, detail="The last administrator must remain active")
    old_value = _serialize(user)
    if "password" in changes:
        user.password_hash = hash_password(str(changes["password"]))
    if "role" in changes:
        user.role = str(changes["role"])
    if "enabled" in changes:
        user.enabled = bool(changes["enabled"])
    user.updated_at = datetime.now(UTC)
    db.add(
        AuditEntry(
            actor=principal.username,
            action="UPDATE_ADMIN_USER",
            entity_type="admin_user",
            entity_id=str(user.id),
            target_system="ezeus",
            old_value=old_value,
            new_value=_serialize(user),
        )
    )
    db.commit()
    db.refresh(user)
    return _serialize(user)
