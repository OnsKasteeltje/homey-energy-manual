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
 const name=encodeURIComponent(day);
 const [main, archivedResponse]=await Promise.all([
  fetch(API_ROOT+"/"+name,{cache:"no-store"}),
  fetch("/web/analysis/planner/day/"+name,{cache:"no-store"}).catch(()=>null)
 ]);
 if(!main.ok)throw new Error("PV & Flex API "+main.status);
 const d=await main.json();
 if(d.schema!=="EMS_WEB_PV_FLEX_ANALYSIS_V1")throw new Error("Onbekend PV & Flex-schema");
 let evidence=null;
 if(archivedResponse?.ok){
  const candidate=await archivedResponse.json();
  if(candidate.schema==="EMS_WEB_PLANNER_EVALUATION_V2" &&
     candidate.forecastSource==="ARCHIVED_CANONICAL_V1_DYNAMIC_PLAN") evidence=candidate;
 }
 // NEVER let V2 forecasts from the old resource masquerade as historical V1.
 const map=new Map((evidence?.series||[]).map(x=>[new Date(x.start).getTime(),x]));
 return {
  ...d,
  historicalPlannerAvailable:!!evidence,
  summary:{
   ...d.summary,
   forecastKWh:evidence?.summary?.forecastKWh??null,
   forecastSlots:evidence?.summary?.forecastSlots||0,
   planSlots:evidence?.summary?.planSlots||0,
   plannedEvKWh:evidence?.summary?.plannedEvKWh??null,
   plannedWwKWh:evidence?.summary?.plannedWwKWh??null,
   plannedQuookerKWh:evidence?.summary?.plannedQuookerKWh??null,
   quookerPlanSlots:evidence?.summary?.quookerPlanSlots||0
  },
  series:d.series.map(slot=>{
   const historical=map.get(new Date(slot.start).getTime());
   return {...slot,forecast:historical?.forecast||null,plan:historical?.plan||null};
  })
 };
}

export async function loadDailyPerformance(day){
 if(day>=todayAmsterdam())return null; // A completed Amsterdam day is required.
 const r=await fetch("/web/analysis/performance/day/"+encodeURIComponent(day),{cache:"no-store"});
 if(r.status===404)return null; // No archived report for this date.
 if(!r.ok)throw new Error("Dagrapport API "+r.status);
 const d=await r.json();
 if(d.schema!=="EMS_WEB_DAILY_PERFORMANCE_V1"||d.dateLocal!==day||
    d.readOnly!==true||d.controlWrites!==false)throw new Error("Ongeldig dagrapport");
 return d;
}
