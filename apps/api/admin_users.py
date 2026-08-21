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

from apps.api.ui import page_shell
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


@router.get("/page", response_class=HTMLResponse, include_in_schema=False)
def admin_users_page() -> str:
    content = """
<div class="grid sidebar-layout">
  <div class="content-stack">
    <section class="panel">
      <div class="section-heading">
        <div>
          <h2>Neues Administratorkonto</h2>
          <p class="section-copy">Persönliche Zugänge mit passender Berechtigungsrolle anlegen.</p>
        </div>
      </div>
      <div class="form-grid">
        <div><label for="new-user">Benutzername</label>
          <input id="new-user" autocomplete="off" maxlength="64"></div>
        <div><label for="new-role">Rolle</label><select id="new-role">
          <option value="admin">Administrator</option>
          <option value="viewer">Nur lesen</option>
        </select></div>
        <div class="full"><label for="new-password">Passwort</label>
          <input id="new-password" type="password" minlength="12" autocomplete="new-password">
          <p class="help-text">Mindestens 12 Zeichen.</p></div>
      </div>
      <div class="form-actions">
        <button id="create" class="primary" type="button">Konto anlegen</button>
      </div>
      <div id="message" class="notice" role="status" hidden></div>
    </section>
    <details class="panel auth-panel">
      <summary>Alternative API-Anmeldung</summary>
      <p class="section-copy">Nur erforderlich, wenn der vorgeschaltete eZEUS-Zugang
        nicht verwendet wird.</p>
      <div class="form-grid auth-fields">
        <div><label for="login-user">Benutzername</label>
          <input id="login-user" autocomplete="username"></div>
        <div><label for="login-password">Passwort</label>
          <input id="login-password" type="password" autocomplete="current-password"></div>
      </div>
      <div class="form-actions"><button id="load" type="button">Konten neu laden</button></div>
    </details>
  </div>
  <section class="panel">
    <div class="section-heading">
      <div><h2>Konten und Rollen</h2>
        <p class="section-copy">Aktive Konten und ihre Zugriffsrechte verwalten.</p></div>
      <span class="status-badge success" id="user-count">Wird geladen</span>
    </div>
    <div id="users" class="loading-state" role="status">Konten werden geladen</div>
  </section>
</div>
"""
    script = """
<script>
  const message=document.getElementById("message");
  const usersRoot=document.getElementById("users");
  function headers(json=false) {
    const username=document.getElementById("login-user").value;
    const password=document.getElementById("login-password").value;
    const result={};
    if(username&&password) {
      result["X-EZEUS-Admin-User"]=username;
      result["X-EZEUS-Admin-Password"]=password;
    }
    if(json) result["Content-Type"]="application/json";
    return result;
  }
  function show(text,error=false) {
    window.ezeusUI?.announce(message,text,error?"error":"success");
  }
  async function load() {
    usersRoot.className="loading-state"; usersRoot.textContent="Konten werden geladen";
    try {
      const response=await fetch("/api/admin-users",{headers:headers()});
      const body=await response.json();
      if(!response.ok) throw new Error(body.detail||`HTTP ${response.status}`);
      usersRoot.replaceChildren(); usersRoot.className="user-list";
      document.getElementById("user-count").textContent=
        `${body.users.length} ${body.users.length===1?"Konto":"Konten"}`;
      if(!body.users.length) {
        usersRoot.className="empty-state"; usersRoot.textContent="Noch keine Konten vorhanden.";
        return;
      }
      body.users.forEach(user=>{
        const card=document.createElement("article"); card.className="user-card";
        const info=document.createElement("div");
        const heading=document.createElement("div"); heading.className="user-title";
        const name=document.createElement("h3"); name.textContent=user.username;
        const badge=document.createElement("span");
        badge.className=`status-badge ${user.enabled?"success":"danger"}`;
        badge.textContent=user.enabled?"Aktiv":"Deaktiviert"; heading.append(name,badge);
        const meta=document.createElement("div"); meta.className="user-meta";
        const roleText=document.createElement("span");
        roleText.textContent=user.role==="admin"?"Vollzugriff":"Nur lesender Zugriff";
        const login=document.createElement("span");
        login.textContent=user.last_login_at?
          `Letzte Anmeldung: ${new Date(user.last_login_at).toLocaleString("de-DE")}`:
          "Noch keine Anmeldung";
        meta.append(roleText,login); info.append(heading,meta);
        const actions=document.createElement("div"); actions.className="user-actions";
        const role=document.createElement("select"); role.setAttribute("aria-label",`Rolle für ${user.username}`);
        role.add(new Option("Administrator","admin")); role.add(new Option("Nur lesen","viewer"));
        role.value=user.role;
        const enabledLabel=document.createElement("label"); enabledLabel.className="toggle-label";
        const enabled=document.createElement("input"); enabled.type="checkbox"; enabled.checked=user.enabled;
        enabled.setAttribute("aria-label",`${user.username} aktiv`);
        enabledLabel.append(enabled,document.createTextNode(" Aktiv"));
        const save=document.createElement("button"); save.className="small primary";
        save.textContent="Speichern";
        save.addEventListener("click",async()=>{
          if(user.enabled&&!enabled.checked&&!confirm(`Konto „${user.username}“ deaktivieren?`)) {
            enabled.checked=true; return;
          }
          window.ezeusUI?.setBusy(save,true,"Speichert …");
          try {
            const result=await fetch(`/api/admin-users/${user.id}`,{
              method:"PATCH",headers:headers(true),
              body:JSON.stringify({role:role.value,enabled:enabled.checked})});
            const body=await result.json();
            show(body.detail||(result.ok?"Konto aktualisiert.":`HTTP ${result.status}`),!result.ok);
            if(result.ok) await load();
          } finally { window.ezeusUI?.setBusy(save,false); }
        });
        actions.append(role,enabledLabel,save); card.append(info,actions); usersRoot.append(card);
      });
    } catch(error) {
      usersRoot.className="notice error"; usersRoot.textContent=`Laden fehlgeschlagen: ${error.message}`;
      document.getElementById("user-count").textContent="Nicht verfügbar";
    }
  }
  async function create() {
    const button=document.getElementById("create"); window.ezeusUI?.setBusy(button,true,"Legt an …");
    try {
      const response=await fetch("/api/admin-users",{method:"POST",headers:headers(true),
        body:JSON.stringify({username:document.getElementById("new-user").value,
          password:document.getElementById("new-password").value,
          role:document.getElementById("new-role").value})});
      const body=await response.json();
      show(body.detail||(response.ok?"Konto wurde angelegt.":`HTTP ${response.status}`),!response.ok);
      if(response.ok) {
        document.getElementById("new-user").value="";
        document.getElementById("new-password").value="";
        await load();
      }
    } finally { window.ezeusUI?.setBusy(button,false); }
  }
  document.getElementById("load").addEventListener("click",load);
  document.getElementById("create").addEventListener("click",create);
  load();
</script>
"""
    return page_shell(
        title="Benutzerverwaltung",
        description=(
            "Persönliche Administrationskonten, Rollen und Aktivstatus "
            "sicher verwalten."
        ),
        active="users",
        content=content,
        script=script,
    )


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
