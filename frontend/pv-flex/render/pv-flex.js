import {loadFlexPriorityShadow,loadHeatingPreheatProgressionShadow,loadHeatingPreheatShadow,loadPvFlex,shiftDay,todayAmsterdam} from "../state/pv-flex-state.js";
const $=id=>document.getElementById(id); let day=todayAmsterdam();
const kwh=v=>`${Number(v||0).toLocaleString("nl-NL",{minimumFractionDigits:1,maximumFractionDigits:2})} kWh`;
const pct=v=>`${Math.round(Number(v||0)*100)}%`;
const time=x=>new Date(x).toLocaleTimeString("nl-NL",{timeZone:"Europe/Amsterdam",hour:"2-digit",minute:"2-digit"});
function summary(d){
 $("day-title").textContent=new Date(d.period.start).toLocaleDateString("nl-NL",{timeZone:"Europe/Amsterdam",weekday:"long",day:"numeric",month:"long",year:"numeric"});
 $("kpi-forecast").textContent=kwh(d.summary.forecastKWh); $("kpi-slots").textContent=`${d.summary.forecastSlots}/${d.series.length} forecastkwartieren`;
 $("kpi-pv").textContent=kwh(d.summary.pvKWh); $("kpi-self").textContent=kwh(d.summary.pvSelfConsumedKWh); $("kpi-export").textContent=kwh(d.summary.exportKWh);
 $("quality").textContent=`Dekking ${pct(d.quality.actualCoverage)}`; $("next").disabled=day>=todayAmsterdam();
}
function slotAllocation(x){
 const pvW=Math.max(0,Number(x.actual.pvKWh||0)*4000);
 const exportW=Math.min(pvW,Math.max(0,Number(x.actual.exportKWh||0)*4000));
 const directPvW=Math.max(0,pvW-exportW);
 const houseW=Math.max(0,Number(x.actual.houseKWh||0)*4000);
 const evActualW=(typeof x.devices?.evPowerW==="number"&&Number.isFinite(x.devices.evPowerW))?Math.max(0,x.devices.evPowerW):0;
 const nonEvHouseW=Math.max(0,houseW-evActualW);
 const evPvW=Math.min(evActualW,directPvW,Math.max(0,pvW-nonEvHouseW));
 const otherPvW=Math.max(0,directPvW-evPvW);
 return {pvW,exportW,directPvW,houseW,evActualW,evPvW,otherPvW};
}
function chart(d){
 const svg=$("pv-chart"), tip=$("tooltip"), a=d.series; svg.replaceChildren(); const has=a.some(x=>x.actual.coverage>0||x.forecast); $("empty").hidden=has; svg.hidden=!has;if(!has)return;
 const W=1000,H=330,p={l:52,r:18,t:18,b:40},iw=W-p.l-p.r,ih=H-p.t-p.b,ns="http://www.w3.org/2000/svg";
 const allocated=a.map(slotAllocation), max=Math.max(100,...a.flatMap((x,i)=>[allocated[i].pvW,x.forecast?.pvForecastW||0]));
 svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
 const add=(t,z,txt)=>{const e=document.createElementNS(ns,t);Object.entries(z).forEach(([k,v])=>e.setAttribute(k,v));if(txt!=null)e.textContent=txt;svg.appendChild(e);return e;};
 for(let i=0;i<=4;i++){let y=p.t+ih*i/4;add("line",{x1:p.l,y1:y,x2:W-p.r,y2:y,class:"gridline"});add("text",{x:p.l-7,y:y+4,class:"axis","text-anchor":"end"},`${Math.round(max*(4-i)/400)/10}kW`);}
 const step=iw/a.length, points=[];
 a.forEach((x,i)=>{
  const cx=p.l+(i+.5)*step,s=allocated[i],barW=step*.68;
  let y=p.t+ih;
  for(const [w,cls] of [[s.evPvW,"pv-ev"],[s.otherPvW,"pv-self"],[s.exportW,"pv-export"]]){
   const h=w/max*ih;
   if(h>0){y-=h;add("rect",{x:cx-barW/2,y,width:barW,height:h,class:cls});}
  }
  if(x.forecast)points.push(`${cx},${p.t+ih-(x.forecast.pvForecastW/max*ih)}`);
  if(i%8===0)add("text",{x:cx,y:H-15,class:"axis","text-anchor":"middle"},time(x.start));
  const hit=add("rect",{x:p.l+i*step,y:p.t,width:step,height:ih,class:"hit"});
  hit.addEventListener("mousemove",e=>{
   const forecast=x.forecast?(x.forecast.pvForecastW/1000).toFixed(2)+" kW":"—";
   tip.hidden=false;
   tip.innerHTML=`<strong>${time(x.start)}</strong><span>PV werkelijk ${(s.pvW/1000).toFixed(2)} kW</span><span>Forecast ${forecast}</span><span>EV uit PV ${(s.evPvW/1000).toFixed(2)} kW</span><span>Tesla werkelijk ${(s.evActualW/1000).toFixed(2)} kW</span><span>Overig eigen PV ${(s.otherPvW/1000).toFixed(2)} kW</span><span>Export ${(s.exportW/1000).toFixed(2)} kW</span><span>Confidence ${x.forecast?.confidence!=null?Math.round(x.forecast.confidence*100)+"%":"—"}</span><span>Lead ${x.forecast?.leadMinutes??"—"} min</span>`;
   const r=svg.parentElement.getBoundingClientRect();tip.style.left=`${Math.min(r.width-210,Math.max(8,e.clientX-r.left+10))}px`;tip.style.top=`${Math.max(8,e.clientY-r.top-110)}px`;
  });
  hit.addEventListener("mouseleave",()=>tip.hidden=true);
 });
 if(points.length>1)add("polyline",{points:points.join(" "),class:"forecast-line",fill:"none"});
}
const temp=v=>typeof v==="number"&&Number.isFinite(v)?`${v.toLocaleString("nl-NL",{minimumFractionDigits:1,maximumFractionDigits:1})} °C`:"—";
const label=s=>({
 PREHEAT_READY_FOR_GRANT:"Klaar voor planner",
 PREHEAT_BLOCKED_CV_ASSIST:"Geblokkeerd · CV-assist",
 PREHEAT_BLOCKED_CV_STATUS_UNKNOWN:"Geblokkeerd · CV-status",
 BASELINE_HEATING:"Normale warmtevraag",
 NOT_ELIGIBLE:"Niet kandidaat"
}[s]||s||"—");
const priorityLabel=p=>({
 HEATING:"Heating eerst",
 EV:"EV eerst",
 HOLD_UNKNOWN:"Veilig HOLD"
}[p]||p||"—");
const evRoleLabel=r=>({
 MUST:"EV MUST",
 PRIMARY_OPPORTUNITY:"EV primaire opportunity",
 RESIDUAL_OPPORTUNITY:"EV residual via P1",
 SAFETY_HOLD:"EV safety hold"
}[r]||r||"—");
const plannerReasonLabel=r=>({
 NO_HEATING_PREHEAT_CANDIDATE:"Geen Heating-kandidaat",
 HEATING_WINDOW_CLOSES_FIRST:"Heating-window sluit eerder",
 HEATING_SCARCE_WINDOW_WITH_NO_EV_DEADLINE_PRESSURE:"Heating-window is schaars; geen EV-deadline-druk",
 EV_SLACK_CLOSES_BEFORE_HEATING_WINDOW:"EV-slack sluit eerder",
 EV_DEADLINE_MUST:"EV-deadline MUST",
 EV_DEADLINE_STATE_NOT_SAFE_TO_DEPRIORITIZE:"EV-deadline onzeker; Heating veilig HOLD"
}[r]||r||"—");
const progressionLabel=s=>({
 INACTIVE:"Inactief",
 WAITING_FOR_FRESH_PRIORITY:"Wacht op verse prioriteit",
 WAITING_FOR_GRANT:"Wacht op planner-grant",
 STEP_WAIT:"Stap actief · op temperatuur wachten",
 STEP_REACHED:"Stap bereikt",
 STEP_REACHED_GROUP_WAIT:"Stap bereikt · wacht op groep",
 STEP_HOLD_PRIORITY_UNKNOWN:"Stap HOLD · prioriteit onzeker",
 STEP_HOLD_NO_GRANT:"Stap HOLD · geen grant",
 BLOCKED_CV_ASSIST:"Geblokkeerd · CV-assist",
 BLOCKED_CV_STATUS_UNKNOWN:"Geblokkeerd · CV-status onbekend",
 ENDED_BASELINE_HEATING:"Beëindigd · baseline warmtevraag",
 COMPLETE_TARGET_REACHED:"Gereed · Honeywell-target bereikt",
 COMPLETE_NO_NEXT_STEP:"Gereed · geen volgende stap"
}[s]||s||"—");
function roomPlannerState(room,priority){
 const decision=priority?.decision;
 if(!decision)return {grant:"NOT_EVALUATED",reason:"Prioriteit niet beschikbaar"};
 const readyRooms=Array.isArray(priority?.heating?.readyRooms)?priority.heating.readyRooms:[];
 const roomReady=room.shadow?.state==="PREHEAT_READY_FOR_GRANT"&&readyRooms.includes(room.key);
 if(!roomReady)return {grant:"HOLD",reason:"Kamer niet klaar voor planner-grant"};
 if(decision.heatingShadowGrant==="SHADOW_GRANT"){
  return {grant:"SHADOW_GRANT",reason:plannerReasonLabel(decision.reason)};
 }
 return {grant:"HOLD",reason:plannerReasonLabel(decision.reason)};
}
function renderPreheat(d,priority,progression,isCurrent){
 const root=$("preheat-rooms"),empty=$("preheat-empty"),status=$("preheat-status");root.replaceChildren();
 if(!isCurrent){status.textContent="Live shadow";empty.hidden=false;empty.textContent="Preheat shadow wordt alleen voor vandaag getoond.";return;}
 if(!d){status.textContent="Niet beschikbaar";empty.hidden=false;empty.textContent="Heating Preheat shadow is niet beschikbaar; PV & Flex blijft read-only actief.";return;}
 empty.hidden=true;
 const cv=d.cvGuard?.status==="OK"?(d.cvGuard.cvActive?"CV actief":"CV uit"):"CV onbekend";
 const pr=priority?.decision;
 const priorityText=pr?`${priorityLabel(pr.priorityOwner)} · ${evRoleLabel(pr.evRole)}`:"Prioriteit niet beschikbaar";
 status.textContent=`${priorityText} · ${d.house?.baselineHeatingDemandPresent?"Baselinevraag actief":"Baseline voldaan"} · ${cv}`;
 const progressionByKey=new Map((progression?.rooms||[]).map(r=>[r.key,r]));
 for(const r of d.rooms||[]){
  const roomPlan=roomPlannerState(r,priority);
  const v04=progressionByKey.get(r.key);
  const prog=v04?.progression;
  const card=document.createElement("article");card.className="preheat-room";
  const head=document.createElement("div");head.className="preheat-room-head";
  const name=document.createElement("strong");name.textContent=r.displayName||r.key;
  const badge=document.createElement("span");badge.className=`preheat-state ${r.shadow?.state==="PREHEAT_READY_FOR_GRANT"?"ready":"blocked"}`;badge.textContent=label(r.shadow?.state);
  head.append(name,badge);
  const metrics=document.createElement("div");metrics.className="preheat-metrics";
  const entries=[
   ["Nu",temp(r.current?.temperature_C)],
   ["Baseline",temp(r.baseline?.currentTargetTemperature_C)],
   ["Volgende Honeywell-UP",r.baseline?.direction==="UP"?temp(r.baseline?.targetTemperature_C):"—"],
   ["Preheat-window",r.candidate?.opportunityOpensAt&&r.candidate?.opportunityClosesAt?`${time(r.candidate.opportunityOpensAt)}–${time(r.candidate.opportunityClosesAt)}`:"—"],
   ["Planner grant",roomPlan.grant],
   ["V0.4 progression",progressionLabel(prog?.state)],
   ["Actieve shadow-target",temp(prog?.activeStepTarget_C)],
   ["Target bereikt",prog?.activeStepReached===true?"Ja":prog?.activeStepReached===false?"Nee":"—"],
   ["Volgende V0.4-stap",temp(prog?.nextStepTarget_C)]
  ];
  for(const [k,v] of entries){const row=document.createElement("span");const b=document.createElement("b");b.textContent=k;const val=document.createTextNode(v);row.append(b,val);metrics.append(row);}
  const reason=document.createElement("small");reason.className="preheat-reason";reason.textContent=r.shadow?.reason||r.candidate?.reason||"—";
  const plannerReason=document.createElement("small");plannerReason.className="preheat-reason";plannerReason.textContent=`Planner: ${roomPlan.reason}`;
  const progressionReason=document.createElement("small");progressionReason.className="preheat-reason";progressionReason.textContent=`V0.4: ${prog?.reason||"Niet beschikbaar"}`;
  card.append(head,metrics,reason,plannerReason,progressionReason);root.append(card);
 }
}
async function refresh(){
 $("quality").textContent="Laden…";
 try{
  const isCurrent=day===todayAmsterdam();
  const [d,h,p,g]=await Promise.all([
   loadPvFlex(day),
   isCurrent?loadHeatingPreheatShadow().catch(()=>null):Promise.resolve(null),
   isCurrent?loadFlexPriorityShadow().catch(()=>null):Promise.resolve(null),
   isCurrent?loadHeatingPreheatProgressionShadow().catch(()=>null):Promise.resolve(null)
  ]);
  summary(d);chart(d);renderPreheat(h,p,g,isCurrent);
 }catch(e){
  $("quality").textContent="Analyse niet beschikbaar";
  $("empty").hidden=false;$("empty").textContent=e.message;$("pv-chart").hidden=true;
  renderPreheat(null,null,null,day===todayAmsterdam());
 }
}
$("prev").addEventListener("click",()=>{day=shiftDay(day,-1);refresh();});$("next").addEventListener("click",()=>{if(day<todayAmsterdam()){day=shiftDay(day,1);refresh();}});refresh();