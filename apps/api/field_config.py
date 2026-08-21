# ruff: noqa: E501

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from apps.api.ui import page_shell
from connectors.base.errors import ConnectorError
from core.db.session import get_db
from core.field_config.schemas import FieldConfigurationSave
from core.field_config.service import FieldConfigurationService
from core.models.paperless_instance import PaperlessInstance
from core.paperless.service import connector_for_instance
from core.security.admin_auth import AdminPrincipal, require_admin_secret, require_admin_user

router = APIRouter(tags=["field-configuration"])


def _instance_or_404(db: Session, slug: str) -> PaperlessInstance:
    instance = FieldConfigurationService(db).instance_by_slug(slug)
    if instance is None:
        raise HTTPException(status_code=404, detail="Paperless-Instanz nicht gefunden")
    return instance


@router.get(
    "/api/instances/{instance_slug}/field-config",
)
async def get_field_configuration(
    instance_slug: str,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[AdminPrincipal, Depends(require_admin_user)],
) -> dict[str, object]:
    service = FieldConfigurationService(db)
    instance = _instance_or_404(db, instance_slug)
    try:
        fields = await service.import_paperless_fields(
            instance,
            connector_for_instance(instance),
            actor=principal.username,
        )
    except ConnectorError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Paperless custom fields could not be loaded: {exc}",
        ) from exc
    return {
        "instance": {"id": str(instance.id), "slug": instance.slug, "name": instance.name},
        "fields": [service.serialize(field) for field in fields],
    }


@router.put(
    "/api/instances/{instance_slug}/field-config",
)
async def save_field_configuration(
    instance_slug: str,
    payload: FieldConfigurationSave,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[AdminPrincipal, Depends(require_admin_secret)],
) -> dict[str, object]:
    service = FieldConfigurationService(db)
    instance = _instance_or_404(db, instance_slug)
    try:
        fields = service.save(instance, payload.fields, actor=principal.username)
        fields = await service.synchronize_paperless_fields(
            instance,
            connector_for_instance(instance),
            actor=principal.username,
        )
    except ConnectorError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Paperless custom fields could not be synchronized: {exc}",
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "instance": {"id": str(instance.id), "slug": instance.slug, "name": instance.name},
        "fields": [service.serialize(field) for field in fields],
    }


@router.post(
    "/api/instances/{instance_slug}/field-config/preview",
)
def preview_field_configuration(
    instance_slug: str,
    payload: FieldConfigurationSave,
    db: Annotated[Session, Depends(get_db)],
    _principal: Annotated[AdminPrincipal, Depends(require_admin_user)],
) -> dict[str, object]:
    instance = _instance_or_404(db, instance_slug)
    fields = sorted(
        (field for field in payload.fields if field.enabled),
        key=lambda field: field.sort_order,
    )
    return {
        "instance": {"slug": instance.slug, "name": instance.name},
        "fields": [
            {
                "field_key": field.field_key,
                "label": field.label,
                "field_type": field.field_type,
                "required": field.required,
                "ocr_enabled": field.ocr_enabled,
                "ai_enabled": field.ai_enabled,
                "options": field.options,
            }
            for field in fields
        ],
    }


@router.get(
    "/admin/instances/{instance_slug}/fields",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def field_configuration_page(instance_slug: str) -> str:
    if not instance_slug:
        raise HTTPException(status_code=404)
    content = """
<div class="content-stack">
  <section class="panel config-context">
    <div class="section-heading">
      <div>
        <h2 id="instance-name">Instanz wird geladen</h2>
        <p class="section-copy">Nur aktive Felder werden von eZEUS-AI-2 extrahiert
          und verarbeitet. Paperless-Felder selbst bleiben unverändert erhalten.</p>
      </div>
      <span id="field-count" class="status-badge warning">Wird geladen</span>
    </div>
    <details class="auth-panel">
      <summary>Alternative API-Anmeldung</summary>
      <div class="form-grid auth-fields">
        <div><label for="username">Benutzername</label>
          <input id="username" autocomplete="username"></div>
        <div><label for="password">Passwort</label>
          <input id="password" type="password" autocomplete="current-password"></div>
      </div>
      <div class="form-actions"><button id="load" type="button">Neu laden</button></div>
    </details>
    <div id="message" class="notice" role="status" hidden></div>
  </section>
  <section class="panel">
    <div class="section-heading">
      <div><h2>Dokumentfelder</h2>
        <p class="section-copy">Reihenfolge, Datentyp, Pflichtstatus sowie OCR- und
          KI-Auslesung für diesen Mandanten festlegen.</p></div>
      <div class="button-row">
        <button id="add" type="button">Feld hinzufügen</button>
        <button id="save" class="primary" type="button">Konfiguration speichern</button>
      </div>
    </div>
    <div id="fields" class="loading-state" role="status">Felder werden geladen</div>
  </section>
  <section class="panel">
    <div class="section-heading">
      <div><h2>Vorschau Dokumentbearbeitung</h2>
        <p class="section-copy">Darstellung der aktuell aktiven Felder vor dem Speichern.</p></div>
      <button id="preview" class="small" type="button">Vorschau aktualisieren</button>
    </div>
    <div id="preview-content" class="preview-grid"></div>
  </section>
</div>
"""
    script = """
<script>
  const slug=decodeURIComponent(location.pathname.split("/").filter(Boolean)[2]||"");
  const fieldsRoot=document.getElementById("fields");
  const previewRoot=document.getElementById("preview-content");
  const message=document.getElementById("message");
  let fields=[]; let initiallyEnabled=new Set();
  const types=[["text","Text"],["number","Zahl"],["money","Geldbetrag"],
    ["date","Datum"],["boolean","Ja/Nein"],["select","Auswahlfeld"],
    ["textarea","Mehrzeiliger Text"]];
  function authHeaders(json=true) {
    const username=document.getElementById("username").value;
    const password=document.getElementById("password").value; const headers={};
    if(username&&password) {
      headers["X-EZEUS-Admin-User"]=username;
      headers["X-EZEUS-Admin-Password"]=password;
    }
    if(json) headers["Content-Type"]="application/json"; return headers;
  }
  function show(text,error=false) {
    window.ezeusUI?.announce(message,text,error?"error":"success");
  }
  function control(label,node,className="") {
    const wrap=document.createElement("div"); if(className) wrap.className=className;
    const caption=document.createElement("label"); caption.textContent=label;
    if(node.id) caption.htmlFor=node.id; wrap.append(caption,node); return wrap;
  }
  function checkbox(field,key,label) {
    const input=document.createElement("input"); input.type="checkbox"; input.checked=field[key];
    input.setAttribute("aria-label",`${label}: ${field.label}`);
    input.addEventListener("change",()=>{field[key]=input.checked;
      if(key==="enabled") render();}); return input;
  }
  function render() {
    fieldsRoot.replaceChildren(); fieldsRoot.className="field-list";
    fields.sort((a,b)=>a.sort_order-b.sort_order).forEach((field,index)=>{
      const row=document.createElement("article");
      row.className=`field-card${field.enabled?"":" inactive"}`;
      const move=document.createElement("div"); move.className="move-controls";
      [["↑","Nach oben",-1],["↓","Nach unten",1]].forEach(([symbol,label,direction])=>{
        const button=document.createElement("button"); button.type="button";
        button.className="small"; button.textContent=symbol;
        button.setAttribute("aria-label",`${field.label} ${label}`);
        button.addEventListener("click",()=>{
          const other=index+direction; if(other<0||other>=fields.length)return;
          [fields[index].sort_order,fields[other].sort_order]=
            [fields[other].sort_order,fields[index].sort_order]; render();
        }); move.append(button);
      }); row.append(move);
      const name=document.createElement("input"); name.value=field.label; name.maxLength=128;
      name.id=`field-name-${index}`; name.addEventListener("input",()=>field.label=name.value);
      const nameControl=control("Bezeichnung",name);
      if(!field.is_standard&&field.external_field_id) {
        const source=document.createElement("span"); source.className="source-badge";
        source.textContent="Paperless-Feld"; nameControl.querySelector("label").append(source);
      } row.append(nameControl);
      const type=document.createElement("select"); type.id=`field-type-${index}`;
      types.forEach(([value,label])=>{
        const option=new Option(label,value); option.selected=field.field_type===value; type.add(option);
      });
      type.addEventListener("change",()=>{field.field_type=type.value;
        if(type.value!=="select")field.options=[]; render();});
      row.append(control("Feldtyp",type));
      [["enabled","In eZEUS"],["required","Pflichtfeld"],["ocr_enabled","OCR"],
        ["ai_enabled","KI"]].forEach(([key,label])=>{
        row.append(control(label,checkbox(field,key,label),"check-control"));
      });
      const external=document.createElement("input"); external.value=field.external_field_id||"";
      external.id=`field-external-${index}`; external.placeholder="Paperless-ID";
      external.addEventListener("input",()=>field.external_field_id=external.value||null);
      row.append(control("Paperless-ID",external));
      const details=document.createElement("div"); details.className="field-details";
      const instructions=document.createElement("textarea");
      instructions.value=field.extraction_instructions||"";
      instructions.id=`field-instructions-${index}`;
      instructions.placeholder="Optionale Hinweise für die KI-Auslesung";
      instructions.addEventListener("input",()=>field.extraction_instructions=
        instructions.value||null);
      details.append(control("Extraktionshinweise",instructions));
      const options=document.createElement("input"); options.value=(field.options||[]).join(", ");
      options.id=`field-options-${index}`; options.disabled=field.field_type!=="select";
      options.placeholder="Option A, Option B";
      options.addEventListener("input",()=>field.options=options.value.split(",")
        .map(value=>value.trim()).filter(Boolean));
      details.append(control("Auswahlwerte",options)); row.append(details); fieldsRoot.append(row);
    });
    const active=fields.filter(field=>field.enabled).length;
    document.getElementById("field-count").textContent=`${active} von ${fields.length} aktiv`;
    document.getElementById("field-count").className="status-badge success";
  }
  function payload() { return {fields:fields.map((field,index)=>({...field,
    sort_order:(index+1)*10,id:undefined,is_standard:undefined}))}; }
  async function load() {
    fieldsRoot.className="loading-state"; fieldsRoot.textContent="Felder werden geladen";
    try {
      const response=await fetch(`/api/instances/${encodeURIComponent(slug)}/field-config`,
        {headers:authHeaders(false)}); const body=await response.json();
      if(!response.ok) throw new Error(body.detail||`HTTP ${response.status}`);
      fields=body.fields; initiallyEnabled=new Set(fields.filter(field=>field.enabled)
        .map(field=>field.field_key));
      document.getElementById("instance-name").textContent=body.instance.name;
      render(); await updatePreview();
    } catch(error) {
      fieldsRoot.className="notice error"; fieldsRoot.textContent=`Laden fehlgeschlagen: ${error.message}`;
      show(error.message,true);
    }
  }
  async function updatePreview() {
    const button=document.getElementById("preview");
    window.ezeusUI?.setBusy(button,true,"Aktualisiert …");
    try {
      const response=await fetch(`/api/instances/${encodeURIComponent(slug)}/field-config/preview`,
        {method:"POST",headers:authHeaders(),body:JSON.stringify(payload())});
      const body=await response.json();
      if(!response.ok) throw new Error(body.detail||"Vorschau ungültig");
      previewRoot.replaceChildren();
      if(!body.fields.length) {
        const empty=document.createElement("div"); empty.className="empty-state";
        empty.textContent="Keine Felder sind in eZEUS aktiv."; previewRoot.append(empty); return;
      }
      body.fields.forEach(field=>{
        const wrap=document.createElement("div"); wrap.className="preview-field";
        const label=document.createElement("label"); label.textContent=field.label;
        if(field.required)label.className="required"; let input;
        if(field.field_type==="textarea") input=document.createElement("textarea");
        else if(field.field_type==="select") {
          input=document.createElement("select");
          field.options.forEach(value=>input.add(new Option(value,value)));
        } else {
          input=document.createElement("input");
          input.type=field.field_type==="date"?"date":
            field.field_type==="number"||field.field_type==="money"?"number":
            field.field_type==="boolean"?"checkbox":"text";
        }
        input.disabled=true; wrap.append(label,input); previewRoot.append(wrap);
      });
    } catch(error) { show(error.message,true); }
    finally { window.ezeusUI?.setBusy(button,false); }
  }
  async function save() {
    const disabled=fields.filter(field=>!field.enabled&&initiallyEnabled.has(field.field_key));
    if(disabled.length&&!confirm(`${disabled.length} bisher aktive Felder werden in eZEUS deaktiviert. Fortfahren?`)) return;
    const button=document.getElementById("save"); window.ezeusUI?.setBusy(button,true,"Speichert …");
    try {
      const response=await fetch(`/api/instances/${encodeURIComponent(slug)}/field-config`,{
        method:"PUT",headers:authHeaders(),body:JSON.stringify(payload())});
      const body=await response.json();
      if(!response.ok) throw new Error(body.detail||"Speichern fehlgeschlagen");
      fields=body.fields; initiallyEnabled=new Set(fields.filter(field=>field.enabled)
        .map(field=>field.field_key));
      show("Mandantenkonfiguration wurde gespeichert."); render(); await updatePreview();
    } catch(error) { show(error.message,true); }
    finally { window.ezeusUI?.setBusy(button,false); }
  }
  document.getElementById("load").addEventListener("click",load);
  document.getElementById("preview").addEventListener("click",updatePreview);
  document.getElementById("save").addEventListener("click",save);
  document.getElementById("add").addEventListener("click",()=>{
    fields.push({field_key:null,label:"Neues Feld",field_type:"text",
      sort_order:(fields.length+1)*10,is_standard:false,enabled:true,required:false,
      ocr_enabled:true,ai_enabled:false,external_field_id:null,options:[],
      extraction_instructions:null}); render();
  });
  load();
</script>
"""
    return page_shell(
        title="Feldkonfiguration",
        description=(
            "Dokumentfelder ausschließlich für die ausgewählte "
            "Kundeninstanz konfigurieren und vorab prüfen."
        ),
        active="instances",
        content=content,
        script=script,
        eyebrow="Mandantenkonfiguration",
    )
