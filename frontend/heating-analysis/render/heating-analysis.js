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
      room.name,
      present(room.belowSetpointBy02CSlots)&&present(room.completePairedSlots)?
        room.belowSetpointBy02CSlots+"/"+room.completePairedSlots:"—",
      percent(room.coverage)
    ];
    for(const value of cols)tr.appendChild(el("td",null,value));
    tbody.appendChild(tr);
  }
}

const svgNS="http://www.w3.org/2000/svg";
function svgNode(tag,attributes){
  const n=document.createElementNS(svgNS,tag);
  for(const [key,value] of Object.entries(attributes||{}))n.setAttribute(key,String(value));
  return n;
}
const localTime=stamp=>new Date(stamp).toLocaleTimeString("nl-NL",{
  timeZone:ZONE,hour:"2-digit",minute:"2-digit"
});
let temperatureData=null;
let selectedRoomKey="woonkamer";
function coolingText(value,strong,explanation){
  if(value?.status==="OBSERVED_WITH_QUATT_SIGNAL_OFF"&&present(value.coolingCPerHour)){
    $(strong).textContent=fmt(value.coolingCPerHour,2)+" °C/uur";
    $(explanation).textContent="Gemeten daling "+fmt(value.temperatureDropC,2)+" °C in "+
      (value.durationMinutes/60).toLocaleString("nl-NL",{maximumFractionDigits:2})+
      "u · "+localTime(value.fromAt)+"–"+localTime(value.toAt);
  }else{
    $(strong).textContent="Onvoldoende bewijs";
    $(explanation).textContent="Geen aaneengesloten afkoelperiode van minstens 1 uur, bij stabiel setpoint en Quatt-signaal uit.";
  }
}
function renderReaction(room){
  const events=room.responseEvents||[];
  const reached=events.filter(e=>e.status==="REACHED"&&present(e.minutesToTarget));
  if(reached.length){
    const e=reached[0];
    $("reaction").textContent=e.minutesToTarget+" minuten";
    $("reaction-explanation").textContent=localTime(e.at)+
      " · "+temp(e.fromTargetC)+" → "+temp(e.toTargetC)+
      (events.length>1?" · "+events.length+" geobserveerde verhogingen":"");
  }else if(events.some(e=>e.status==="ALREADY_AT_TARGET")){
    $("reaction").textContent="Doel al bereikt";
    $("reaction-explanation").textContent="Bij de herkenbare setpointverhoging was de kamer al binnen 0,2 °C van het nieuwe doel.";
  }else{
    $("reaction").textContent="Niet vast te stellen";
    $("reaction-explanation").textContent=events.length?
      "Doel niet betrouwbaar bereikt binnen 4 uur, tussentijds aangepast of meetgegevens ontbreken.":
      "Geen voldoende herkenbare doelverhoging in de geselecteerde dag.";
  }
}
function renderThermalChart(room,data){
  const svg=$("temperature-chart");
  svg.replaceChildren();
  const W=1150,H=410,left=58,right=67,top=22,bottom=55;
  const width=W-left-right,height=H-top-bottom;
  svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
  const samples=room.series;
  const quatt=data.quatt;
  const range=samples.flatMap(s=>[s.temperatureC,s.observedTargetC]).filter(present);
  const outside=quatt.map(q=>q.outsideTemperatureC).filter(present);
  if(!range.length){
    svg.setAttribute("aria-label","Geen complete temperatuurmetingen beschikbaar");
    $("chart-hover").textContent="Geen complete kwartiermetingen beschikbaar voor deze kamer.";
    return;
  }
  const low=Math.floor((Math.min(...range)-0.6)*2)/2;
  const high=Math.ceil((Math.max(...range)+0.6)*2)/2;
  const olow=outside.length?Math.floor((Math.min(...outside)-1)/2)*2:0;
  const ohigh=outside.length?Math.ceil((Math.max(...outside)+1)/2)*2:20;
  const y=v=>top+height-(v-low)/(high-low)*height;
  const oy=v=>top+height-(v-olow)/(ohigh-olow||1)*height;
  const x=i=>left+i/(samples.length-1)*width;
  const txt=(x0,y0,v,attrs={})=>{
    const n=svgNode("text",{x:x0,y:y0,"font-size":"12",fill:"#6a7c91",...attrs});
    n.textContent=v;svg.appendChild(n);
  };
  svg.appendChild(svgNode("rect",{x:left,y:top,width,height,fill:"#fff"}));
  for(let i=0;i<quatt.length;i++){
    if(quatt[i]?.heatingOnFraction>0.5){
      const p0=x(i)-width/(samples.length-1)/2;
      svg.appendChild(svgNode("rect",{
        x:Math.max(left,p0),y:top,
        width:Math.min(width/(samples.length-1),W-right-Math.max(left,p0)),
        height,fill:"#f4c565",opacity:".18"
      }));
    }
  }
  for(let n=0;n<=5;n++){
    const t=low+(high-low)*n/5,at=y(t);
    svg.appendChild(svgNode("line",{
      x1:left,x2:W-right,y1:at,y2:at,stroke:"#e5edf5","stroke-width":1
    }));
    txt(left-9,at+4,fmt(t,1),{"text-anchor":"end"});
    if(outside.length){
      const out=olow+(ohigh-olow)*n/5;
      txt(W-right+10,at+4,fmt(out,0),{"text-anchor":"start"});
    }
  }
  txt(left,15,"°C · Kamer",{"font-weight":"700"});
  txt(W-right+6,15,"°C · Buiten",{"font-weight":"700"});
  for(let i=0;i<samples.length;i++){
    const t=new Date(samples[i].at);
    const hour=t.toLocaleTimeString("nl-NL",{timeZone:ZONE,hour:"2-digit",minute:"2-digit"});
    if(hour.endsWith(":00")&&Number(hour.slice(0,2))%3===0){
      txt(x(i),H-bottom+23,hour,{"text-anchor":"middle","font-size":"11"});
    }
  }
  function draw(values,color,dash="",toY=y){
    let pts=[];
    const flush=()=>{
      if(pts.length>=2){
        const path=svgNode("polyline",{
          points:pts.join(" "),fill:"none",stroke:color,
          "stroke-width":2.4,"stroke-linejoin":"round",
          "stroke-linecap":"round",...(dash?{"stroke-dasharray":dash}:{})
        });
        svg.appendChild(path);
      }
      pts=[];
    };
    values.forEach((val,i)=>{
      if(!present(val)){flush();return;}
      pts.push(x(i)+","+toY(val));
    });
    flush();
  }
  draw(quatt.map(p=>p.outsideTemperatureC),"#d98939","4 4",oy);
  draw(samples.map(p=>p.observedTargetC),"#129c75","6 4");
  draw(samples.map(p=>p.temperatureC),"#2677c6");
  const marker=svgNode("line",{
    x1:left,x2:left,y1:top,y2:top+height,
    stroke:"#52687e","stroke-width":1.1,"stroke-dasharray":"3 3",opacity:0
  });
  svg.appendChild(marker);
  svg.onmousemove=event=>{
    const rect=svg.getBoundingClientRect();
    const sx=(event.clientX-rect.left)/rect.width*W;
    const i=Math.max(0,Math.min(samples.length-1,Math.round((sx-left)/width*(samples.length-1))));
    const s=samples[i],q=quatt[i];
    marker.setAttribute("x1",x(i));marker.setAttribute("x2",x(i));
    marker.setAttribute("opacity",1);
    $("chart-hover").textContent=localTime(s.at)+
      " · Kamer "+temp(s.temperatureC)+
      " · Honeywell-doel "+temp(s.observedTargetC)+
      " · Buiten "+temp(q?.outsideTemperatureC)+
      " · Quatt heating_on "+percent(q?.heatingOnFraction);
  };
  svg.onmouseleave=()=>{
    marker.setAttribute("opacity",0);
    $("chart-hover").textContent="Beweeg over de grafiek om metingen per kwartier te bekijken.";
  };
  svg.setAttribute("aria-label",
    "Temperatuurverloop van "+room.name+" met geregistreerd Honeywell-setpoint, buitentemperatuur en Quatt-signaal");
}
function renderSelectedRoom(){
  if(!temperatureData)return;
  const room=temperatureData.rooms.find(r=>r.key===selectedRoomKey);
  if(!room)return;
  renderThermalChart(room,temperatureData);
  $("series-quality").textContent="Geldige paren kamertemperatuur/doel: "+
    room.completePairedSlots+"/"+temperatureData.expectedSlots+
    " kwartieren. Lijnen worden onderbroken bij ontbrekende meetwaarden; doelen kunnen overrides bevatten.";
  renderReaction(room);
  coolingText(room.cooling?.evening,"cooling-evening","cooling-evening-detail");
  coolingText(room.cooling?.night,"cooling-night","cooling-night-detail");
}
function renderTemperatureView(report,data){
  if(data.schema!=="EMS_WEB_HEATING_DAILY_TEMPERATURE_V1"||
     data.dateLocal!==report.dateLocal||data.controlWrites!==false||
     data.mode!=="READ_ONLY"||data.controlMode!=="SHADOW"||
     data.setpointProvenance!=="OBSERVED_HONEYWELL_SETPOINT_INCLUDING_OVERRIDES_NOT_VERSIONED_WEEKLY_SCHEDULE"||
     !Array.isArray(data.rooms)||data.rooms.length!==8||
     !Array.isArray(data.quatt)||data.expectedSlots!==data.quatt.length||
     !data.rooms.every(r=>Array.isArray(r.series)&&r.series.length===data.expectedSlots)){
    throw new Error("Ongeldige historische temperatuurreeks");
  }
  temperatureData=data;
  const selector=$("room-select");
  selector.replaceChildren(...data.rooms.map(room=>{
    const opt=el("option",null,room.name);
    opt.value=room.key;
    return opt;
  }));
  if(!data.rooms.some(r=>r.key===selectedRoomKey))selectedRoomKey=data.rooms[0].key;
  selector.value=selectedRoomKey;
  renderSelectedRoom();
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
    try {
      const response=await fetch(
        "/web/analysis/heating/temperature/day/"+encodeURIComponent(day),
        {cache:"no-store"}
      );
      if(id!==requestId)return;
      if(!response.ok)throw new Error("API "+response.status);
      const history=await response.json();
      if(id!==requestId)return;
      renderTemperatureView(data,history);
    } catch (error) {
      if(id!==requestId)return;
      temperatureData=null;
      $("series-quality").textContent="Historische temperatuurreeks niet beschikbaar: "+error.message;
      $("chart-hover").textContent="Geen grafiek beschikbaar voor deze dag.";
      $("temperature-chart").replaceChildren();
      $("reaction").textContent="—";
      $("cooling-evening").textContent="—";
      $("cooling-night").textContent="—";
    }
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
$("room-select").addEventListener("change",value=>{
  selectedRoomKey=value.target.value;
  renderSelectedRoom();
});
load();
