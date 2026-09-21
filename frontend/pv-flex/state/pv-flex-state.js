const API_ROOT="/web/analysis/pv-flex/day";
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