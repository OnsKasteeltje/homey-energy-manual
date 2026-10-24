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

// Use only the canonical, freshness-validated Pi plan; never fall back to
// a separate forecast model or rewrite archived decisions.
async function loadCurrentPiPvForecast(day){
 if(day!==todayAmsterdam())return null;
 try{
  const response=await fetch("/web/planner/current",{cache:"no-store"});
  if(!response.ok)return null;
  const plan=await response.json(),now=Date.now();
  if(plan.schema!=="EMS_WEB_DYNAMIC_PLAN_V1" ||
     plan.controlWrites!==false || plan.status!=="SHADOW" ||
     plan.forecastSource!=="PV_V1_EMBEDDED_IN_DYNAMIC_PLAN" ||
     !Array.isArray(plan.slots) || plan.slots.length!==96 ||
     !Number.isFinite(Date.parse(plan.generatedAt)) ||
     Date.parse(plan.generatedAt)>now+120000 ||
     !Number.isFinite(Date.parse(plan.validUntil)) ||
     Date.parse(plan.validUntil)<=now)return null;
  return plan;
 }catch{return null;} // Best-effort overlay, never break historical evaluation.
}

export async function loadPvFlex(day){
 const name=encodeURIComponent(day);
 const [main, archivedResponse,currentPlan]=await Promise.all([
  fetch(API_ROOT+"/"+name,{cache:"no-store"}),
  fetch("/web/analysis/planner/day/"+name,{cache:"no-store"}).catch(()=>null),
  loadCurrentPiPvForecast(day)
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
 const currentMap=new Map((currentPlan?.slots||[])
  .filter(x=>Number.isFinite(Date.parse(x?.start)) &&
   typeof x.pvForecastW==="number" && Number.isFinite(x.pvForecastW) &&
   x.pvForecastW>=0 && x.pvForecastW<=50000)
  .map(x=>[Date.parse(x.start),x.pvForecastW]));
 const now=Date.now();
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
   const when=Date.parse(slot.start);
   // Keep decision evidence intact; live PV covers the open quarter and future.
   const end=Number.isFinite(Date.parse(slot.end))?Date.parse(slot.end):when+900000;
   const currentPvForecastW=Number.isFinite(when)&&Number.isFinite(end)&&end>now?
    currentMap.get(when)??null:null;
   return {...slot,forecast:historical?.forecast||null,
    plan:historical?.plan||null,
    historicalPvDisplay:historical?.displayForecast||null,
    currentPvForecastW};
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

export async function loadGoodweCloudEvidence(day){
 const response=await fetch("/web/analysis/pv-cloud/day/"+encodeURIComponent(day),{cache:"no-store"});
 if(!response.ok)throw new Error("GoodWe SEMS+ bron niet beschikbaar");
 const data=await response.json();
 if(data.schema!=="EMS_WEB_GOODWE_CLOUD_EVIDENCE_V1" ||
    data.dateLocal!==day || data.readOnly!==true ||
    data.controlWrites!==false || data.eligibleForControl!==false ||
    data.eligibleForHouseBalance!==false)
  throw new Error("Ongeldig GoodWe SHADOW-bewijs");
 return data;
}

