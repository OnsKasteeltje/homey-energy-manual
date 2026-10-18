const $ = id => document.getElementById(id);
const ZONE = "Europe/Amsterdam";
function todayAmsterdam(){
  const parts=Object.fromEntries(new Intl.DateTimeFormat("en-CA",{
    timeZone:ZONE,year:"numeric",month:"2-digit",day:"2-digit"
  }).formatToParts(new Date()).map(x=>[x.type,x.value]));
  return parts.year+"-"+parts.month+"-"+parts.day;
}
function shiftDay(day,step){
  const [year,month,date]=day.split("-").map(Number);
  const d=new Date(Date.UTC(year,month-1,date,12));
  d.setUTCDate(d.getUTCDate()+step);
  return d.toISOString().slice(0,10);
}
let day=shiftDay(todayAmsterdam(),-1);
let requestId=0;
const present=v=>typeof v==="number" && Number.isFinite(v);
const fmt=(v,d=2)=>present(v)?v.toLocaleString("nl-NL",{minimumFractionDigits:d,maximumFractionDigits:d}):"—";
const kwh=v=>present(v)?fmt(v)+" kWh":"—";
const percent=v=>present(v)?fmt(v*100,0)+"%":"—";
const temp=v=>present(v)?fmt(v,1)+" °C":"—";
function dayLabel(value){
  return new Date(value+"T12:00:00Z").toLocaleDateString("nl-NL",{
    timeZone:"UTC",weekday:"long",day:"numeric",month:"long",year:"numeric"
  });
}
function el(tag,className,textValue){
  const node=document.createElement(tag);
  if(className)node.className=className;
  if(textValue!==undefined)node.textContent=textValue;
  return node;
}
function renderBars(periods){
  const data=periods.flatMap(p=>[p.quatt.electricKWh,p.energy.exportKWh])
    .filter(present);
  const max=Math.max(0.1,...data);
  const wrap=$("dayparts");
  wrap.replaceChildren();
  for(const period of periods){
    const group=el("div","daypart");
    group.appendChild(el("span","daypart-label",period.label));
    const pair=el("div","bar-pair");
    for(const [kind,value] of [
      ["quatt",period.quatt.electricKWh],
      ["export",period.energy.exportKWh]
    ]){
      const line=el("div","bar-line");
      const track=el("div","bar-track");
      track.setAttribute("aria-hidden","true");
      const fill=el("div","bar-fill"+(kind==="export"?" export":""));
      fill.style.width=present(value)?(Math.max(0,Math.min(100,value/max*100))+"%"):"0%";
      track.appendChild(fill);
      line.append(track,el("span","bar-value",kwh(value)));
      pair.appendChild(line);
    }
    group.appendChild(pair);
    wrap.appendChild(group);
  }
  wrap.setAttribute("aria-label",periods.map(p=>
    p.label+": Quatt "+kwh(p.quatt.electricKWh)+", export "+kwh(p.energy.exportKWh)
  ).join("; "));
}
function renderRooms(rooms){
  const tbody=$("rooms");
  tbody.replaceChildren();
  for(const room of rooms){
    const tr=el("tr");
    const cols=[
      room.name,temp(room.firstTemperatureC),temp(room.lastTemperatureC),
      temp(room.lastSetpointC),
      present(room.belowSetpointBy02CSlots)&&present(room.completePairedSlots)?
        room.belowSetpointBy02CSlots+"/"+room.completePairedSlots:"—",
      percent(room.coverage)
    ];
    for(const value of cols)tr.appendChild(el("td",null,value));
    tbody.appendChild(tr);
  }
}
function render(d){
  $("report").hidden=false;
  $("page-message").hidden=true;
  $("freshness").textContent="Daganalyse · "+d.quality.status;
  $("kpi-quatt").textContent=kwh(d.quatt.electricKWh);
  $("kpi-thermal").textContent=kwh(d.quatt.hp1HeatSensorKWh);
  $("kpi-import").textContent=kwh(d.energy.importKWh);
  $("kpi-export").textContent=kwh(d.energy.exportKWh);
  $("quality").textContent="Kwaliteit: "+d.quality.status;
  $("coverage").textContent="P1/PV gekoppeld: "+percent(d.energy.pairedCoverage);
  $("hp-coverage").textContent="Quatt: "+d.quatt.completeSlots+"/"+d.quatt.expectedSlots+" kwartieren";
  $("pv-provenance").textContent="PV held "+fmt(d.energy.heldPvHours,1)+"u · estimated "+fmt(d.energy.estimatedPvHours,1)+"u";
  renderBars(d.periods);
  renderRooms(d.rooms);
  $("outside").textContent=temp(d.quatt.outsideTempMeanC);
  $("heating").textContent=percent(d.quatt.heatingSignalMean);
  $("ratio").textContent=present(d.quatt.hp1HeatToElectricRatio)?
    fmt(d.quatt.hp1HeatToElectricRatio,2)+" (indicatief)":"—";
  $("cic").textContent=present(d.cic.boilerSelectedSamples)?
    d.cic.boilerSelectedSamples+" samples":"—";
  $("gas").textContent=present(d.cic.gasObservedSpanDeltaM3)?
    fmt(d.cic.gasObservedSpanDeltaM3,3)+" m³ (meetspan)":"—";
  $("issues").textContent=d.quality.issues.length?
    "Datakwaliteit: "+d.quality.issues.join(", "):
    "Geen kwaliteitsproblemen gemeld in dit dagrapport.";
}
async function load(){
  const id=++requestId;
  $("day-title").textContent=dayLabel(day);
  $("next").disabled=day>=shiftDay(todayAmsterdam(),-1);
  $("page-message").hidden=false;
  $("page-message").textContent="Daganalyse laden…";
  $("report").hidden=true;
  $("freshness").textContent="Historie laden…";
  try{
    const response=await fetch("/web/analysis/heating/day/"+encodeURIComponent(day),{cache:"no-store"});
    if(id!==requestId)return;
    if(response.status===404){
      $("page-message").textContent="Voor deze datum is nog geen automatische verwarmingsanalyse gearchiveerd.";
      $("freshness").textContent="Geen dagrapport";
      return;
    }
    if(!response.ok)throw new Error("API "+response.status);
    const data=await response.json();
    if(id!==requestId)return;
    if(data.schema!=="EMS_WEB_HEATING_DAILY_V1"||data.dateLocal!==day||
      data.readOnly!==true||data.controlWrites!==false||data.controlMode!=="SHADOW"||
      !Array.isArray(data.rooms)||data.rooms.length!==8||
      !Array.isArray(data.periods)||data.periods.length!==4){
      throw new Error("Ongeldig verwarmingsrapport");
    }
    render(data);
  }catch(error){
    if(id!==requestId)return;
    $("page-message").textContent="Het verwarmingsrapport is niet beschikbaar ("+error.message+").";
    $("freshness").textContent="Analyse niet beschikbaar";
  }
}
$("prev").addEventListener("click",()=>{day=shiftDay(day,-1);load();});
$("next").addEventListener("click",()=>{
  const next=shiftDay(day,1);
  if(next<todayAmsterdam()){day=next;load();}
});
load();
