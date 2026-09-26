const API_ROOT="/web/analysis/pv-flex/day";
const PREHEAT_ROOT="/web/planner/heating-preheat-shadow";
const PREHEAT_PROGRESSION_ROOT="/web/planner/heating-preheat-progression-shadow";
const FLEX_PRIORITY_ROOT="/web/planner/flex-priority-shadow";
function pad(v){return String(v).padStart(2,"0");}
export function todayAmsterdam(){
 const p=Object.fromEntries(new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Amsterdam",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date()).map(x=>[x.type,x.value]));
 return `${p.year}-${p.month}-${p.day}`;
}
export function shiftDay(anchor,n){
 const [y,m,d]=anchor.split("-").map(Number), x=new Date(Date.UTC(y,m-1,d,12)); x.setUTCDate(x.getUTCDate()+n);
 return `${x.getUTCFullYear()}-${pad(x.getUTCMonth()+1)}-${pad(x.getUTCDate())}`;
}
export async function loadPvFlex(day){
 const r=await fetch(`${API_ROOT}/${encodeURIComponent(day)}`,{cache:"no-store"});
 if(!r.ok) throw new Error(`PV & Flex API ${r.status}`);
 const d=await r.json(); if(d.schema!=="EMS_WEB_PV_FLEX_ANALYSIS_V1") throw new Error("Onbekend PV & Flex-schema"); return d;
}
export async function loadHeatingPreheatShadow(){
 const r=await fetch(PREHEAT_ROOT,{cache:"no-store"});
 if(!r.ok) throw new Error(`Heating Preheat API ${r.status}`);
 const d=await r.json();
 if(d.schema!=="EMS_WEB_HEATING_PREHEAT_SHADOW_V1") throw new Error("Onbekend Heating Preheat-schema");
 return d;
}

export async function loadFlexPriorityShadow(){
 const r=await fetch(FLEX_PRIORITY_ROOT,{cache:"no-store"});
 if(!r.ok) throw new Error(`Flex Priority API ${r.status}`);
 const d=await r.json();
 if(d.schema!=="EMS_WEB_FLEX_PRIORITY_SHADOW_V1") throw new Error("Onbekend Flex Priority-schema");
 return d;
}

export async function loadHeatingPreheatProgressionShadow(){
 const r=await fetch(PREHEAT_PROGRESSION_ROOT,{cache:"no-store"});
 if(!r.ok) throw new Error(`Heating Preheat Progression API ${r.status}`);
 const d=await r.json();
 if(d.schema!=="EMS_WEB_HEATING_PREHEAT_PROGRESSION_V1") throw new Error("Onbekend Heating Preheat Progression-schema");
 return d;
}
