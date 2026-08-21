import re
import secrets
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import AnyHttpUrl, BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.ui import page_shell
from connectors.base.errors import ConnectorError
from connectors.paperless.connector import PaperlessConnector
from core.config.settings import get_settings
from core.db.session import get_db
from core.field_config.service import FieldConfigurationService
from core.models.audit import AuditEntry
from core.models.paperless_instance import PaperlessInstance
from core.security.admin_auth import AdminPrincipal, require_admin_secret
from core.security.credentials import (
    CredentialEncryptionError,
    decrypt_credential,
    encrypt_credential,
)

router = APIRouter(tags=["paperless-instances"])
SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


class InstanceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_url: AnyHttpUrl
    api_token: str = Field(min_length=1, max_length=4096)
    webhook_secret: str | None = Field(default=None, min_length=16, max_length=4096)


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


def _instance_slug(base_url: str, db: Session) -> str:
    hostname = urlparse(base_url).hostname or "paperless"
    base_slug = re.sub(r"[^a-z0-9]+", "-", hostname.lower()).strip("-")[:64]
    base_slug = base_slug or "paperless"
    slug = base_slug
    suffix = 2
    while db.scalar(select(PaperlessInstance.id).where(PaperlessInstance.slug == slug)):
        suffix_text = f"-{suffix}"
        slug = f"{base_slug[: 64 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return _validate_slug(slug)


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


def _workflow_url(instance: PaperlessInstance) -> str:
    public_base_url = get_settings().public_webhook_base_url.rstrip("/")
    if not public_base_url:
        raise ConnectorError("PUBLIC_WEBHOOK_BASE_URL ist nicht konfiguriert")
    return f"{public_base_url}/webhooks/paperless/{instance.slug}"


async def _provision_workflow(instance: PaperlessInstance) -> dict[str, object]:
    connector = PaperlessConnector(
        base_url=instance.base_url,
        api_token=decrypt_credential(instance.api_token_encrypted),
        verify_tls=instance.verify_tls,
    )
    if not await connector.health_check():
        raise ConnectorError("Paperless-Verbindung ist nicht erreichbar")
    return await connector.ensure_ezeus_workflow(
        webhook_url=_workflow_url(instance),
        webhook_secret=decrypt_credential(instance.webhook_secret_encrypted),
    )


@router.get(
    "/api/paperless-instances",
    dependencies=[Depends(require_admin_secret)],
)
def list_instances(db: Annotated[Session, Depends(get_db)]) -> dict[str, object]:
    instances = db.scalars(select(PaperlessInstance).order_by(PaperlessInstance.name)).all()
    return {"instances": [_serialize(item) for item in instances]}


@router.post(
    "/api/paperless-instances",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_secret)],
)
async def create_instance(
    payload: InstanceCreate,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    base_url = str(payload.base_url).rstrip("/")
    slug = _instance_slug(base_url, db)
    webhook_secret = payload.webhook_secret or secrets.token_urlsafe(32)
    instance = PaperlessInstance(
        name=payload.name.strip(),
        slug=slug,
        base_url=base_url,
        api_token_encrypted=encrypt_credential(payload.api_token),
        webhook_secret_encrypted=encrypt_credential(webhook_secret),
        verify_tls=True,
        enabled=True,
    )
    db.add(instance)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Kennung ist bereits vergeben") from exc
    db.refresh(instance)
    FieldConfigurationService(db).ensure_defaults(instance)
    result = _serialize(instance)
    if get_settings().public_webhook_base_url:
        try:
            result["workflow"] = await _provision_workflow(instance)
        except (ConnectorError, CredentialEncryptionError) as exc:
            db.delete(instance)
            db.commit()
            raise HTTPException(
                status_code=502,
                detail=(
                    "Instanz nicht angelegt: Paperless-Workflow konnte nicht "
                    f"eingerichtet werden: {exc}"
                ),
            ) from exc
    return result


@router.patch(
    "/api/paperless-instances/{instance_id}",
)
def update_instance(
    instance_id: UUID,
    payload: InstanceUpdate,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[AdminPrincipal, Depends(require_admin_secret)],
) -> dict[str, object]:
    instance = db.get(PaperlessInstance, instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Paperless-Instanz nicht gefunden")
    changes = payload.model_dump(exclude_unset=True)
    old_value = {
        "name": instance.name,
        "base_url": instance.base_url,
        "verify_tls": instance.verify_tls,
        "enabled": instance.enabled,
        "has_api_token": bool(instance.api_token_encrypted),
        "has_webhook_secret": bool(instance.webhook_secret_encrypted),
    }
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
    new_value = {
        "name": instance.name,
        "base_url": instance.base_url,
        "verify_tls": instance.verify_tls,
        "enabled": instance.enabled,
        "has_api_token": bool(instance.api_token_encrypted),
        "has_webhook_secret": bool(instance.webhook_secret_encrypted),
        "api_token_replaced": "api_token" in changes,
        "webhook_secret_replaced": "webhook_secret" in changes,
    }
    db.add(
        AuditEntry(
            actor=principal.username,
            action="UPDATE_PAPERLESS_INSTANCE",
            entity_type="paperless_instance",
            entity_id=str(instance.id),
            instance_id=instance.id,
            target_system="paperless",
            old_value=old_value,
            new_value=new_value,
        )
    )
    db.commit()
    db.refresh(instance)
    return _serialize(instance)


@router.delete(
    "/api/paperless-instances/{instance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_instance(
    instance_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[AdminPrincipal, Depends(require_admin_secret)],
) -> None:
    instance = db.get(PaperlessInstance, instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Paperless-Instanz nicht gefunden")
    if instance.enabled:
        raise HTTPException(
            status_code=409,
            detail="Aktive Paperless-Instanzen müssen vor dem Löschen deaktiviert werden",
        )

    deleted_instance = {
        "id": str(instance.id),
        "name": instance.name,
        "slug": instance.slug,
        "base_url": instance.base_url,
        "verify_tls": instance.verify_tls,
        "enabled": instance.enabled,
    }
    # Historische Audit-Einträge bleiben erhalten, dürfen die endgültige
    # Löschung der Instanz aber nicht über ihren Fremdschlüssel blockieren.
    db.execute(
        update(AuditEntry).where(AuditEntry.instance_id == instance.id).values(instance_id=None)
    )
    db.add(
        AuditEntry(
            actor=principal.username,
            action="DELETE_PAPERLESS_INSTANCE",
            entity_type="paperless_instance",
            entity_id=str(instance.id),
            target_system="paperless",
            old_value=deleted_instance,
            new_value=None,
            details={"deleted_instance": deleted_instance},
        )
    )
    db.delete(instance)
    db.commit()


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
        return {"reachable": False, "webhook_configured": False, "detail": str(exc)}

    try:
        webhook_url = _workflow_url(instance)
        workflow = await connector.find_webhook_workflow(webhook_url)
    except (ConnectorError, CredentialEncryptionError) as exc:
        return {
            "reachable": reachable,
            "webhook_configured": False,
            "detail": f"Verbindung erfolgreich, Workflow-Prüfung fehlgeschlagen: {exc}",
        }

    if workflow is None:
        return {
            "reachable": reachable,
            "webhook_configured": False,
            "detail": (
                "Verbindung erfolgreich, aber kein Workflow in Paperless gefunden, "
                f"dessen Webhook-Ziel auf {webhook_url} zeigt. Lege dort einen "
                "Workflow mit Webhook-Aktion auf genau diese Adresse an, "
                "ausgelöst nur durch „Dokument hinzugefügt“."
            ),
        }

    trigger_types = workflow["trigger_types"]
    has_update_trigger = isinstance(trigger_types, list) and 3 in trigger_types
    workflow_name = workflow["workflow_name"]
    problems: list[str] = []
    if not workflow["enabled"]:
        problems.append("der Workflow ist deaktiviert")
    if has_update_trigger:
        problems.append(
            "der Workflow reagiert auch auf „Dokument geändert“ – das kann eine "
            "Endlosschleife auslösen, weil eZEUS' eigenes Zurückschreiben der "
            "erkannten Felder selbst als Änderung zählt. Nur „Dokument "
            "hinzugefügt“ auswählen."
        )
    webhook_configured = bool(workflow["enabled"]) and not has_update_trigger
    if problems:
        detail = f"Workflow „{workflow_name}“ gefunden, aber: " + "; ".join(problems)
    else:
        detail = f"Verbindung erfolgreich, Workflow „{workflow_name}“ korrekt eingerichtet."
    return {
        "reachable": reachable,
        "webhook_configured": webhook_configured,
        "workflow_id": workflow["workflow_id"],
        "workflow_name": workflow["workflow_name"],
        "workflow_enabled": workflow["enabled"],
        "has_update_trigger_warning": has_update_trigger,
        "detail": detail,
    }


@router.post(
    "/api/paperless-instances/{instance_id}/provision-workflow",
    dependencies=[Depends(require_admin_secret)],
)
async def provision_instance_workflow(
    instance_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    instance = db.get(PaperlessInstance, instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Paperless-Instanz nicht gefunden")
    try:
        workflow = await _provision_workflow(instance)
    except (ConnectorError, CredentialEncryptionError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Paperless-Workflow konnte nicht eingerichtet werden: {exc}",
        ) from exc
    return {
        **workflow,
        "detail": "Paperless-Workflow wurde geprüft und vollständig eingerichtet.",
    }


@router.get("/admin/instances", response_class=HTMLResponse, include_in_schema=False)
def instance_admin_page() -> str:
    content = """
<div class="grid sidebar-layout">
  <div class="content-stack">
    <section class="panel">
      <div class="section-heading">
        <div>
          <h2>Neue Paperless-Instanz</h2>
          <p class="section-copy">Mandant und verschlüsselte Zugangsdaten vollständig anlegen.</p>
        </div>
      </div>
      <form id="instance-form">
        <div class="form-grid">
          <div class="full"><label for="name">Bezeichnung</label>
            <input id="name" required maxlength="255" placeholder="Kundenname"></div>
          <div class="full"><label for="base-url">Paperless-URL</label>
            <input id="base-url" type="url" required placeholder="https://paperless.example.de"></div>
          <div><label for="api-token">API-Token</label>
            <input id="api-token" type="password" required autocomplete="new-password"></div>
          <div><label>Webhook-Authentifizierung</label>
            <p class="help-text">eZEUS erzeugt das Secret sicher und richtet den
              Paperless-Workflow automatisch ein.</p></div>
        </div>
        <div class="form-actions">
          <button class="primary" id="save-instance" type="submit">Instanz speichern</button>
        </div>
      </form>
      <div id="message" class="notice" role="status" hidden></div>
    </section>
    <details class="panel auth-panel">
      <summary>Alternative API-Anmeldung</summary>
      <p class="section-copy">Nur erforderlich, wenn keine Anmeldung über den
        vorgeschalteten eZEUS-Zugang erfolgt.</p>
      <div class="form-grid auth-fields">
        <div><label for="admin-username">Benutzername</label>
          <input id="admin-username" autocomplete="username"></div>
        <div><label for="admin-password">Passwort</label>
          <input id="admin-password" type="password" autocomplete="current-password"></div>
      </div>
    </details>
  </div>
  <section class="panel">
    <div class="section-heading">
      <div>
        <h2>Konfigurierte Instanzen</h2>
        <p class="section-copy">Verbindungen prüfen und kundenspezifische Felder verwalten.</p>
      </div>
      <span class="status-badge success" id="instance-count">Wird geladen</span>
    </div>
    <div id="instances" class="loading-state" role="status">Instanzen werden geladen</div>
  </section>
</div>
<dialog id="edit-instance-dialog" class="edit-dialog" aria-labelledby="edit-instance-title">
  <form id="edit-instance-form" method="dialog">
    <div class="dialog-heading">
      <div>
        <p class="eyebrow">Instanzkonfiguration</p>
        <h2 id="edit-instance-title">Paperless-Instanz bearbeiten</h2>
        <p class="section-copy">Zugangsdaten werden nur ersetzt, wenn ein neuer Wert
          eingegeben wird.</p>
      </div>
      <button id="close-edit-dialog" class="icon-button" type="button"
        aria-label="Dialog schließen">×</button>
    </div>
    <div class="form-grid">
      <div class="full"><label for="edit-name">Bezeichnung</label>
        <input id="edit-name" required maxlength="255"></div>
      <div class="full"><label for="edit-base-url">Paperless-URL</label>
        <input id="edit-base-url" type="url" required></div>
      <div><label for="edit-api-token">Neuer API-Token</label>
        <input id="edit-api-token" type="password" autocomplete="new-password"
          placeholder="Unverändert lassen">
        <p class="help-text">Leer lassen, um den gespeicherten Token beizubehalten.</p></div>
      <div><label for="edit-webhook-secret">Neues Webhook-Secret</label>
        <input id="edit-webhook-secret" type="password" minlength="16"
          autocomplete="new-password" placeholder="Unverändert lassen">
        <p class="help-text">Leer lassen, um das gespeicherte Secret beizubehalten.</p></div>
      <div class="full">
        <label class="toggle-label" for="edit-verify-tls">
          <input id="edit-verify-tls" type="checkbox"> TLS-Zertifikat prüfen
        </label>
      </div>
    </div>
    <div id="edit-message" class="notice" role="status" hidden></div>
    <div class="form-actions dialog-actions">
      <button id="cancel-edit-instance" type="button">Abbrechen</button>
      <button id="save-edit-instance" class="primary" type="submit">Änderungen speichern</button>
    </div>
  </form>
</dialog>
"""
    script = """
<script>
  const message=document.getElementById("message");
  const instances=document.getElementById("instances");
  const editDialog=document.getElementById("edit-instance-dialog");
  const editMessage=document.getElementById("edit-message");
  let editingInstance=null;
  function headers(json=false) {
    const username=document.getElementById("admin-username").value;
    const password=document.getElementById("admin-password").value;
    const result={};
    if(username&&password) {
      result["X-EZEUS-Admin-User"]=username;
      result["X-EZEUS-Admin-Password"]=password;
    }
    if(json) result["Content-Type"]="application/json";
    return result;
  }
  function showMessage(text,error=false) {
    window.ezeusUI?.announce(message,text,error?"error":"success");
  }
  function showEditMessage(text,error=false) {
    window.ezeusUI?.announce(editMessage,text,error?"error":"success");
  }
  function openEditDialog(item) {
    editingInstance=item;
    document.getElementById("edit-name").value=item.name;
    document.getElementById("edit-base-url").value=item.base_url;
    document.getElementById("edit-api-token").value="";
    document.getElementById("edit-webhook-secret").value="";
    document.getElementById("edit-verify-tls").checked=item.verify_tls;
    editMessage.hidden=true;
    editDialog.showModal();
    document.getElementById("edit-name").focus();
  }
  function closeEditDialog() {
    editDialog.close(); editingInstance=null;
  }
  function webhookUrl(path) { return `${location.protocol}//${location.host}${path}`; }
  function actionButton(label,className,handler) {
    const button=document.createElement("button"); button.type="button";
    button.className=`small ${className||""}`; button.textContent=label;
    button.addEventListener("click",handler); return button;
  }
  async function loadInstances() {
    instances.className="loading-state"; instances.textContent="Instanzen werden geladen";
    try {
      const response=await fetch("/api/paperless-instances",{headers:headers()});
      if(!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload=await response.json(); instances.replaceChildren();
      document.getElementById("instance-count").textContent=
        `${payload.instances.length} ${payload.instances.length===1?"Instanz":"Instanzen"}`;
      if(!payload.instances.length) {
        instances.className="empty-state";
        instances.textContent="Noch keine Paperless-Instanz konfiguriert."; return;
      }
      instances.className="instance-list";
      payload.instances.forEach((item)=>{
        const card=document.createElement("article"); card.className="instance-card";
        const info=document.createElement("div");
        const heading=document.createElement("div"); heading.className="instance-title";
        const title=document.createElement("h3"); title.textContent=item.name;
        const badge=document.createElement("span");
        badge.className=`status-badge ${item.enabled?"success":"danger"}`;
        badge.textContent=item.enabled?"Aktiv":"Deaktiviert"; heading.append(title,badge);
        const meta=document.createElement("div"); meta.className="instance-meta";
        const url=document.createElement("span"); url.textContent=item.base_url;
        const webhook=document.createElement("span"); webhook.className="mono";
        webhook.textContent=item.webhook_url||webhookUrl(item.webhook_path);
        meta.append(url,webhook); info.append(heading,meta);
        const actions=document.createElement("div"); actions.className="instance-actions";
        actions.append(
          actionButton("Bearbeiten","",()=>openEditDialog(item)),
          actionButton("Felder","primary",()=>{
            location.href=`/admin/instances/${encodeURIComponent(item.slug)}/fields`;
          }),
          actionButton("Verbindung testen","",async(event)=>{
            const button=event.currentTarget; window.ezeusUI?.setBusy(button,true,"Prüfung …");
            try {
              const result=await fetch(`/api/paperless-instances/${item.id}/test`,
                {method:"POST",headers:headers()});
              const body=await result.json();
              const ok=body.reachable&&body.webhook_configured;
              showMessage(body.detail||`HTTP ${result.status}`,!ok);
            } finally { window.ezeusUI?.setBusy(button,false); }
          }),
          actionButton("Workflow einrichten","",async(event)=>{
            const button=event.currentTarget; window.ezeusUI?.setBusy(button,true,"Einrichtung …");
            try {
              const result=await fetch(
                `/api/paperless-instances/${item.id}/provision-workflow`,
                {method:"POST",headers:headers()});
              const body=await result.json();
              showMessage(body.detail||`HTTP ${result.status}`,!result.ok);
            } finally { window.ezeusUI?.setBusy(button,false); }
          }),
          actionButton(item.enabled?"Deaktivieren":"Aktivieren",item.enabled?"danger":"",async()=>{
            if(item.enabled&&!confirm(`Instanz „${item.name}“ wirklich deaktivieren?`)) return;
            const result=await fetch(`/api/paperless-instances/${item.id}`,{
              method:"PATCH",headers:headers(true),body:JSON.stringify({enabled:!item.enabled})
            });
            if(!result.ok) {
              showMessage(`Änderung fehlgeschlagen: HTTP ${result.status}`,true);
              return;
            }
            showMessage(`Instanz wurde ${item.enabled?"deaktiviert":"aktiviert"}.`);
            await loadInstances();
          })
        );
        if(!item.enabled) {
          actions.append(actionButton("Endgültig löschen","danger",async()=>{
            if(!confirm(
              `Instanz „${item.name}“ endgültig löschen? Die Zugangsdaten und `+
              `Feldkonfigurationen werden unwiderruflich entfernt.`
            )) return;
            const result=await fetch(`/api/paperless-instances/${item.id}`,{
              method:"DELETE",headers:headers()
            });
            if(!result.ok) {
              let detail=`Löschen fehlgeschlagen: HTTP ${result.status}`;
              try { detail=(await result.json()).detail||detail; } catch(error) {}
              showMessage(detail,true); return;
            }
            showMessage(`Instanz „${item.name}“ wurde endgültig gelöscht.`);
            await loadInstances();
          }));
        }
        card.append(info,actions); instances.append(card);
      });
    } catch(error) {
      instances.className="notice error";
      instances.textContent=`Laden fehlgeschlagen: ${error.message}`;
      document.getElementById("instance-count").textContent="Nicht verfügbar";
    }
  }
  document.getElementById("instance-form").addEventListener("submit",async(event)=>{
    event.preventDefault(); const button=document.getElementById("save-instance");
    window.ezeusUI?.setBusy(button,true,"Speichert …");
    const payload={name:document.getElementById("name").value,
      base_url:document.getElementById("base-url").value,
      api_token:document.getElementById("api-token").value};
    try {
      const response=await fetch("/api/paperless-instances",{
        method:"POST",headers:headers(true),body:JSON.stringify(payload)});
      const body=await response.json();
      if(!response.ok) {
        showMessage(body.detail||`Speichern fehlgeschlagen: HTTP ${response.status}`,true);
        return;
      }
      event.target.reset();
      showMessage("Instanz und Paperless-Workflow wurden vollständig eingerichtet.");
      await loadInstances();
    } finally { window.ezeusUI?.setBusy(button,false); }
  });
  document.getElementById("close-edit-dialog").addEventListener("click",closeEditDialog);
  document.getElementById("cancel-edit-instance").addEventListener("click",closeEditDialog);
  editDialog.addEventListener("click",(event)=>{
    if(event.target===editDialog) closeEditDialog();
  });
  document.getElementById("edit-instance-form").addEventListener("submit",async(event)=>{
    event.preventDefault();
    if(!editingInstance) return;
    const button=document.getElementById("save-edit-instance");
    const apiToken=document.getElementById("edit-api-token").value;
    const webhookSecret=document.getElementById("edit-webhook-secret").value;
    const payload={
      name:document.getElementById("edit-name").value,
      base_url:document.getElementById("edit-base-url").value,
      verify_tls:document.getElementById("edit-verify-tls").checked
    };
    if(apiToken) payload.api_token=apiToken;
    if(webhookSecret) payload.webhook_secret=webhookSecret;
    window.ezeusUI?.setBusy(button,true,"Speichert …");
    try {
      const response=await fetch(`/api/paperless-instances/${editingInstance.id}`,{
        method:"PATCH",headers:headers(true),body:JSON.stringify(payload)
      });
      const body=await response.json();
      if(!response.ok) {
        showEditMessage(body.detail||`Speichern fehlgeschlagen: HTTP ${response.status}`,true);
        return;
      }
      closeEditDialog();
      showMessage(`Instanz „${body.name}“ wurde aktualisiert.`);
      await loadInstances();
    } finally { window.ezeusUI?.setBusy(button,false); }
  });
  loadInstances();
</script>
"""
    return page_shell(
        title="Paperless-Instanzen",
        description=(
            "Kundenverbindungen, Webhooks und mandantenbezogene "
            "Feldkonfigurationen zentral verwalten."
        ),
        active="instances",
        content=content,
        script=script,
    )
