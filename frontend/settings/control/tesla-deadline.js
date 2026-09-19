const CONFIG="../config/tesla-control-config.json";

const $=id=>document.getElementById(id);
let saving=false;
let savedValues=null;

async function loadConfig(){
  const r=await fetch(`${CONFIG}?t=${Date.now()}`,{cache:"no-store"});
  if(!r.ok)throw new Error(`config HTTP ${r.status}`);
  return r.json();
}
function values(){
  return {
    currentSoc:Number($("current-soc")?.value),
    targetSoc:Number($("target-soc")?.value),
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
  return Boolean(a&&b)&&a.currentSoc===b.currentSoc&&a.targetSoc===b.targetSoc&&a.deadline===b.deadline&&a.maxA===b.maxA;
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
async function save(){
  if(saving)return;
  const v=values(),problem=validate(v);
  if(problem){message(problem,"error");return;}
  let cfg;
  try{cfg=await loadConfig();}catch(e){message(`Write-route niet beschikbaar: ${e.message}`,"error");return;}
  const worker=String(cfg?.worker_url||"").trim();
  if(cfg?.status!=="ready"||!worker){message("Write-route niet gereed.","error");return;}
  const pin=window.prompt("Voer de Tesla-control PIN in:");
  if(pin===null)return;
  setBusy(true);message("Opdracht verzenden…","pending");
  try{
    const r=await fetch(worker,{method:"POST",headers:{"Content-Type":"application/json","X-Tesla-Control-Pin":pin},body:JSON.stringify({active:true,currentSoc:v.currentSoc,targetSoc:v.targetSoc,deadline:v.deadline,maxA:v.maxA})});
    const j=await r.json().catch(()=>({}));
    if(!r.ok||j?.ok!==true)throw new Error(j?.error||`HTTP ${r.status}`);
    accepted(j.command);
    savedValues=values();
    updateSaveButton();
    message("Opgeslagen · opdracht geaccepteerd door write-route.","ok");
  }catch(e){message(`Opslaan mislukt: ${e.message||e}`,"error");}
  finally{setBusy(false);}
}
$("tesla-save")?.addEventListener("click",save);
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
