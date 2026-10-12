from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from apps.api.ui import page_shell

router = APIRouter(tags=["triggers"])


@router.get("/admin/triggers", response_class=HTMLResponse, include_in_schema=False)
def trigger_admin_page() -> str:
    content = """
<section class="panel">
  <div class="section-heading">
    <div>
      <h2>Automatische Dokument-Trigger</h2>
      <p class="section-copy">Für jede Paperless-Instanz getrennt festlegen, ob eZEUS
        sofort beim Hinzufügen oder erst nach dem Setzen eines Paperless-Tags startet.</p>
    </div>
  </div>
  <div id="trigger-instances" class="loading-state" role="status">Instanzen werden geladen</div>
</section>
"""
    script = """
<script>
  const container=document.getElementById("trigger-instances");
  function modeLabel(mode) {
    return mode==="tag_added"?"Nach Paperless-Tag":"Beim Hinzufügen";
  }
  async function saveTrigger(item,mode,tagName,button,message) {
    if(mode==="tag_added"&&!tagName) {
      window.ezeusUI?.announce(message,"Bitte ein Trigger-Tag eingeben.","error"); return;
    }
    window.ezeusUI?.setBusy(button,true,"Speichert …");
    try {
      const update=await fetch(`/api/paperless-instances/${item.id}`,{
        method:"PATCH",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          automatic_trigger_mode:mode,
          automatic_trigger_tag_name:mode==="tag_added"?tagName:null
        })
      });
      const updateBody=await update.json();
      if(!update.ok) throw new Error(updateBody.detail||`HTTP ${update.status}`);
      const provision=await fetch(`/api/paperless-instances/${item.id}/provision-workflow`,{
        method:"POST"
      });
      const provisionBody=await provision.json();
      if(!provision.ok) throw new Error(provisionBody.detail||`HTTP ${provision.status}`);
      window.ezeusUI?.announce(message,
        `Trigger gespeichert: ${modeLabel(mode)}${tagName?` „${tagName}“`:""}.`,"success");
    } catch(error) {
      window.ezeusUI?.announce(message,`Speichern fehlgeschlagen: ${error.message}`,"error");
    } finally { window.ezeusUI?.setBusy(button,false); }
  }
  async function loadTriggers() {
    try {
      const response=await fetch("/api/paperless-instances",{cache:"no-store"});
      if(!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload=await response.json(); container.replaceChildren();
      if(!payload.instances.length) {
        container.className="empty-state"; container.textContent="Keine Instanzen konfiguriert.";
        return;
      }
      container.className="content-stack";
      payload.instances.forEach((item)=>{
        const card=document.createElement("article"); card.className="instance-card";
        const form=document.createElement("div"); form.className="form-grid";
        const title=document.createElement("h3"); title.textContent=item.name;
        const meta=document.createElement("p"); meta.className="help-text";
        meta.textContent=item.base_url;
        const modeWrap=document.createElement("div");
        const modeLabelElement=document.createElement("label");
        modeLabelElement.textContent="Auslöser";
        const mode=document.createElement("select");
        [["document_added","Beim Hinzufügen des Dokuments"],
         ["tag_added","Erst nach gesetztem Paperless-Tag"]].forEach(([value,label])=>{
          const option=document.createElement("option");
          option.value=value; option.textContent=label;
          mode.appendChild(option);
        });
        mode.value=item.automatic_trigger_mode||"document_added";
        modeWrap.append(modeLabelElement,mode);
        const tagWrap=document.createElement("div");
        const tagLabel=document.createElement("label");
        tagLabel.textContent="Paperless-Trigger-Tag";
        const tag=document.createElement("input"); tag.maxLength=128;
        tag.placeholder="z. B. bereit-für-ezeus";
        tag.value=item.automatic_trigger_tag_name||"";
        tagWrap.append(tagLabel,tag);
        const sync=()=>{ tagWrap.hidden=mode.value!=="tag_added"; };
        mode.addEventListener("change",sync); sync();
        const message=document.createElement("div");
        message.className="notice"; message.hidden=true;
        const actions=document.createElement("div"); actions.className="form-actions";
        const button=document.createElement("button"); button.className="primary";
        button.type="button"; button.textContent="Trigger speichern und einrichten";
        button.addEventListener("click",()=>saveTrigger(
          item,mode.value,tag.value.trim(),button,message));
        actions.appendChild(button); form.append(modeWrap,tagWrap);
        const info=document.createElement("div"); info.append(title,meta,form,message,actions);
        card.appendChild(info); container.appendChild(card);
      });
    } catch(error) {
      container.className="notice error";
      container.textContent=`Trigger konnten nicht geladen werden: ${error.message}`;
    }
  }
  loadTriggers();
</script>
"""
    return page_shell(
        title="Trigger",
        description="Automatische Auslöser je Paperless-Instanz konfigurieren.",
        active="triggers",
        content=content,
        script=script,
    )
