# ruff: noqa: E501

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from connectors.base.errors import ConnectorError
from core.db.session import get_db
from core.field_config.schemas import FieldConfigurationSave
from core.field_config.service import FieldConfigurationService
from core.models.paperless_instance import PaperlessInstance
from core.paperless.service import connector_for_instance
from core.security.admin_auth import AdminPrincipal, require_admin_secret, require_admin_user

router = APIRouter(tags=["field-configuration"])


def _instance_or_404(
    db: Session, slug: str
) -> PaperlessInstance:
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


FIELD_CONFIG_HTML = """<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Feldkonfiguration | eZEUS-AI-2</title>
  <style>
    :root { color-scheme:dark; --bg:#0b1020; --panel:#141b2d; --soft:#1a2338;
      --text:#f4f7ff; --muted:#9ca9c4; --accent:#65d6ad; --border:#2a3550;
      --error:#ff7b86; }
    * { box-sizing:border-box; } body { margin:0; background:var(--bg); color:var(--text);
      font:15px/1.5 Inter,system-ui,sans-serif; }
    header { padding:1rem clamp(1rem,4vw,3rem); border-bottom:1px solid var(--border);
      display:flex; justify-content:space-between; } a { color:var(--accent); }
    main { width:min(1280px,calc(100% - 2rem)); margin:2rem auto 4rem; }
    .panel { background:var(--panel); border:1px solid var(--border); border-radius:1rem;
      padding:1.2rem; margin-bottom:1rem; } h1,h2 { margin-top:0; }
    .toolbar,.actions { display:flex; flex-wrap:wrap; gap:.7rem; align-items:end; }
    label { color:var(--muted); display:block; font-size:.85rem; }
    input,select,textarea,button { background:var(--soft); color:var(--text);
      border:1px solid var(--border); border-radius:.55rem; padding:.58rem; font:inherit; }
    button { cursor:pointer; } button.primary { background:var(--accent); color:#08111b;
      font-weight:700; } button.danger { color:var(--error); }
    #secret { min-width:280px; } #message { min-height:1.5rem; color:var(--accent); }
    #message.error { color:var(--error); } .field { display:grid;
      grid-template-columns:42px minmax(150px,1fr) 130px 100px 110px 110px 110px 130px;
      gap:.55rem; align-items:end; padding:.8rem 0; border-bottom:1px solid var(--border); }
    .field textarea { min-height:42px; resize:vertical; } .field input[type=checkbox] {
      width:1.15rem; height:1.15rem; } .field .checks { text-align:center; }
    .field .move { display:flex; flex-direction:column; gap:.2rem; }
    .field .move button { padding:.15rem .35rem; }
    .wide { grid-column:2/-1; display:grid; grid-template-columns:1fr 1fr; gap:.55rem; }
    .preview-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem; }
    .preview-field input,.preview-field select,.preview-field textarea { width:100%; }
    .required::after { content:" *"; color:var(--error); }
    .source { display:inline-block; margin-left:.35rem; padding:.05rem .4rem;
      border:1px solid var(--accent); border-radius:999px; color:var(--accent);
      font-size:.72rem; font-weight:600; }
    @media(max-width:900px) { .field { grid-template-columns:1fr 1fr; }
      .wide { grid-column:1/-1; } .preview-grid { grid-template-columns:1fr; } }
  </style>
</head>
<body>
<header><strong>Feldkonfiguration</strong><a href="/admin/instances">Instanzen</a></header>
<main>
  <h1 id="title">Feldkonfiguration</h1>
  <p>Die URL-Kennung bestimmt die Kundeninstanz. Änderungen gelten ausschließlich für diesen Mandanten.</p>
  <section class="panel">
    <div class="toolbar">
      <div><label for="secret">Admin-Secret</label>
        <input id="secret" type="password" autocomplete="current-password"></div>
      <div><label for="username">Benutzername</label>
        <input id="username" autocomplete="username"></div>
      <div><label for="password">Passwort</label>
        <input id="password" type="password" autocomplete="current-password"></div>
      <button id="load" type="button">Konfiguration laden</button>
    </div>
    <div id="message"></div>
  </section>
  <section class="panel">
    <h2>Felder</h2>
    <p>Paperless-Felder werden automatisch angezeigt. „In eZEUS aktiv“ steuert
      ausschließlich die Verarbeitung durch eZEUS-AI-2; das Feld bleibt in
      Paperless unabhängig davon erhalten und nutzbar.</p>
    <div id="fields"></div>
    <div class="actions">
      <button id="add" type="button">Benutzerdefiniertes Feld hinzufügen</button>
      <button id="preview" type="button">Vorschau aktualisieren</button>
      <button id="save" class="primary" type="button">Konfiguration speichern</button>
    </div>
  </section>
  <section class="panel">
    <h2>Vorschau Dokumentbearbeitung</h2>
    <div id="preview-content" class="preview-grid"></div>
  </section>
</main>
<script>
  const slug = decodeURIComponent(location.pathname.split("/").filter(Boolean)[2] || "");
  const fieldsRoot = document.getElementById("fields");
  const previewRoot = document.getElementById("preview-content");
  const message = document.getElementById("message");
  let fields = [];
  const types = [["text","Text"],["number","Zahl"],["money","Geldbetrag"],
    ["date","Datum"],["boolean","Ja/Nein"],["select","Auswahlfeld"],
    ["textarea","Mehrzeiliger Text"]];
  function authHeaders(json=true) {
    const username=document.getElementById("username").value;
    const password=document.getElementById("password").value;
    const headers = {};
    if(username && password) {
      headers["X-EZEUS-Admin-User"]=username;
      headers["X-EZEUS-Admin-Password"]=password;
    }
    else headers["X-EZEUS-Admin-Secret"]=document.getElementById("secret").value;
    if (json) headers["Content-Type"] = "application/json";
    return headers;
  }
  function show(text,error=false) { message.textContent=text; message.classList.toggle("error",error); }
  function control(label,node,cls="") {
    const wrap=document.createElement("div"); if(cls) wrap.className=cls;
    const caption=document.createElement("label"); caption.textContent=label;
    wrap.append(caption,node); return wrap;
  }
  function checkbox(value,onchange) {
    const input=document.createElement("input"); input.type="checkbox"; input.checked=value;
    input.addEventListener("change",()=>onchange(input.checked)); return input;
  }
  function render() {
    fieldsRoot.replaceChildren();
    fields.sort((a,b)=>a.sort_order-b.sort_order).forEach((field,index)=>{
      const row=document.createElement("div"); row.className="field";
      const move=document.createElement("div"); move.className="move";
      ["↑","↓"].forEach((label,direction)=>{ const button=document.createElement("button");
        button.type="button"; button.textContent=label; button.addEventListener("click",()=>{
          const other=index+(direction===0?-1:1); if(other<0||other>=fields.length)return;
          [fields[index].sort_order,fields[other].sort_order]=
            [fields[other].sort_order,fields[index].sort_order]; render(); }); move.append(button); });
      row.append(move);
      const name=document.createElement("input"); name.value=field.label; name.maxLength=255;
      name.addEventListener("input",()=>field.label=name.value);
      const nameControl=control("Bezeichnung",name);
      if(!field.is_standard && field.external_field_id) {
        const source=document.createElement("span"); source.className="source";
        source.textContent="Vorhandenes Paperless-Feld";
        nameControl.querySelector("label").append(source);
      }
      row.append(nameControl);
      const type=document.createElement("select"); types.forEach(([value,label])=>{
        const option=new Option(label,value); option.selected=field.field_type===value; type.add(option); });
      type.addEventListener("change",()=>{field.field_type=type.value;
        if(type.value!=="select")field.options=[]; render();}); row.append(control("Typ",type));
      row.append(control("In eZEUS aktiv",checkbox(field.enabled,v=>field.enabled=v),"checks"));
      row.append(control("Pflichtfeld",checkbox(field.required,v=>field.required=v),"checks"));
      row.append(control("OCR",checkbox(field.ocr_enabled,v=>field.ocr_enabled=v),"checks"));
      row.append(control("KI",checkbox(field.ai_enabled,v=>field.ai_enabled=v),"checks"));
      const external=document.createElement("input"); external.value=field.external_field_id||"";
      external.placeholder="Paperless-ID"; external.addEventListener("input",()=>field.external_field_id=
        external.value||null); row.append(control("Paperless-Feld-ID",external));
      const wide=document.createElement("div"); wide.className="wide";
      const instructions=document.createElement("textarea");
      instructions.value=field.extraction_instructions||"";
      instructions.placeholder="Optionale Hinweise für die KI-Auslesung";
      instructions.addEventListener("input",()=>field.extraction_instructions=
        instructions.value||null); wide.append(control("Extraktionshinweise",instructions));
      const options=document.createElement("input"); options.value=(field.options||[]).join(", ");
      options.disabled=field.field_type!=="select"; options.placeholder="Option A, Option B";
      options.addEventListener("input",()=>field.options=options.value.split(",").map(v=>v.trim())
        .filter(Boolean)); wide.append(control("Auswahlwerte",options)); row.append(wide);
      fieldsRoot.append(row);
    });
  }
  function payload() { return {fields:fields.map((field,index)=>({...field,
    sort_order:(index+1)*10, id:undefined, is_standard:undefined}))}; }
  async function load() {
    const response=await fetch(`/api/instances/${encodeURIComponent(slug)}/field-config`,
      {headers:authHeaders(false)}); const body=await response.json();
    if(!response.ok){show(body.detail||`HTTP ${response.status}`,true);return;}
    fields=body.fields; document.getElementById("title").textContent=
      `Feldkonfiguration: ${body.instance.name}`; show("Konfiguration geladen."); render();
    await updatePreview();
  }
  async function updatePreview() {
    const response=await fetch(`/api/instances/${encodeURIComponent(slug)}/field-config/preview`,
      {method:"POST",headers:authHeaders(),body:JSON.stringify(payload())});
    const body=await response.json(); if(!response.ok){show(body.detail||"Vorschau ungültig",true);return;}
    previewRoot.replaceChildren(); body.fields.forEach(field=>{
      const wrap=document.createElement("div"); wrap.className="preview-field";
      const label=document.createElement("label"); label.textContent=field.label;
      if(field.required)label.className="required"; let input;
      if(field.field_type==="textarea")input=document.createElement("textarea");
      else if(field.field_type==="select"){input=document.createElement("select");
        field.options.forEach(value=>input.add(new Option(value,value)));}
      else {input=document.createElement("input"); input.type=field.field_type==="date"?"date":
        field.field_type==="number"||field.field_type==="money"?"number":
        field.field_type==="boolean"?"checkbox":"text";}
      input.disabled=true; wrap.append(label,input); previewRoot.append(wrap);
    });
  }
  async function save() {
    const response=await fetch(`/api/instances/${encodeURIComponent(slug)}/field-config`,
      {method:"PUT",headers:authHeaders(),body:JSON.stringify(payload())});
    const body=await response.json(); if(!response.ok){show(body.detail||"Speichern fehlgeschlagen",true);return;}
    fields=body.fields; show("Mandantenkonfiguration wurde gespeichert."); render(); await updatePreview();
  }
  document.getElementById("load").addEventListener("click",load);
  document.getElementById("preview").addEventListener("click",updatePreview);
  document.getElementById("save").addEventListener("click",save);
  document.getElementById("add").addEventListener("click",()=>{fields.push({field_key:null,
    label:"Neues Feld",field_type:"text",sort_order:(fields.length+1)*10,is_standard:false,
    enabled:true,required:false,ocr_enabled:true,ai_enabled:false,external_field_id:null,
    options:[],extraction_instructions:null});render();});
  load();
</script>
</body>
</html>"""


@router.get(
    "/admin/instances/{instance_slug}/fields",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def field_configuration_page(instance_slug: str) -> str:
    if not instance_slug:
        raise HTTPException(status_code=404)
    return FIELD_CONFIG_HTML
