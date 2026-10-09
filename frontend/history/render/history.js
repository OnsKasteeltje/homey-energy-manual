import { loadHistory, shiftAnchor, todayAmsterdam } from "../state/history-state.js";

const $ = id => document.getElementById(id);
const tabs = [...document.querySelectorAll("[data-kind]")];
let kind = "day";
let anchor = todayAmsterdam();
let current = null;

function isCurrentPeriod() {
  const today = todayAmsterdam();
  if (kind === "day") return anchor >= today;
  if (kind === "month") return anchor.slice(0,7) >= today.slice(0,7);
  if (kind === "year") return anchor.slice(0,4) >= today.slice(0,4);
  if (kind === "week") {
    return shiftAnchor("week", anchor, 1) > today;
  }
  return false;
}

function updateNavigation() {
  $("period-next").disabled = isCurrentPeriod();
}

function kwh(value) { return value==null?"—":`${Number(value).toLocaleString("nl-NL",{minimumFractionDigits:1,maximumFractionDigits:2})} kWh`; }
function known(item,key){return typeof item?.knownFraction?.[key]==="number" && item.knownFraction[key]>=0.999999;}
function fmtField(item,key){const f=item?.knownFraction?.[key];if(f===undefined||f===0)return "Onbekend";return f<0.999999?`${kwh(item[key])} bekend (onvolledig)`:kwh(item[key]);}
function pct(value) { return `${Math.round(Number(value || 0) * 100)}%`; }
function dateLabel(data) {
  const start = new Date(data.period.start);
  const opts = {timeZone:"Europe/Amsterdam"};
  if (kind === "day") return start.toLocaleDateString("nl-NL",{...opts,weekday:"long",day:"numeric",month:"long",year:"numeric"});
  if (kind === "week") return `Week van ${start.toLocaleDateString("nl-NL",{...opts,day:"numeric",month:"long",year:"numeric"})}`;
  if (kind === "month") return start.toLocaleDateString("nl-NL",{...opts,month:"long",year:"numeric"});
  return start.toLocaleDateString("nl-NL",{...opts,year:"numeric"});
}
function bucketLabel(item) {
  const d = new Date(item.start);
  const opts={timeZone:"Europe/Amsterdam"};
  if (kind === "day") return d.toLocaleTimeString("nl-NL",{...opts,hour:"2-digit",minute:"2-digit"});
  if (kind === "week" || kind === "month") return d.toLocaleDateString("nl-NL",{...opts,day:"numeric",month:"short"});
  return d.toLocaleDateString("nl-NL",{...opts,month:"short"});
}
function renderSummary(data) {
  for(const [key,label,detail,normal] of [
    ["houseKWh","kpi-house","kpi-house-detail","import + PV − export"],
    ["pvKWh","kpi-pv","kpi-pv-detail","3 omvormers"]
  ]){
    const complete=data.quality?.metricQuality?.[key]?.completeWithinMeasuredIntervals===true;
    $(label).textContent=complete?kwh(data.summary[key]):"—";
    $(detail).textContent=complete?normal:`Onvolledig · ${kwh(data.summary[key])} bekend`;
  }
  $("kpi-import").textContent=kwh(data.summary.importKWh);
  $("kpi-export").textContent=kwh(data.summary.exportKWh);
  $("period-title").textContent=dateLabel(data);
  $("bucket-label").textContent=({day:"UUR",week:"DAG",month:"DAG",year:"MAAND"})[kind];
  $("coverage").textContent=`Dekking ${pct(data.quality.coverage)}`;
  $("gaps").textContent=`Gaps ${data.quality.gapCount}`;
  $("discontinuities").textContent=`Discontinuïteiten ${data.quality.discontinuityCount}`;
  const houseQ=data.quality?.metricQuality?.houseKWh;
  $("history-quality").textContent=houseQ?.completeWithinMeasuredIntervals===true?
    `Dekking ${pct(data.quality.coverage)}`:
    "Huisverbruik onvolledig · P1 apart beschikbaar";
}
function renderChart(data) {
  const svg=$("history-chart"), tooltip=$("chart-tooltip");
  svg.replaceChildren();
  const series=data.series || [];
  const hasData=series.some(x=>x.coverage>0);
  $("chart-empty").hidden=hasData; svg.hidden=!hasData;
  if(!hasData) return;
  const W=1000,H=360,p={l:52,r:18,t:20,b:48}, iw=W-p.l-p.r, ih=H-p.t-p.b;
  const max=Math.max(0.1,...series.flatMap(x=>[x.houseKWh,x.pvKWh,x.importKWh,x.exportKWh].filter((v,j)=>known(x,["houseKWh","pvKWh","importKWh","exportKWh"][j])).map(v=>Math.max(0,Number(v)||0))));
  svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
  const ns="http://www.w3.org/2000/svg";
  const add=(tag,attrs,text)=>{const el=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v));if(text!=null)el.textContent=text;svg.appendChild(el);return el;};
  for(let i=0;i<=4;i++){const y=p.t+ih*i/4;add("line",{x1:p.l,y1:y,x2:W-p.r,y2:y,class:"gridline"});add("text",{x:p.l-8,y:y+4,class:"axis-label","text-anchor":"end"},kwh(max*(4-i)/4).replace(" kWh",""));}
  const step=iw/series.length, bar=Math.max(2,Math.min(12,step*.18));
  const keys=[["houseKWh","bar-house"],["pvKWh","bar-pv"],["importKWh","bar-grid"],["exportKWh","bar-export"]];
  series.forEach((item,i)=>{
    const gx=p.l+i*step;
    keys.forEach(([key,cls],j)=>{
      const x=gx+step*.08+j*bar;
      if(item.coverage>0&&!known(item,key)){
        add("text",{x:x+bar*.3,y:p.t+ih-7,class:"missing-energy","text-anchor":"middle"},"?");
        return; // Null/partial values are unknown, never a zero-height bar.
      }
      const value=Math.max(0,Number(item[key])||0),h=value/max*ih;
      add("rect",{x,y:p.t+ih-h,width:bar*.82,height:h,class:cls,rx:2});
    });
    if(series.length<=31 || i%Math.ceil(series.length/12)===0)add("text",{x:gx+step/2,y:H-20,class:"axis-label","text-anchor":"middle"},bucketLabel(item));
    const hit=add("rect",{x:gx,y:p.t,width:step,height:ih,class:"hit"});
    hit.addEventListener("mousemove",e=>{tooltip.hidden=false;tooltip.innerHTML=`<strong>${bucketLabel(item)}</strong><span>Huis ${fmtField(item,"houseKWh")}</span><span>PV ${fmtField(item,"pvKWh")}</span><span>SolarEdge ${fmtField(item,"pvSolarEdgeKWh")}</span><span>GoodWe 4200 ${fmtField(item,"pvGoodWe4200KWh")}</span><span>GoodWe 2000 ${fmtField(item,"pvGoodWe2000KWh")}</span><span>Netafname ${fmtField(item,"importKWh")}</span><span>Teruglevering ${fmtField(item,"exportKWh")}</span><em>Dekking ${pct(item.coverage)}</em>`;const r=$("chart-wrap").getBoundingClientRect();tooltip.style.left=`${Math.min(r.width-190,Math.max(8,e.clientX-r.left+12))}px`;tooltip.style.top=`${Math.max(8,e.clientY-r.top-90)}px`;});
    hit.addEventListener("mouseleave",()=>tooltip.hidden=true);
  });
}
async function refresh(){
  $("history-quality").textContent="Laden…";
  try{current=await loadHistory(kind,anchor);renderSummary(current);renderChart(current);updateNavigation();}
  catch(error){$("history-quality").textContent="History niet beschikbaar";$("chart-empty").hidden=false;$("chart-empty").textContent=error.message;$("history-chart").hidden=true;}
}
tabs.forEach(tab=>tab.addEventListener("click",()=>{kind=tab.dataset.kind;tabs.forEach(x=>x.classList.toggle("active",x===tab));refresh();}));
$("period-prev").addEventListener("click",()=>{anchor=shiftAnchor(kind,anchor,-1);refresh();});
$("period-next").addEventListener("click",()=>{if(!isCurrentPeriod()){anchor=shiftAnchor(kind,anchor,1);refresh();}});
refresh();