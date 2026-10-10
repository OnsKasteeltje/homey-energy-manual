import {loadFlexPriorityShadow,loadHeatingPreheatProgressionShadow,loadHeatingPreheatShadow,loadPvFlex,shiftDay,todayAmsterdam} from "../state/pv-flex-state.js";
const $=id=>document.getElementById(id); let day=todayAmsterdam();
const kwh=v=>typeof v==="number"&&Number.isFinite(v)?v.toLocaleString("nl-NL",{minimumFractionDigits:1,maximumFractionDigits:2})+" kWh":"—";
const pct=v=>typeof v==="number"&&Number.isFinite(v)?Math.round(v*100)+"%":"—";
const time=x=>new Date(x).toLocaleTimeString("nl-NL",{timeZone:"Europe/Amsterdam",hour:"2-digit",minute:"2-digit"});
const available=v=>typeof v==="number"&&Number.isFinite(v);
const power=v=>available(v)?(v/1000).toLocaleString("nl-NL",{maximumFractionDigits:2})+" kW":"—";
const measuredW=v=>available(v)?power(v):"— (geen apparaatmeting)";
const planW=v=>available(v)?power(v):"— (niet vastgelegd)";
const stamp=v=>v?new Date(v).toLocaleString("nl-NL",{timeZone:"Europe/Amsterdam",hour:"2-digit",minute:"2-digit",second:"2-digit"}):"—";
const MIN_COVERAGE=0.95;

// End-of-slot and independent P1/PV evidence: zero coverage is never 0 kWh.
// Open/future 15-minute intervals must not be reported as completed outcomes.
function slotEvidence(slot,nowMs=Date.now()){
 const start=Date.parse(slot.start);
 const end=slot.end?Date.parse(slot.end):start+900000;
 const phase=nowMs<start?"FUTURE":nowMs<end?"OPEN":"CLOSED";
 const a=slot.actual||{};
 const p1=phase==="CLOSED"&&available(a.p1Coverage)&&a.p1Coverage>=MIN_COVERAGE&&
  available(a.importKWh)&&available(a.exportKWh);
 const pv=phase==="CLOSED"&&available(a.pvCoverage)&&a.pvCoverage>=MIN_COVERAGE&&
  available(a.pvKWh);
 const comparable=!!slot.plan&&!!slot.forecast&&available(slot.forecast.pvForecastW)&&p1&&pv;
 return {phase,p1,pv,comparable};
}
function summary(d){
 $("day-title").textContent=new Date(d.period.start).toLocaleDateString("nl-NL",{timeZone:"Europe/Amsterdam",weekday:"long",day:"numeric",month:"long",year:"numeric"});
 const matched=d.series.filter(x=>slotEvidence(x).comparable);
 const forecast=matched.length?matched.reduce((sum,x)=>sum+x.forecast.pvForecastW/4000,0):null;
 const actual=matched.length?matched.reduce((sum,x)=>sum+x.actual.pvKWh,0):null;
 $("kpi-forecast").textContent=kwh(forecast);
 $("kpi-pv").textContent=kwh(actual);
 $("kpi-slots").textContent=matched.length+" vergelijkbare kwartieren · "+(d.summary.planSlots||0)+" besluiten";
 $("kpi-pv-note").textContent=matched.length+" kwartieren · zelfde periode als PV-forecast";
 const validatedSelf=matched.filter(x=>available(x.actual.pvSelfConsumedKWh));
 $("kpi-self").textContent=validatedSelf.length? kwh(validatedSelf.reduce((sum,x)=>sum+Math.max(0,x.actual.pvSelfConsumedKWh),0)): "—";
 $("kpi-self-note").textContent=validatedSelf.length+" kwartieren met gevalideerd direct PV-gebruik";
 $("kpi-export").textContent=matched.length?kwh(matched.reduce((sum,x)=>sum+x.actual.exportKWh,0)):"—";
 $("kpi-export-note").textContent=matched.length+" vergelijkbare kwartieren";
 $("quality").textContent="Dekking kalenderdag "+pct(d.quality.actualCoverage);
 $("next").disabled=day>=todayAmsterdam();
 $("archive-status").textContent=d.historicalPlannerAvailable?
  "Historisch besluit: EV "+kwh(d.summary.plannedEvKWh)+" · boiler "+kwh(d.summary.plannedWwKWh)+
  " · Quooker "+kwh(d.summary.plannedQuookerKWh)+" · "+d.summary.planSlots+"/"+d.series.length+
  " geldige kwartieren. PV-KPI vergelijkt uitsluitend "+matched.length+" afgesloten kwartieren met voldoende P1/PV-dekking.":
  "V1-plannerarchief ontbreekt. Gemeten P1/PV blijft beschikbaar; geen terugval op V2.";
}
function slotAllocation(x,nowMs=Date.now()){
 const quality=slotEvidence(x,nowMs);
 const known=quality.p1&&quality.pv;
 const pvW=known?Math.max(0,x.actual.pvKWh*4000):0;
 const exportW=known?Math.min(pvW,Math.max(0,x.actual.exportKWh*4000)):0;
 const directPvW=known?Math.max(0,pvW-exportW):0;
 const houseW=known&&available(x.actual.houseKWh)?Math.max(0,x.actual.houseKWh*4000):null;
 const evActualW=available(x.devices?.evPowerW)?Math.max(0,x.devices.evPowerW):null;
 // No attribution without household balance and observed EV power.
 const evPvW=known&&houseW!==null&&evActualW!==null?
  Math.min(evActualW,directPvW,Math.max(0,pvW-Math.max(0,houseW-evActualW))):0;
 const otherPvW=known?Math.max(0,directPvW-evPvW):0;
 return {pvW,exportW,directPvW,houseW,evActualW,evPvW,otherPvW,actualKnown:known};
}
function renderEvidence(slot,nowMs=Date.now()){
 const root=$("decision-evidence");root.replaceChildren();
 if(!slot){$("evidence-time").textContent="—";return;}
 const q=slotEvidence(slot,nowMs);
 const state=q.phase==="OPEN"?"LOPEND · voorlopig":q.phase==="FUTURE"?"TOEKOMST · nog niet uitgevoerd":"AFGESLOTEN";
 $("evidence-time").textContent=time(slot.start)+" · "+state;
 const plan=slot.plan, actual=slot.actual||{},devices=slot.devices||{};
 const deviceNote=q.phase==="OPEN"?" (voorlopige apparaatwaarde)":q.phase==="FUTURE"?" (nog niet uitgevoerd)":"";
 const evKnown=q.phase!=="FUTURE"&&available(devices.evPowerW);
 const wwKnown=q.phase!=="FUTURE"&&available(devices.boilerPowerW);
 const noEvidence=q.phase!=="CLOSED"?"— (kwartier nog niet afgesloten)":"— (onvoldoende meetdekking)";
 const verdict=!plan?"Geen geldig historisch plannerbesluit":q.phase!=="CLOSED"?
  "Nog geen beoordeling: kwartier niet afgesloten":!q.p1||!q.pv?
  "Onvoldoende meetgegevens: P1/PV-dekking onvolledig":
  "Besluit en gemeten resultaat beschikbaar; oorzaak/kwaliteit niet automatisch bewezen";
 const cells=[
  ["1. Informatie",[
   "Besluit vastgelegd: "+stamp(plan?.generatedAt),
   "PV verwacht: "+planW(slot.forecast?.pvForecastW),
   "Confidence: "+(available(slot.forecast?.confidence)?pct(slot.forecast.confidence):"—"),
   "EV beschikbaar (prognose): "+(plan?.teslaAvailableForecast==null?"—":plan.teslaAvailableForecast?"Ja":"Nee"),
   "Warmwaterbron: "+(plan?.wwSourceMode||"—")
  ]],
  ["2. Beslissing",[
   "Tesla: "+planW(plan?.evPlanW)+" · "+(plan?.evReason||"reden onbekend"),
   "Boiler: "+planW(plan?.wwPlanW)+" · "+(plan?.wwReason||"reden onbekend"),
   "Quooker: "+planW(plan?.quookerPlanW)+" · "+(plan?.quookerMode||"modus onbekend"),
   "PV-opportunity Quooker: "+(plan?.quookerOpportunityAllowed==null?"—":plan.quookerOpportunityAllowed?"toegestaan":"niet toegestaan"),
   "Net gepland: import "+planW(plan?.gridImportAfterFlexW)+" / export "+planW(plan?.gridExportAfterFlexW)
  ]],
  ["3. Uitvoering",[
   "Tesla werkelijk: "+(evKnown?measuredW(devices.evPowerW)+deviceNote:"— (niet beschikbaar)"),
   "Boiler werkelijk: "+(wwKnown?measuredW(devices.boilerPowerW)+deviceNote:"— (niet beschikbaar)"),
   "Quooker werkelijk: — (niet gemeten in deze API)",
   "Heating: "+(slot.heatingFlex?.intent?"shadow-intent vastgelegd":"geen aangetoonde shadow-intent")
  ]],
  ["4. Resultaat",[
   "PV gemeten: "+(q.pv?kwh(actual.pvKWh):noEvidence),
   "Import: "+(q.p1?kwh(actual.importKWh):noEvidence),
   "Export: "+(q.p1?kwh(actual.exportKWh):noEvidence),
   "Direct PV-gebruik: "+(q.comparable&&available(actual.pvSelfConsumedKWh)?kwh(actual.pvSelfConsumedKWh):noEvidence),
   "Dekking P1/PV: "+pct(actual.p1Coverage)+" / "+pct(actual.pvCoverage)
  ]],
  ["5. Beoordeling",[
   verdict,
   "EV uitvoering: "+(!plan||!evKnown?"onvoldoende bewijs":"plan "+planW(plan.evPlanW)+" / apparaat "+measuredW(devices.evPowerW)+deviceNote),
   "Boiler uitvoering: "+(!plan||!wwKnown?"onvoldoende bewijs":"plan "+planW(plan.wwPlanW)+" / apparaat "+measuredW(devices.boilerPowerW)+deviceNote),
   "Quooker: daadwerkelijke uitvoering niet vastgesteld",
   "Een verschil is geen bewezen uitvoeringsfout; realtime controlreden ontbreekt",
   "Gemiste kans: niet beoordeeld (haalbare benchmark ontbreekt)"
  ]]
 ];
 for(const [heading,lines] of cells){
  const card=document.createElement("article");card.className="evidence-step";
  const headingNode=document.createElement("strong");headingNode.textContent=heading;
  const text=document.createElement("p");text.textContent=lines.join("\n");
  card.append(headingNode,text);root.append(card);
 }
}

// Mouse hover is for a single *visible* curve or stacked measured bar.
// Intent/history details belong to the selected-quarter evidence panel.
function closestEvaluationSeries(slots,allocated,index,px,py,view){
 const {left,top,height,step,max,radius}=view;
 const cx=i=>left+(i+0.5)*step;
 const y=v=>top+height-v/max*height;
 let best=null,dist=radius;
 const lines=[
  ["pvForecastW","PV-forecast bij besluit",s=>s.forecast?.pvForecastW],
  ["evPlanW","Tesla gepland",s=>s.plan?.evPlanW],
  ["wwPlanW","Warm water gepland",s=>s.plan?.wwPlanW],
  ["quookerPlanW","Quooker gepland",s=>s.plan?.quookerPlanW]
 ];
 for(const [key,label,read] of lines){
  for(const j of [index-1,index]){
   if(j<0||j>=slots.length-1)continue;
   const a=read(slots[j]),b=read(slots[j+1]);
   if(!available(a)||!available(b)||(a===0&&b===0))continue;
   const x1=cx(j),x2=cx(j+1),y1=y(a),y2=y(b),dx=x2-x1,dy=y2-y1;
   const f=Math.max(0,Math.min(1,((px-x1)*dx+(py-y1)*dy)/(dx*dx+dy*dy)));
   const distance=Math.hypot(px-(x1+dx*f),py-(y1+dy*f));
   if(distance<dist){
    dist=distance;best={label,value:read(slots[index])};
   }
  }
 }
 if(best)return best;
 const a=allocated[index];
 if(!a?.actualKnown||Math.abs(px-cx(index))>step*.34)return null;
 let bottom=top+height;
 for(const [label,w] of [
  ["EV uit PV",a.evPvW],["Overig eigen PV",a.otherPvW],["Export werkelijk",a.exportW]
 ]){
  if(w<=0)continue;
  const upper=bottom-w/max*height;
  if(py>=upper&&py<=bottom)return {label,value:w};
  bottom=upper;
 }
 return null;
}
function chart(d){
 const svg=$("pv-chart"),tip=$("tooltip"),a=d.series;svg.replaceChildren();
 const nowMs=Date.now();
 const has=a.some(x=>slotEvidence(x,nowMs).pv||x.plan);
 $("empty").hidden=has;svg.hidden=!has;
 if(!has){tip.hidden=true;renderEvidence(null,nowMs);return;}
 const W=1000,H=330,p={l:52,r:18,t:18,b:40},iw=W-p.l-p.r,ih=H-p.t-p.b,ns="http://www.w3.org/2000/svg";
 const allocated=a.map(s=>slotAllocation(s,nowMs));
 const max=Math.max(100,...a.flatMap((x,i)=>[
  allocated[i].pvW,x.forecast?.pvForecastW||0,x.plan?.evPlanW||0,
  x.plan?.wwPlanW||0,x.plan?.quookerPlanW||0
 ]));
 svg.setAttribute("viewBox","0 0 "+W+" "+H);
 const add=(t,z,txt)=>{
  const e=document.createElementNS(ns,t);
  Object.entries(z).forEach(([k,v])=>e.setAttribute(k,v));
  if(txt!=null)e.textContent=txt;
  svg.appendChild(e);return e;
 };
 for(let i=0;i<=4;i++){
  const y=p.t+ih*i/4;
  add("line",{x1:p.l,y1:y,x2:W-p.r,y2:y,class:"gridline"});
  add("text",{x:p.l-7,y:y+4,class:"axis","text-anchor":"end"},(max*(4-i)/4000).toFixed(1)+"kW");
 }
 const step=iw/a.length;
 let selectedIndex=-1;
 for(let i=a.length-1;i>=0;i--){
  if(slotEvidence(a[i],nowMs).comparable){selectedIndex=i;break;}
 }
 if(selectedIndex<0)selectedIndex=a.findIndex(x=>x.plan);
 if(selectedIndex<0)selectedIndex=0;
 const selectedRect=add("rect",{
  x:p.l+selectedIndex*step,y:p.t,width:step,height:ih,class:"selected-quarter"
 });
 for(let i=0;i<a.length;i++){
  const q=slotEvidence(a[i],nowMs);
  if(q.phase==="OPEN")add("rect",{
   x:p.l+i*step,y:p.t,width:step,height:ih,class:"provisional-quarter"
  });
 }
 const points=[];
 a.forEach((slot,i)=>{
  const cx=p.l+(i+.5)*step,s=allocated[i],barW=step*.68;
  const heat=slot.heatingFlex||{};
  if(heat.opportunity)add("rect",{x:p.l+i*step,y:p.t+ih+4,width:step,height:5,class:"heating-opportunity-lane"});
  if(heat.intent)add("rect",{x:p.l+i*step,y:p.t+ih+12,width:step,height:5,class:"heating-intent-lane"});
  let y=p.t+ih;
  if(s.actualKnown){
   for(const [w,cls] of [[s.evPvW,"pv-ev"],[s.otherPvW,"pv-self"],[s.exportW,"pv-export"]]){
    const h=w/max*ih;
    if(h>0){y-=h;add("rect",{x:cx-barW/2,y,width:barW,height:h,class:cls});}
   }
  }
  points.push(slot.forecast?cx+","+(p.t+ih-slot.forecast.pvForecastW/max*ih):null);
  if(i%8===0)add("text",{x:cx,y:H-15,class:"axis","text-anchor":"middle"},time(slot.start));
  const hit=add("rect",{x:p.l+i*step,y:p.t,width:step,height:ih,class:"hit"});
  hit.addEventListener("mousemove",event=>{
   const matrix=svg.getScreenCTM();
   if(!matrix){tip.hidden=true;return;}
   const point=svg.createSVGPoint();
   point.x=event.clientX;point.y=event.clientY;
   const pos=point.matrixTransform(matrix.inverse());
   const scale=Math.hypot(matrix.a,matrix.b);
   const hover=closestEvaluationSeries(a,allocated,i,pos.x,pos.y,{
    left:p.l,top:p.t,height:ih,step,max,radius:11/scale
   });
   if(!hover||!available(hover.value)){tip.hidden=true;return;}
   tip.replaceChildren();
   const title=document.createElement("strong");title.textContent=time(slot.start);
   const detail=document.createElement("span");detail.textContent=hover.label+": "+power(hover.value);
   tip.append(title,detail);
   tip.hidden=false;
   const rect=svg.parentElement.getBoundingClientRect();
   tip.style.left=Math.min(Math.max(8,rect.width-tip.offsetWidth-8),
    Math.max(8,event.clientX-rect.left+10))+"px";
   tip.style.top=Math.min(Math.max(8,rect.height-tip.offsetHeight-8),
    Math.max(8,event.clientY-rect.top-tip.offsetHeight-12))+"px";
  });
  hit.addEventListener("mouseleave",()=>tip.hidden=true);
  hit.addEventListener("click",()=>{
   selectedIndex=i;selectedRect.setAttribute("x",p.l+i*step);
   renderEvidence(slot,Date.now());
  });
 });
 const plotSegments=(values,cls)=>{
  let segment=[];
  const flush=()=>{if(segment.length>1)add("polyline",{points:segment.join(" "),class:cls,fill:"none"});segment=[];};
  for(const value of values){if(value==null)flush();else segment.push(value);}
  flush();
 };
 plotSegments(points,"forecast-line");
 for(const [field,cls] of [
  ["evPlanW","planned-ev-line"],["wwPlanW","planned-ww-line"],["quookerPlanW","planned-quooker-line"]
 ]){
  plotSegments(a.map((slot,i)=>available(slot.plan?.[field])?
   (p.l+(i+.5)*step)+","+(p.t+ih-slot.plan[field]/max*ih):null),cls);
 }
 renderEvidence(a[selectedIndex],nowMs);
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