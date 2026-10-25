import {loadDailyPerformance,loadPvFlex,loadGoodweCloudEvidence,shiftDay,todayAmsterdam} from "../state/pv-flex-state.js";
const $=id=>document.getElementById(id); let day=todayAmsterdam();
const pct=v=>typeof v==="number"&&Number.isFinite(v)?Math.round(v*100)+"%":"—";
const time=x=>new Date(x).toLocaleTimeString("nl-NL",{timeZone:"Europe/Amsterdam",hour:"2-digit",minute:"2-digit"});
const available=v=>typeof v==="number"&&Number.isFinite(v);
const power=v=>available(v)?(v/1000).toLocaleString("nl-NL",{maximumFractionDigits:2})+" kW":"—";
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
// Historic decisions are shown for closed quarters; current Pi PV covers
// the running quarter and the future. No archived snapshot is rewritten.
const slotEndMs=s=>{
 const end=Date.parse(s.end);
 return Number.isFinite(end)?end:Date.parse(s.start)+900000;
};
const decisionPvW=(s,nowMs=Date.now())=>{
 if(slotEndMs(s)>nowMs)return null;
 if(available(s.forecast?.pvForecastW))return s.forecast.pvForecastW;
 return available(s.historicalPvDisplay?.pvForecastW)?
  s.historicalPvDisplay.pvForecastW:null;
};
const currentFuturePvW=(s,nowMs=Date.now())=>
 slotEndMs(s)>nowMs&&available(s.currentPvForecastW)?s.currentPvForecastW:null;
// Extend the dashed series by one actual archived point to make the seam
// continuous; never interpolate across missing historical decision evidence.
function joinedPvForecasts(slots,nowMs=Date.now()){
 const historical=slots.map(s=>decisionPvW(s,nowMs));
 const current=slots.map(s=>currentFuturePvW(s,nowMs));
 const boundary=current.findIndex(v=>v!==null);
 if(boundary>0&&historical[boundary-1]!==null){
  current[boundary-1]=historical[boundary-1];
 }
 return {historical,current};
}
const dailyPct=v=>available(v)?(v*100).toLocaleString("nl-NL",{minimumFractionDigits:1,maximumFractionDigits:1})+"%":"—";
function summary(d){
 $("quality").textContent="Dekking kalenderdag "+pct(d.quality.actualCoverage);
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
// Hover exposes only the nearest visible curve or measured bar.
function closestEvaluationSeries(slots,allocated,index,px,py,view,nowMs=Date.now()){
 const {left,top,height,step,max,radius}=view;
 const cx=i=>left+(i+0.5)*step;
 const y=v=>top+height-v/max*height;
 let best=null,dist=radius;
 const lines=[
  ["pvForecastW","PV-forecast historisch",s=>decisionPvW(s,nowMs)],
  ["currentPvForecastW","PV-forecast actueel",s=>currentFuturePvW(s,nowMs)],
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
 const has=a.some(x=>slotEvidence(x,nowMs).pv||x.plan||currentFuturePvW(x,nowMs)!==null);
 $("empty").hidden=has;svg.hidden=!has;
 if(!has){tip.hidden=true;return;}
 const W=1000,H=330,p={l:52,r:18,t:18,b:40},iw=W-p.l-p.r,ih=H-p.t-p.b,ns="http://www.w3.org/2000/svg";
 const allocated=a.map(s=>slotAllocation(s,nowMs));
 const max=Math.max(100,...a.flatMap((x,i)=>[
  allocated[i].pvW,decisionPvW(x,nowMs)||0,currentFuturePvW(x,nowMs)||0,
  x.plan?.evPlanW||0,
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
 const points=[],currentPoints=[],forecastValues=joinedPvForecasts(a,nowMs);
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
  const historicalW=forecastValues.historical[i];
  const currentW=forecastValues.current[i];
  points.push(historicalW===null?null:cx+","+(p.t+ih-historicalW/max*ih));
  currentPoints.push(currentW===null?null:cx+","+(p.t+ih-currentW/max*ih));
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
   },nowMs);
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
 });
 const plotSegments=(values,cls)=>{
  let segment=[];
  const flush=()=>{if(segment.length>1)add("polyline",{points:segment.join(" "),class:cls,fill:"none"});segment=[];};
  for(const value of values){if(value==null)flush();else segment.push(value);}
  flush();
 };
 plotSegments(points,"forecast-line");
 plotSegments(currentPoints,"forecast-current-line");
 for(const [field,cls] of [
  ["evPlanW","planned-ev-line"],["wwPlanW","planned-ww-line"],["quookerPlanW","planned-quooker-line"]
 ]){
  plotSegments(a.map((slot,i)=>available(slot.plan?.[field])?
   (p.l+(i+.5)*step)+","+(p.t+ih-slot.plan[field]/max*ih):null),cls);
 }
}
function renderDailyReport(report,selectedDay){
 const labelDate=new Date(selectedDay+"T12:00:00Z").toLocaleDateString("nl-NL",{
  timeZone:"Europe/Amsterdam",day:"numeric",month:"long",year:"numeric"
 });
 $("daily-report-date").textContent=labelDate;
 const notes=$("daily-report-notes");notes.replaceChildren();
 const status=$("daily-report-status");
 const isToday=selectedDay>=todayAmsterdam();
 const valid=report&&report.dateLocal===selectedDay&&report.readOnly===true&&report.controlWrites===false;
 const accounting=valid?report.accounting||{}:{};
 const decimal=v=>available(v)?v.toLocaleString("nl-NL",{
  minimumFractionDigits:3,maximumFractionDigits:3
 })+" kWh":"—";
 $("report-pv").textContent=decimal(accounting.pvProducedKWh);
 $("report-self").textContent=decimal(accounting.pvSelfConsumedKWh);
 $("report-self-rate").textContent=valid?dailyPct(accounting.pvSelfConsumptionRate):"—";
 $("report-import").textContent=decimal(accounting.gridImportKWh);
 $("report-export").textContent=decimal(accounting.gridExportKWh);
 status.textContent=valid?(
  report.status==="PROVISIONAL"&&report.throughLocal?
  "Voorlopig · t/m "+time(report.throughLocal):
  report.status==="READY"?"Definitief · compleet":report.status==="PARTIAL"?
  "Definitief · gedeeltelijk":
  report.status==="INSUFFICIENT_EVIDENCE"&&isToday?
  "Voorlopig · onvoldoende meetbewijs":"Onvoldoende meetbewijs"
 ):(isToday?"Dag in uitvoering":"Niet beschikbaar");
 const lines=valid&&Array.isArray(report.lines)?(
  isToday?report.lines:report.lines.slice(2)
 ):[
  isToday?"Vandaag is nog niet afgerond; het definitieve dagrapport volgt na de dagelijkse verwerking om 00:20.":
  "Voor deze dag is nog geen dagrapport gearchiveerd. Bestaande kwartierhistorie blijft hierboven beschikbaar."
 ];
 for(const line of lines){
  const p=document.createElement("p");p.textContent=line;notes.append(p);
 }
}


function renderGoodweEvidence(data,daily){
 const host=$("goodwe-evidence");host.replaceChildren();
 const line=message=>{
  const p=document.createElement("p");p.textContent=message;host.appendChild(p);
 };
 // Time-stamped station PV curve is shadow evidence until accounting is validated.
 const curve=data?.historicalQuarterEvidence;
 if(curve?.status==="OBSERVED_PARTIAL_DAY"){
  line("SEMS+ historische curve: "+curve.completeQuarters+
       " gedekte kwartieren · "+curve.coveredQuarterKWh.toLocaleString("nl-NL",{
         maximumFractionDigits:2
       })+" kWh in die kwartieren (SHADOW, nog niet in huisbalans).");
 }
 // Durable day-counter source is independent of the 192-sample SHADOW ring.
 if(daily && available(daily.reportedDayKWh)){
  const amount=daily.reportedDayKWh.toLocaleString("nl-NL",{
   minimumFractionDigits:1,maximumFractionDigits:2
  });
  line("GoodWe SEMS+ dagtellers: "+amount+" kWh"+
       (daily.status==="LATE_DAY_COUNTER_OBSERVED"?
       " (laat op de dag ontvangen, niet gegarandeerd definitief)":
       " (voorlopig, tot laatste ontvangst)"));
  for(const inv of daily.devices||[]){
   line("Omvormer …"+inv.serialSuffix+": "+
        inv.reportedDayKWh.toLocaleString("nl-NL",{maximumFractionDigits:2})+
        " kWh dagteller");
  }
  line("Duurzaam opgeslagen tellerreeks; niet toegevoegd aan de kwartierbalken.");
 }else{
  line("Historische GoodWe-dagteller: "+
       (daily?.status||"niet beschikbaar")+
       ". Ontbrekende gegevens zijn onbekend, niet 0 kWh.");
 }
 if(!data){
  line("SEMS+ SHADOW-historie niet beschikbaar. Dit betekent niet 0 kWh productie.");
  return;
 }
 if(data.status==="NO_SAMPLES" || !data.devices?.length){
  line("Geen SEMS+ observaties voor deze datum in de rolling historie (maximaal 192 samples).");
  return;
 }
 line(data.sampleCount+" geldige SEMS+ observaties · laatste Pi-ontvangst "+
      (data.lastFetchedAt?time(data.lastFetchedAt):"—")+
      (data.ageMinutes>40&&data.dateLocal===todayAmsterdam()?" · mogelijk verouderd":"")+
      " · fysieke bronmeettijd onbekend");
 if(data.status==="OBSERVED_COUNTER_ONLY_UNVERIFIED_FRESHNESS"){
  line("SEMS+ levert alleen geldige energietellers; actueel omvormervermogen is onbekend, niet 0 W.");
 }
 for(const device of data.devices){
  const watts=available(device.lastPowerW)?power(device.lastPowerW):"onbekend";
  const delta=available(device.lifetimeCounterDeltaKWh)?
   device.lifetimeCounterDeltaKWh.toLocaleString("nl-NL",{minimumFractionDigits:1,maximumFractionDigits:3})+" kWh":
   "onbekend";
  line("GoodWe …"+device.serialSuffix+" · laatste ontvangen vermogen "+watts+
       " · tellerstijging "+delta+" over beschikbaar venster"+
       " ("+device.observations+" samples; "+device.counterEvidence+")");
 }
 line("SEMS+ draagt nog niet bij aan de canonieke PV/P1-balans; geen kwartierproductie gereconstrueerd.");
}

let refreshId=0;
async function refresh(){
 const selectedDay=day;
 const requestId=++refreshId;
 $("day-title").textContent=new Date(selectedDay+"T12:00:00Z").toLocaleDateString("nl-NL",{
  timeZone:"Europe/Amsterdam",weekday:"long",day:"numeric",month:"long",year:"numeric"
 });
 $("next").disabled=selectedDay>=todayAmsterdam();
 $("quality").textContent="Laden…";
 const [main,daily,goodwe]=await Promise.allSettled([
  loadPvFlex(selectedDay),loadDailyPerformance(selectedDay),
  loadGoodweCloudEvidence(selectedDay)
 ]);
 if(requestId!==refreshId)return; // Ignore stale requests after day navigation.
 renderGoodweEvidence(goodwe.status==="fulfilled"?goodwe.value:null,
  goodwe.status==="fulfilled"?goodwe.value.dailyCounters:null);
 if(main.status==="fulfilled"){
  try{summary(main.value);chart(main.value);}
  catch(e){$("quality").textContent="Analyse niet beschikbaar";$("empty").hidden=false;$("empty").textContent=e.message;$("pv-chart").hidden=true;}
 }else{
  $("quality").textContent="Analyse niet beschikbaar";
  $("empty").hidden=false;$("empty").textContent=main.reason?.message||"Geen data";
  $("pv-chart").hidden=true;
 }
 const report=selectedDay===todayAmsterdam()&&main.status==="fulfilled"?
  main.value.provisionalDailyReport:(daily.status==="fulfilled"?daily.value:null);
 renderDailyReport(report,selectedDay);
}
$("prev").addEventListener("click",()=>{day=shiftDay(day,-1);refresh();});
$("next").addEventListener("click",()=>{if(day<todayAmsterdam()){day=shiftDay(day,1);refresh();}});
refresh();
