import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import AnyHttpUrl, BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.admin import require_admin_secret
from connectors.base.errors import ConnectorError
from connectors.paperless.connector import PaperlessConnector
from core.config.settings import get_settings
from core.db.session import get_db
from core.models.paperless_instance import PaperlessInstance
from core.security.credentials import (
    CredentialEncryptionError,
    decrypt_credential,
    encrypt_credential,
)

router = APIRouter(tags=["paperless-instances"])
SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


class InstanceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=64)
    base_url: AnyHttpUrl
    api_token: str = Field(min_length=1, max_length=4096)
    webhook_secret: str = Field(min_length=16, max_length=4096)
    verify_tls: bool = True
    enabled: bool = True


class InstanceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    base_url: AnyHttpUrl | None = None
    api_token: str | None = Field(default=None, min_length=1, max_length=4096)
    webhook_secret: str | None = Field(default=None, min_length=16, max_length=4096)
    verify_tls: bool | None = None
    enabled: bool | None = None


def _validate_slug(slug: str) -> str:
    normalized = slug.strip().lower()
    if not SLUG_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=422,
            detail="Kennung darf nur Kleinbuchstaben, Zahlen und Bindestriche enthalten",
        )
    return normalized


def _serialize(instance: PaperlessInstance) -> dict[str, object]:
    webhook_path = f"/webhooks/paperless/{instance.slug}"
    public_base_url = get_settings().public_webhook_base_url.rstrip("/")
    return {
        "id": str(instance.id),
        "name": instance.name,
        "slug": instance.slug,
        "base_url": instance.base_url,
        "verify_tls": instance.verify_tls,
        "enabled": instance.enabled,
        "has_api_token": bool(instance.api_token_encrypted),
        "has_webhook_secret": bool(instance.webhook_secret_encrypted),
        "created_at": instance.created_at.isoformat(),
        "updated_at": instance.updated_at.isoformat(),
        "webhook_path": webhook_path,
        "webhook_url": f"{public_base_url}{webhook_path}" if public_base_url else None,
    }


@router.get("/api/paperless-instances", dependencies=[Depends(require_admin_secret)])
def list_instances(db: Annotated[Session, Depends(get_db)]) -> dict[str, object]:
    instances = db.scalars(select(PaperlessInstance).order_by(PaperlessInstance.name)).all()
    return {"instances": [_serialize(item) for item in instances]}


@router.post(
    "/api/paperless-instances",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_secret)],
)
def create_instance(
    payload: InstanceCreate,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    instance = PaperlessInstance(
        name=payload.name.strip(),
        slug=_validate_slug(payload.slug),
        base_url=str(payload.base_url).rstrip("/"),
        api_token_encrypted=encrypt_credential(payload.api_token),
        webhook_secret_encrypted=encrypt_credential(payload.webhook_secret),
        verify_tls=payload.verify_tls,
        enabled=payload.enabled,
    )
    db.add(instance)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Kennung ist bereits vergeben") from exc
    db.refresh(instance)
    return _serialize(instance)


@router.patch(
    "/api/paperless-instances/{instance_id}",
    dependencies=[Depends(require_admin_secret)],
)
def update_instance(
    instance_id: UUID,
    payload: InstanceUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    instance = db.get(PaperlessInstance, instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Paperless-Instanz nicht gefunden")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        instance.name = str(changes["name"]).strip()
    if "base_url" in changes:
        instance.base_url = str(changes["base_url"]).rstrip("/")
    if "api_token" in changes:
        instance.api_token_encrypted = encrypt_credential(str(changes["api_token"]))
    if "webhook_secret" in changes:
        instance.webhook_secret_encrypted = encrypt_credential(str(changes["webhook_secret"]))
    if "verify_tls" in changes:
        instance.verify_tls = bool(changes["verify_tls"])
    if "enabled" in changes:
        instance.enabled = bool(changes["enabled"])
    db.commit()
    db.refresh(instance)
    return _serialize(instance)


@router.post(
    "/api/paperless-instances/{instance_id}/test",
    dependencies=[Depends(require_admin_secret)],
)
async def test_instance(
    instance_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    instance = db.get(PaperlessInstance, instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Paperless-Instanz nicht gefunden")
    try:
        connector = PaperlessConnector(
            base_url=instance.base_url,
            api_token=decrypt_credential(instance.api_token_encrypted),
            verify_tls=instance.verify_tls,
        )
        reachable = await connector.health_check()
    except (ConnectorError, CredentialEncryptionError) as exc:
        return {"reachable": False, "detail": str(exc)}
    return {"reachable": reachable, "detail": "Verbindung erfolgreich"}


INSTANCE_ADMIN_HTML = """<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Paperless-Instanzen | eZEUS-AI-2</title>
  <style>
    :root { color-scheme: dark; --bg:#0b1020; --panel:#141b2d; --soft:#1a2338;
      --text:#f4f7ff; --muted:#9ca9c4; --accent:#65d6ad; --border:#2a3550;
      --error:#ff7b86; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text);
      font:15px/1.5 Inter,system-ui,sans-serif; }
    header { padding:1rem clamp(1rem,4vw,3rem); border-bottom:1px solid var(--border);
      display:flex; justify-content:space-between; align-items:center; gap:1rem; }
    header a { color:var(--accent); text-decoration:none; }
    main { width:min(1080px,calc(100% - 2rem)); margin:2rem auto 4rem; }
    .panel { background:var(--panel); border:1px solid var(--border); border-radius:1rem;
      padding:1.25rem; margin-bottom:1rem; }
    h1,h2 { margin-top:0; }
    .muted { color:var(--muted); }
    .grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem; }
    label { display:block; color:var(--muted); margin-bottom:.3rem; }
    input { width:100%; padding:.7rem; border:1px solid var(--border); border-radius:.6rem;
      color:var(--text); background:var(--soft); font:inherit; }
    .wide { grid-column:1/-1; }
    .checks { display:flex; gap:1.5rem; align-items:center; }
    .checks label { color:var(--text); margin:0; }
    .checks input { width:auto; margin-right:.4rem; }
    button { border:0; border-radius:.6rem; background:var(--accent); color:#08111b;
      padding:.7rem 1rem; font:inherit; font-weight:700; cursor:pointer; }
    button.secondary { background:var(--soft); color:var(--text); border:1px solid var(--border); }
    .instance { display:grid; grid-template-columns:1fr auto; gap:1rem; padding:1rem 0;
      border-bottom:1px solid var(--border); }
    .instance:last-child { border:0; }
    code { word-break:break-all; color:var(--accent); }
    .actions { display:flex; gap:.5rem; align-items:start; }
    #message { min-height:1.5rem; margin:.8rem 0; color:var(--accent); }
    #message.error { color:var(--error); }
    @media(max-width:700px) { .grid { grid-template-columns:1fr; } .wide { grid-column:auto; }
      .instance { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header><strong>eZEUS-AI-2 Verwaltung</strong><a href="/">Zur Übersicht</a></header>
  <main>
    <h1>Paperless-Instanzen</h1>
    <p class="muted">Zugangsdaten werden verschlüsselt gespeichert und nicht angezeigt.</p>
    <section class="panel">
      <h2>Administrativer Zugriff</h2>
      <label for="admin-secret">Admin-Secret</label>
      <input id="admin-secret" type="password" autocomplete="current-password">
    </section>
    <section class="panel">
      <h2>Instanz hinzufügen</h2>
      <form id="instance-form" class="grid">
        <div><label for="name">Name</label><input id="name" required maxlength="255"></div>
        <div><label for="slug">Eindeutige Kennung</label>
          <input id="slug" required pattern="[a-z0-9][a-z0-9-]{0,63}"></div>
        <div class="wide"><label for="base-url">Paperless-URL</label>
          <input id="base-url" type="url" required placeholder="https://paperless.example.de"></div>
        <div><label for="api-token">API-Token</label>
          <input id="api-token" type="password" required autocomplete="new-password"></div>
        <div><label for="webhook-secret">Webhook-Secret (mindestens 16 Zeichen)</label>
          <input id="webhook-secret" type="password" required minlength="16"
            autocomplete="new-password"></div>
        <div class="wide checks">
          <label><input id="verify-tls" type="checkbox" checked>TLS-Zertifikat prüfen</label>
          <label><input id="enabled" type="checkbox" checked>Instanz aktiv</label>
        </div>
        <div class="wide"><button type="submit">Instanz speichern</button></div>
      </form>
      <div id="message"></div>
    </section>
    <section class="panel">
      <h2>Konfigurierte Instanzen</h2>
      <div id="instances" class="muted">Admin-Secret eingeben, um Instanzen zu laden.</div>
    </section>
  </main>
  <script>
    const secretInput = document.getElementById("admin-secret");
    const message = document.getElementById("message");
    const instances = document.getElementById("instances");
    secretInput.value = sessionStorage.getItem("ezeusAdminSecret") || "";

    function headers(json = false) {
      const result = {"X-EZEUS-Admin-Secret": secretInput.value};
      if (json) result["Content-Type"] = "application/json";
      return result;
    }
    function showMessage(text, error = false) {
      message.textContent = text;
      message.classList.toggle("error", error);
    }
    function webhookUrl(path) {
      return `${location.protocol}//${location.host}${path}`;
    }
    async function loadInstances() {
      if (!secretInput.value) return;
      sessionStorage.setItem("ezeusAdminSecret", secretInput.value);
      const response = await fetch("/api/paperless-instances", {headers:headers()});
      if (!response.ok) {
        instances.textContent = response.status === 401
          ? "Admin-Secret ist ungültig." : `Laden fehlgeschlagen: HTTP ${response.status}`;
        return;
      }
      const payload = await response.json();
      instances.replaceChildren();
      if (!payload.instances.length) {
        instances.textContent = "Noch keine Instanz konfiguriert.";
        return;
      }
      payload.instances.forEach((item) => {
        const row = document.createElement("div");
        row.className = "instance";
        const info = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = `${item.name} (${item.enabled ? "aktiv" : "deaktiviert"})`;
        const url = document.createElement("div");
        url.textContent = item.base_url;
        const webhook = document.createElement("code");
        webhook.textContent = item.webhook_url || webhookUrl(item.webhook_path);
        info.append(title, url, webhook);
        const actions = document.createElement("div");
        actions.className = "actions";
        const test = document.createElement("button");
        test.type = "button";
        test.className = "secondary";
        test.textContent = "Verbindung testen";
        test.addEventListener("click", async () => {
          test.disabled = true;
          const result = await fetch(`/api/paperless-instances/${item.id}/test`,
            {method:"POST", headers:headers()});
          const body = await result.json();
          showMessage(body.detail || `HTTP ${result.status}`, !body.reachable);
          test.disabled = false;
        });
        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "secondary";
        toggle.textContent = item.enabled ? "Deaktivieren" : "Aktivieren";
        toggle.addEventListener("click", async () => {
          await fetch(`/api/paperless-instances/${item.id}`, {
            method:"PATCH", headers:headers(true),
            body:JSON.stringify({enabled:!item.enabled})
          });
          await loadInstances();
        });
        actions.append(test, toggle);
        row.append(info, actions);
        instances.append(row);
      });
    }
    secretInput.addEventListener("change", loadInstances);
    document.getElementById("instance-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!secretInput.value) { showMessage("Admin-Secret fehlt.", true); return; }
      const payload = {
        name:document.getElementById("name").value,
        slug:document.getElementById("slug").value,
        base_url:document.getElementById("base-url").value,
        api_token:document.getElementById("api-token").value,
        webhook_secret:document.getElementById("webhook-secret").value,
        verify_tls:document.getElementById("verify-tls").checked,
        enabled:document.getElementById("enabled").checked
      };
      const response = await fetch("/api/paperless-instances", {
        method:"POST", headers:headers(true), body:JSON.stringify(payload)
      });
      if (!response.ok) {
        const body = await response.json();
        showMessage(body.detail || `Speichern fehlgeschlagen: HTTP ${response.status}`, true);
        return;
      }
      event.target.reset();
      document.getElementById("verify-tls").checked = true;
      document.getElementById("enabled").checked = true;
      showMessage("Instanz wurde gespeichert.");
      await loadInstances();
    });
    loadInstances();
  </script>
</body>
</html>
"""


@router.get("/admin/instances", response_class=HTMLResponse, include_in_schema=False)
def instance_admin_page() -> str:
    return INSTANCE_ADMIN_HTML
