import {loadPvFlex,shiftDay,todayAmsterdam} from "../state/pv-flex-state.js";
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
function chart(d){
 const svg=$("pv-chart"), tip=$("tooltip"), a=d.series; svg.replaceChildren(); const has=a.some(x=>x.actual.coverage>0||x.forecast); $("empty").hidden=has; svg.hidden=!has;if(!has)return;
 const W=1000,H=330,p={l:52,r:18,t:18,b:40},iw=W-p.l-p.r,ih=H-p.t-p.b,ns="http://www.w3.org/2000/svg";
 const watts=x=>Number(x.actual.pvKWh||0)*4000, max=Math.max(100,...a.flatMap(x=>[watts(x),x.forecast?.pvForecastW||0]));
 svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
 const add=(t,z,txt)=>{const e=document.createElementNS(ns,t);Object.entries(z).forEach(([k,v])=>e.setAttribute(k,v));if(txt!=null)e.textContent=txt;svg.appendChild(e);return e;};
 for(let i=0;i<=4;i++){let y=p.t+ih*i/4;add("line",{x1:p.l,y1:y,x2:W-p.r,y2:y,class:"gridline"});add("text",{x:p.l-7,y:y+4,class:"axis","text-anchor":"end"},`${Math.round(max*(4-i)/400)/10}kW`);}
 const step=iw/a.length, points=[];
 a.forEach((x,i)=>{const cx=p.l+(i+.5)*step,v=watts(x),h=v/max*ih;add("rect",{x:cx-step*.34,y:p.t+ih-h,width:step*.68,height:h,class:"pvbar",rx:2});if(x.forecast)points.push(`${cx},${p.t+ih-(x.forecast.pvForecastW/max*ih)}`);
 if(i%8===0)add("text",{x:cx,y:H-15,class:"axis","text-anchor":"middle"},time(x.start));
 const hit=add("rect",{x:p.l+i*step,y:p.t,width:step,height:ih,class:"hit"});hit.addEventListener("mousemove",e=>{tip.hidden=false;tip.innerHTML=`<strong>${time(x.start)}</strong><span>PV werkelijk ${(v/1000).toFixed(2)} kW</span><span>Forecast ${x.forecast?(x.forecast.pvForecastW/1000).toFixed(2)+" kW":"—"}</span><span>Confidence ${x.forecast?.confidence!=null?Math.round(x.forecast.confidence*100)+"%":"—"}</span><span>Lead ${x.forecast?.leadMinutes??"—"} min</span><span>Export ${kwh(x.actual.exportKWh)}</span>`;const r=svg.parentElement.getBoundingClientRect();tip.style.left=`${Math.min(r.width-190,Math.max(8,e.clientX-r.left+10))}px`;tip.style.top=`${Math.max(8,e.clientY-r.top-80)}px`;});hit.addEventListener("mouseleave",()=>tip.hidden=true);});
 if(points.length>1)add("polyline",{points:points.join(" "),class:"forecast-line",fill:"none"});
}
async function refresh(){ $("quality").textContent="Laden…";try{const d=await loadPvFlex(day);summary(d);chart(d);}catch(e){$("quality").textContent="Analyse niet beschikbaar";$("empty").hidden=false;$("empty").textContent=e.message;$("pv-chart").hidden=true;}}
$("prev").addEventListener("click",()=>{day=shiftDay(day,-1);refresh();});$("next").addEventListener("click",()=>{if(day<todayAmsterdam()){day=shiftDay(day,1);refresh();}});refresh();