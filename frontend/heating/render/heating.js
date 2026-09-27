const SCHEDULE_URL = "/web/heating/schedule";
const TEMPERATURE_URL = "/web/heating/temperature-history";
const SHADOW_URL = "/web/planner/heating-preheat-shadow";
const PROGRESSION_URL = "/web/planner/heating-preheat-progression-shadow";

const DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"];
const ROOM_KEYS = ["woonkamer","eetkamer","keuken","serre"];
const COLORS = ["#2f9e87","#2e86b7","#d08b33","#8d6cab"];
const HORIZON_MIN = 1440;
const HISTORY_MIN = 360;

const $ = selector => document.querySelector(selector);
const svg = $("#heating-chart");
const legend = $("#legend");
const empty = $("#empty");
const fresh = $("#freshness");

const timeFmt = new Intl.DateTimeFormat("nl-NL",{hour:"2-digit",minute:"2-digit",hour12:false});
const tipTimeFmt = new Intl.DateTimeFormat("nl-NL",{weekday:"short",hour:"2-digit",minute:"2-digit"});
const partsFmt = new Intl.DateTimeFormat("en-US",{weekday:"long",hour:"2-digit",minute:"2-digit",hour12:false,timeZone:"Europe/Amsterdam"});

const parts = d => Object.fromEntries(
  partsFmt.formatToParts(d)
    .filter(x => x.type !== "literal")
    .map(x => [x.type,x.value])
);

const dayName = d => {
  const s = String(d?.day_of_week ?? "");
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
};

const numeric = value => typeof value === "number" && Number.isFinite(value);
const temp = value => numeric(value) ? value.toFixed(1) + " °C" : "—";
const clock = value => value ? timeFmt.format(new Date(value)) : "—";
const minuteAt = (value,start) => (new Date(value).getTime() - start.getTime()) / 60000;
const clamp = (v,min,max) => Math.max(min,Math.min(max,v));
const hasPreheatWindow = (baseline,candidate) => baseline?.direction === "UP" && candidate?.opportunityOpensAt && candidate?.opportunityClosesAt;

const progressionLabels = {
  INACTIVE:"Inactief",
  WAITING_FOR_FRESH_PRIORITY:"Wacht op verse prioriteit",
  WAITING_FOR_GRANT:"Wacht op planner-grant",
  STEP_WAIT:"Stap actief · wacht op temperatuur",
  STEP_REACHED:"Stap bereikt",
  STEP_REACHED_GROUP_WAIT:"Stap bereikt · wacht op groep",
  STEP_HOLD_PRIORITY_UNKNOWN:"Stap HOLD · prioriteit onzeker",
  STEP_HOLD_NO_GRANT:"Stap HOLD · geen grant",
  BLOCKED_CV_ASSIST:"Geblokkeerd · CV actief",
  BLOCKED_CV_STATUS_UNKNOWN:"Geblokkeerd · CV-status onbekend",
  ENDED_BASELINE_HEATING:"Beëindigd · baseline warmtevraag",
  COMPLETE_TARGET_REACHED:"Gereed · Honeywell-target bereikt",
  COMPLETE_NO_NEXT_STEP:"Gereed · geen volgende stap",
};

const eligibilityLabels = {
  PREHEAT_READY_FOR_GRANT:"Kandidaat",
  BASELINE_HEATING:"Baseline warmtevraag",
  PREHEAT_BLOCKED_CV_ASSIST:"Geblokkeerd · CV actief",
  PREHEAT_BLOCKED_CV_STATUS_UNKNOWN:"Geblokkeerd · CV-status onbekend",
  NOT_ELIGIBLE:"Niet kandidaat",
};

function schedulePoints(schedule,start){
  const out = [];
  let last = null;
  for(let m=0;m<=HORIZON_MIN;m++){
    const at = new Date(start.getTime()+m*60000);
    const p = parts(at);
    const mins = Number(p.hour)*60 + Number(p.minute);
    const today = (schedule||[]).find(x => dayName(x) === p.weekday)?.switchpoints || [];
    let value = null;
    for(const sp of today){
      const [hh,mm] = String(sp.time_of_day).split(":").map(Number);
      if(hh*60+mm <= mins) value = Number(sp.heat_setpoint);
    }
    if(value === null){
      const di = DAYS.indexOf(p.weekday);
      for(let back=1;back<=7 && value===null;back++){
        const previous = (schedule||[]).find(x => dayName(x) === DAYS[(di-back+7)%7])?.switchpoints || [];
        if(previous.length) value = Number(previous.at(-1).heat_setpoint);
      }
    }
    if(value !== null && value !== last){
      out.push({m,t:value});
      last = value;
    }
  }
  if(out.length && out.at(-1).m !== HORIZON_MIN){
    out.push({m:HORIZON_MIN,t:out.at(-1).t});
  }
  return out;
}

function valueAtStep(points,m){
  let value = points[0]?.t;
  for(const point of points){
    if(point.m <= m) value = point.t;
    else break;
  }
  return value;
}

async function loadOptional(url,schema){
  try{
    const response = await fetch(url,{cache:"no-store"});
    if(!response.ok) return null;
    const payload = await response.json();
    return payload?.schema === schema ? payload : null;
  }catch{
    return null;
  }
}

function buildActualSeries(historyRoom,shadowRoom,start,now){
  const series = [];
  for(const item of historyRoom?.series || []){
    const m = minuteAt(item.slotStart,start);
    if(m < 0 || m > HORIZON_MIN || !Number.isFinite(Number(item.avg_C))) continue;
    series.push({m,t:Number(item.avg_C),quality:item.quality,at:item.slotStart});
  }

  const current = shadowRoom?.current?.temperature_C;
  const shadowAt = shadowRoom?._generatedAt;
  if(Number.isFinite(current) && shadowAt){
    const m = minuteAt(shadowAt,start);
    if(m >= 0 && m <= HORIZON_MIN && m <= minuteAt(now,start)+1){
      const last = series.at(-1);
      if(!last || Math.abs(last.m-m) > 0.5){
        series.push({m,t:current,quality:"current",at:shadowAt});
      }
    }
  }
  series.sort((a,b)=>a.m-b.m);
  return series;
}

function actualPath(series,x,y){
  let path = "";
  let previous = null;
  for(const point of series){
    const command = !previous || point.m-previous.m > 30 ? "M" : "L";
    path += `${command} ${x(point.m)} ${y(point.t)} `;
    previous = point;
  }
  return path.trim();
}

function shadowStepIntervals(room,now){
  const out = [];
  for(const item of room.progressionSource?.stepHistory || []){
    if(
      numeric(item?.target_C) &&
      item?.startedAt &&
      item?.endedAt
    ){
      out.push({
        target_C:item.target_C,
        startedAt:item.startedAt,
        endedAt:item.endedAt,
        outcome:item.outcome || "ENDED",
        reason:item.reason || null,
        active:false,
      });
    }
  }

  const progression = room.progressionSource?.progression;
  if(progression?.activeStepStartedAt && numeric(progression.activeStepTarget_C)){
    out.push({
      target_C:progression.activeStepTarget_C,
      startedAt:progression.activeStepStartedAt,
      endedAt:now.toISOString(),
      outcome:"ACTIVE",
      reason:progression.reason || null,
      active:true,
    });
  }

  return out;
}

function preheatWindows(room,start,now,maxAdvanceMinutes){
  const out = [];
  const byWindow = new Map();
  const addWindow = window => {
    const openMs = new Date(window.opensAt).getTime();
    const closeMs = new Date(window.closesAt).getTime();
    if(!Number.isFinite(openMs) || !Number.isFinite(closeMs) || closeMs < openMs) return;
    const key = `${openMs}|${closeMs}`;
    const existing = byWindow.get(key);
    if(existing){
      existing.ready = existing.ready || window.ready === true;
      existing.current = existing.current || window.current === true;
      return;
    }
    const normalized = {...window,ready:window.ready === true,current:window.current === true};
    out.push(normalized);
    byWindow.set(key,normalized);
  };

  for(const item of room.progressionSource?.opportunityHistory || []){
    if(!item?.opportunityId || !item?.opensAt || !item?.closesAt) continue;
    addWindow({
      opportunityId:item.opportunityId,
      opensAt:item.opensAt,
      closesAt:item.closesAt,
      ready:false,
      current:false,
    });
  }

  const candidate = room.shadowSource?.candidate;
  if(hasPreheatWindow(room.shadowSource?.baseline,candidate)){
    addWindow({
      opportunityId:room.progressionSource?.opportunityId || null,
      opensAt:candidate.opportunityOpensAt,
      closesAt:candidate.opportunityClosesAt,
      ready:room.shadowSource?.shadow?.state === "PREHEAT_READY_FOR_GRANT",
      current:true,
    });
  }

  if(numeric(maxAdvanceMinutes) && maxAdvanceMinutes > 0){
    for(let i=1;i<room.points.length;i++){
      const previous = room.points[i-1];
      const transition = room.points[i];
      if(!numeric(previous?.t) || !numeric(transition?.t) || transition.t <= previous.t) continue;
      const closesAt = new Date(start.getTime()+transition.m*60000);
      if(closesAt <= now) continue;
      addWindow({
        opportunityId:null,
        opensAt:new Date(closesAt.getTime()-maxAdvanceMinutes*60000).toISOString(),
        closesAt:closesAt.toISOString(),
        ready:false,
        current:false,
      });
    }
  }

  out.sort((a,b)=>new Date(a.opensAt)-new Date(b.opensAt));
  return out;
}

function renderStatus(shadow,progression,rooms){
  const house = shadow?.house;
  const cv = shadow?.cvGuard;
  $("#heating-status").innerHTML = [
    `<span><b>Baseline</b> · ${house?.baselineHeatingDemandPresent ? "warmtevraag aanwezig" : "voldaan"}</span>`,
    `<span><b>CV</b> · ${cv?.status === "OK" ? (cv.cvActive ? "actief" : "uit") : "onbekend"}</span>`,
    `<span><b>Preheat</b> · V0.3 eligibility · V0.4 progression</span>`,
  ].join("");

  $("#signal-legend").innerHTML = [
    '<span><i class="sample baseline-sample"></i>Honeywell baseline</span>',
    '<span><i class="sample actual-sample"></i>Gemeten temperatuur</span>',
    '<span><i class="sample shadow-sample"></i>EMS shadow-target</span>',
    '<span><i class="sample rail-sample"></i>Preheat-window</span>',
  ].join("");

  $("#room-status").innerHTML = rooms.map(room => {
    const s = room.shadowSource;
    const p = room.progressionSource;
    const eligibility = eligibilityLabels[s?.shadow?.state] || s?.shadow?.state || "Niet beschikbaar";
    const progressionState = progressionLabels[p?.progression?.state] || p?.progression?.state || "Niet beschikbaar";
    const grant = p?.planner?.domainGrant || "—";
    const candidate = s?.candidate;
    const open = candidate?.opportunityOpensAt;
    const close = candidate?.opportunityClosesAt;
    const windowText = hasPreheatWindow(s?.baseline,candidate) ? `${clock(open)}–${clock(close)}` : "—";
    const active = p?.progression?.activeStepTarget_C;

    return `<article class="room-status-card" data-room="${room.key}">
      <header><i style="background:${room.color}"></i><b>${room.displayName}</b></header>
      <dl>
        <div><dt>Nu</dt><dd>${temp(s?.current?.temperature_C ?? p?.currentTemperature_C)}</dd></div>
        <div><dt>Honeywell baseline</dt><dd>${temp(s?.baseline?.currentTargetTemperature_C)}</dd></div>
        <div><dt>Preheat-window</dt><dd>${windowText}</dd></div>
        <div><dt>V0.3</dt><dd>${eligibility}</dd></div>
        <div><dt>Planner grant</dt><dd>${grant}</dd></div>
        <div><dt>V0.4</dt><dd>${progressionState}</dd></div>
        <div><dt>Shadow-target</dt><dd>${temp(active)}</dd></div>
      </dl>
    </article>`;
  }).join("");
}

async function load(){
  const schedule = await loadOptional(SCHEDULE_URL,"EMS_WEB_HEATING_SCHEDULE_V1");
  if(!schedule || schedule.baselineAuthority !== "HONEYWELL" || !Array.isArray(schedule.rooms)){
    empty.hidden = false;
    fresh.textContent = "Geen schema";
    return;
  }

  const [history,shadow,progression] = await Promise.all([
    loadOptional(TEMPERATURE_URL,"EMS_WEB_HEATING_TEMPERATURE_HISTORY_V1"),
    loadOptional(SHADOW_URL,"EMS_WEB_HEATING_PREHEAT_SHADOW_V1"),
    loadOptional(PROGRESSION_URL,"EMS_WEB_HEATING_PREHEAT_PROGRESSION_V1"),
  ]);

  const now = new Date();
  const start = new Date(now.getTime()-HISTORY_MIN*60000);
  start.setSeconds(0,0);
  start.setMinutes(Math.floor(start.getMinutes()/15)*15);

  const historyMap = new Map((history?.rooms || []).map(r => [r.key,r]));
  const shadowMap = new Map((shadow?.rooms || []).map(r => [r.key,{...r,_generatedAt:shadow.generatedAt}]));
  const progressionMap = new Map((progression?.rooms || []).map(r => [r.key,r]));

  const rooms = schedule.rooms
    .filter(r => ROOM_KEYS.includes(r.key))
    .sort((a,b)=>ROOM_KEYS.indexOf(a.key)-ROOM_KEYS.indexOf(b.key))
    .map((room,index) => {
      const shadowSource = shadowMap.get(room.key) || null;
      return {
        ...room,
        color:COLORS[index],
        points:schedulePoints(room.weeklySchedule,start),
        actual:buildActualSeries(historyMap.get(room.key),shadowSource,start,now),
        shadowSource,
        progressionSource:progressionMap.get(room.key) || null,
      };
    });

  const maxAdvanceMinutes = numeric(shadow?.policy?.maxAdvanceMinutes)
    ? shadow.policy.maxAdvanceMinutes
    : null;

  renderStatus(shadow,progression,rooms);
  render(rooms,start,now,maxAdvanceMinutes);
  fresh.textContent = "Verwarming · " + timeFmt.format(new Date(
    progression?.generatedAt || shadow?.generatedAt || history?.generatedAt || schedule.generatedAt || Date.now()
  ));
}

function render(rooms,start,now,maxAdvanceMinutes){
  $("#cluster-summary").innerHTML = [
    "<span><b>Leefzone</b> · Woonkamer + Eetkamer</span>",
    "<span><b>Keuken</b> · zelfstandig</span>",
    "<span><b>Serre</b> · zelfstandig</span>",
  ].join("");

  legend.innerHTML = "";
  const off = new Set();

  rooms.forEach(room => {
    const button = document.createElement("button");
    button.innerHTML = `<i style="background:${room.color}"></i>${room.displayName}`;
    button.onclick = () => {
      off.has(room.key) ? off.delete(room.key) : off.add(room.key);
      button.classList.toggle("off");
      document.querySelector(`.room-status-card[data-room="${room.key}"]`)?.classList.toggle("off");
      draw();
    };
    legend.append(button);
  });

  function draw(){
    const visible = rooms.filter(r => !off.has(r.key));
    const ySource = visible.length ? visible : rooms;
    const temperatures = ySource.flatMap(room => [
      ...room.points.map(p => p.t),
      ...room.actual.map(p => p.t),
      room.progressionSource?.progression?.activeStepTarget_C,
      ...(room.progressionSource?.stepHistory || []).map(item => item?.target_C),
    ]).filter(numeric);

    const min = Math.floor((Math.min(...temperatures)-0.5)*2)/2;
    const max = Math.ceil((Math.max(...temperatures)+0.5)*2)/2;

    const W = 1180;
    const HH = 500;
    const L = 58;
    const R = 20;
    const T = 20;
    const PLOT_B = 390;
    const AXIS_Y = 414;
    const RAIL_TOP = 435;
    const RAIL_GAP = 14;

    const x = m => L + m/HORIZON_MIN*(W-L-R);
    const y = t => T + (max-t)/(max-min)*(PLOT_B-T);
    const ns = "http://www.w3.org/2000/svg";

    svg.setAttribute("viewBox",`0 0 ${W} ${HH}`);
    svg.innerHTML = "";

    const add = (tag,attributes,text) => {
      const element = document.createElementNS(ns,tag);
      Object.entries(attributes).forEach(([key,value]) => element.setAttribute(key,value));
      if(text != null) element.textContent = text;
      svg.append(element);
      return element;
    };

    for(let t=min;t<=max+0.01;t+=0.5){
      add("line",{x1:L,y1:y(t),x2:W-R,y2:y(t),class:"grid"});
      add("text",{x:L-8,y:y(t)+4,"text-anchor":"end",class:"axis"},t.toFixed(1)+"°");
    }

    for(let m=0;m<=HORIZON_MIN;m+=180){
      add("line",{x1:x(m),y1:T,x2:x(m),y2:PLOT_B,class:"grid"});
      add("text",{
        x:x(m),y:AXIS_Y,
        "text-anchor":m===0?"start":m===HORIZON_MIN?"end":"middle",
        class:"axis"
      },timeFmt.format(new Date(start.getTime()+m*60000)));
    }

    const hoverTargets = [];

    visible.forEach(room => {
      if(room.points.length){
        let d = `M ${x(room.points[0].m)} ${y(room.points[0].t)}`;
        for(let i=1;i<room.points.length;i++){
          d += ` H ${x(room.points[i].m)} V ${y(room.points[i].t)}`;
        }
        add("path",{d,stroke:room.color,class:"room baseline-line"});
        hoverTargets.push({kind:"baseline",room,tag:"path",attributes:{d}});
      }

      if(room.actual.length){
        const d = actualPath(room.actual,x,y);
        if(d){
          add("path",{d,stroke:room.color,class:"room actual-line"});
          hoverTargets.push({kind:"actual",room,tag:"path",attributes:{d}});
        }
        const latest = room.actual.at(-1);
        add("circle",{cx:x(latest.m),cy:y(latest.t),r:2.8,fill:room.color,class:"actual-dot"});
      }

      for(const interval of shadowStepIntervals(room,now)){
        const rawFrom = minuteAt(interval.startedAt,start);
        const rawTo = minuteAt(interval.endedAt,start);
        if(rawTo < 0 || rawFrom > HORIZON_MIN || rawTo < rawFrom) continue;
        const from = clamp(rawFrom,0,HORIZON_MIN);
        const to = clamp(rawTo,0,HORIZON_MIN);
        if(to >= from){
          const attributes = {
            x1:x(from),y1:y(interval.target_C),x2:x(to),y2:y(interval.target_C),
          };
          add("line",{
            ...attributes,stroke:room.color,class:"shadow-target"
          });
          hoverTargets.push({kind:"shadow",room,interval,tag:"line",attributes});
        }
      }
    });

    visible.forEach((room,index) => {
      const railY = RAIL_TOP + index*RAIL_GAP;
      add("text",{x:4,y:railY+8,class:"rail-label"},room.displayName);
      add("line",{x1:L,y1:railY+4,x2:W-R,y2:railY+4,class:"rail-base"});

      for(const window of preheatWindows(room,start,now,maxAdvanceMinutes)){
        const rawFrom = minuteAt(window.opensAt,start);
        const rawTo = minuteAt(window.closesAt,start);
        if(rawTo < 0 || rawFrom > HORIZON_MIN || rawTo < rawFrom) continue;
        const from = clamp(rawFrom,0,HORIZON_MIN);
        const to = clamp(rawTo,0,HORIZON_MIN);
        if(to > from){
          add("rect",{
            x:x(from),y:railY,width:Math.max(1,x(to)-x(from)),height:8,
            fill:room.color,class:window.ready?"preheat-window ready":"preheat-window"
          });
        }
      }

      for(const interval of shadowStepIntervals(room,now)){
        const rawFrom = minuteAt(interval.startedAt,start);
        const rawTo = minuteAt(interval.endedAt,start);
        if(rawTo < 0 || rawFrom > HORIZON_MIN || rawTo < rawFrom) continue;
        const from = clamp(rawFrom,0,HORIZON_MIN);
        const to = clamp(rawTo,0,HORIZON_MIN);
        if(to > from){
          add("rect",{
            x:x(from),y:railY+1,width:Math.max(1,x(to)-x(from)),height:6,
            fill:room.color,class:"preheat-active"
          });
        }
      }
    });

    const nowM = (now.getTime()-start.getTime())/60000;
    if(nowM>=0 && nowM<=HORIZON_MIN){
      add("line",{x1:x(nowM),y1:T,x2:x(nowM),y2:RAIL_TOP+(visible.length-1)*RAIL_GAP+11,class:"now"});
    }

    const tip = $("#tooltip");
    const marker = add("circle",{cx:0,cy:0,r:4,class:"hover-marker"});
    marker.style.display = "none";

    const nearestActualPoint = (series,m) => {
      let nearest = null;
      let distance = Infinity;
      for(const point of series){
        const current = Math.abs(point.m-m);
        if(current < distance){
          nearest = point;
          distance = current;
        }
      }
      return nearest;
    };

    const hideTip = () => {
      tip.hidden = true;
      marker.style.display = "none";
    };

    const showTarget = (event,target) => {
      const rect = svg.getBoundingClientRect();
      const px = clamp((event.clientX-rect.left)/rect.width*W,L,W-R);
      const py = clamp((event.clientY-rect.top)/rect.height*HH,T,PLOT_B);
      const m = (px-L)/(W-L-R)*HORIZON_MIN;
      const hoverTime = new Date(start.getTime()+m*60000);

      let label = "";
      let value = null;
      let meta = "";

      if(target.kind === "baseline"){
        label = "Honeywell baseline";
        value = valueAtStep(target.room.points,m);
        meta = tipTimeFmt.format(hoverTime);
      }else if(target.kind === "actual"){
        const point = nearestActualPoint(target.room.actual,m);
        if(!point) return hideTip();
        label = "Gemeten temperatuur";
        value = point.t;
        const valueTime = new Date(point.at);
        meta = `${tipTimeFmt.format(valueTime)} · ${point.quality === "complete" ? "compleet" : "partieel"}`;
      }else if(target.kind === "shadow"){
        label = "EMS shadow-target";
        value = target.interval?.target_C;
        const outcome = target.interval?.active
          ? (progressionLabels[target.room.progressionSource?.progression?.state] || target.room.progressionSource?.progression?.state)
          : target.interval?.outcome;
        meta = [
          tipTimeFmt.format(hoverTime),
          target.interval?.active ? "actief" : "historisch",
          outcome,
        ].filter(Boolean).join(" · ");
      }

      if(!numeric(value)) return hideTip();

      tip.innerHTML = `<div class="tip-line">
        <strong><i style="background:${target.room.color}"></i>${target.room.displayName}</strong>
        <span class="tip-signal">${label}</span>
        <b class="tip-value">${temp(value)}</b>
        <span class="tip-meta">${meta}</span>
      </div>`;
      tip.hidden = false;

      marker.setAttribute("cx",px);
      marker.setAttribute("cy",py);
      marker.setAttribute("stroke",target.room.color);
      marker.style.display = "";

      const left = (px/W)*rect.width;
      const top = (py/HH)*rect.height;
      tip.style.left = Math.min(Math.max(8,left+12),Math.max(8,rect.width-tip.offsetWidth-8))+"px";
      tip.style.top = Math.min(Math.max(8,top+12),Math.max(8,rect.height-tip.offsetHeight-8))+"px";
    };

    hoverTargets.forEach(target => {
      const hit = add(target.tag,{
        ...target.attributes,
        class:"line-hit",
      });
      hit.addEventListener("pointermove",event => showTarget(event,target));
      hit.addEventListener("pointerdown",event => showTarget(event,target));
      hit.addEventListener("pointerleave",hideTip);
    });
  }

  draw();
}

load();
