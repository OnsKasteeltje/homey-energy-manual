
const $=id=>document.getElementById(id);
let saving=false;
let savedValues=null;
let retryFingerprint=null;
let retryRequestId=null;

function values(){
  return {
    currentSoc:$("current-soc")?.value?.trim()===""?NaN:Number($("current-soc")?.value),
    targetSoc:$("target-soc")?.value?.trim()===""?NaN:Number($("target-soc")?.value),
    deadline:String($("deadline")?.value||"").trim(),
    maxA:Number($("max-a")?.value)
  };
}
function validate(v){
  if(!Number.isFinite(v.currentSoc)||v.currentSoc<0||v.currentSoc>99)return "Controleer huidige SOC.";
  if(!Number.isFinite(v.targetSoc)||v.targetSoc<1||v.targetSoc>100||v.targetSoc<=v.currentSoc)return "Doel-SOC moet hoger zijn dan huidige SOC.";
  if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(v.deadline))return "Controleer de deadline.";
  if(new Date(v.deadline).getTime()<=Date.now())return "Deadline moet in de toekomst liggen.";
  if(!Number.isFinite(v.maxA)||v.maxA<6||v.maxA>16)return "Maximale laadstroom moet 6–16 A zijn.";
  return "";
}
function sameValues(a,b){
  return Boolean(a&&b)&&["currentSoc","targetSoc","deadline","maxA"].every(k=>Object.is(a[k],b[k]));
}
function updateSaveButton(){
  const b=$("tesla-save");if(!b)return;
  if(saving){b.disabled=true;b.textContent="Opslaan…";return;}
  const unchanged=sameValues(values(),savedValues);
  b.disabled=unchanged;
  b.textContent=unchanged?"Opgeslagen":"Opslaan";
}
function setBusy(on){
  saving=on;
  updateSaveButton();
}
function message(text,state=""){
  const e=$("tesla-message");if(!e)return;e.textContent=text;e.dataset.state=state;
}
function accepted(cmd){
  if(!cmd)return;
  $("current-soc").value=cmd.currentSoc??"";
  $("target-soc").value=cmd.targetSoc??"";
  $("deadline").value=cmd.deadline??"";
  $("max-a").value=cmd.maxA??"";
  $("tesla-command-state").textContent=cmd.active===true?"ACTIEF":"INACTIEF";
  $("tesla-summary").textContent=cmd.active===true?`${cmd.currentSoc}% → ${cmd.targetSoc}% · uiterlijk ${String(cmd.deadline).replace("T"," ")} · max ${cmd.maxA} A`:"Geen actieve deadline-opdracht";
}
function clientRequestId(){
  // Idempotency only, not authentication.
  return window.crypto?.randomUUID?.() || "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g,c=>{
    const r=Math.floor(Math.random()*16);return(c==="x"?r:(r&3|8)).toString(16);
  });
}
function idempotencyKey(active,v){
  const fingerprint=JSON.stringify({active,...v});
  if(retryFingerprint!==fingerprint||!retryRequestId){
    retryFingerprint=fingerprint;
    retryRequestId=clientRequestId();
  }
  return retryRequestId;
}
async function submit(active){
  if(saving)return;
  const v=values(),problem=active?validate(v):"";
  if(problem){message(problem,"error");return;}
  const pin=window.prompt("Voer de Tesla-control PIN in:");
  if(pin===null)return;
  setBusy(true);
  message(active?"Deadline lokaal opslaan…":"Deadline lokaal uitschakelen…","pending");
  try{
    const r=await fetch("/web/commands/tesla",{
      method:"POST",cache:"no-store",
      headers:{"Content-Type":"application/json","X-Tesla-Control-Pin":pin},
      body:JSON.stringify({active,deadline:active?v.deadline:"",currentSoc:active?v.currentSoc:null,
        targetSoc:active?v.targetSoc:null,maxA:active?v.maxA:11,clientRequestId:idempotencyKey(active,v)})
    });
    const j=await r.json().catch(()=>({}));
    if(!r.ok||j?.ok!==true){
      throw new Error(r.status===403?"Gebruik de Tailscale-website voor opdrachten.":
        r.status===503?"Pi-commandservice niet geconfigureerd of beschikbaar.":
        j?.error||"HTTP "+r.status);
    }
    accepted(j.command);
    retryFingerprint=null;
    retryRequestId=null;
    savedValues=values();
    updateSaveButton();
    message(j.derivedState==="UPDATED"?"Pi heeft opdracht opgeslagen en verwerkt.":
      "Pi heeft opdracht opgeslagen; verwerking nog niet bevestigd.","ok");
    window.dispatchEvent(new Event("ems:tesla-command-saved"));
  }catch(e){message("Opslaan mislukt: "+(e.message||e),"error");}
  finally{setBusy(false);}
}
async function save(){return submit(true);}
async function cancel(){return submit(false);}

$("tesla-save")?.addEventListener("click",save);
$("tesla-cancel")?.addEventListener("click",cancel);
window.addEventListener("ems:tesla-command-rendered",()=>{
  savedValues=values();
  updateSaveButton();
});

["current-soc","target-soc","deadline","max-a"].forEach(id=>{
  $(id)?.addEventListener("input",()=>{
    updateSaveButton();
    if(savedValues&&!sameValues(values(),savedValues))message("Wijzigingen nog niet opgeslagen.","pending");
  });
});
