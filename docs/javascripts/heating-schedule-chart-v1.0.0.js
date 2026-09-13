(() => {
  const DATA_URL = 'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/honeywell-schedule.json';
  const PLANNER_URL = 'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-planner-shadow-dynamic.json';
  const DAY_NAMES = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
  const COLORS = ['#2f9e87','#2e86b7','#8d6cab','#d08b33','#4778bd','#b75d74','#6d9b45','#8a6f4d'];
  const HORIZON_MINUTES = 24 * 60;

  const planner = document.getElementById('planner-list');
  if (!planner) return;

  const root = document.createElement('section');
  root.className = 'hs-section';
  root.innerHTML = `
    <h2>Warmteplanning per ruimte</h2>
    <p class="hs-note">Rolling 24 uur, gelijk aan de Pi-planner. Honeywell is de baseline; straks wordt de EMS-planning met opportunistische voorverwarming hier overheen gelegd.</p>
    <div class="hs-status">Honeywell-schema laden…</div>
    <div class="hs-chart-wrap" hidden>
      <div class="hs-legend"></div>
      <div class="hs-meta"></div>
      <div class="hs-canvas-wrap">
        <svg class="hs-chart" role="img" aria-label="Rolling 24-uurs warmteplanning per ruimte"></svg>
        <div class="hs-tooltip" hidden></div>
      </div>
    </div>`;
  planner.append(root);

  const status = root.querySelector('.hs-status');
  const wrap = root.querySelector('.hs-chart-wrap');
  const legend = root.querySelector('.hs-legend');
  const meta = root.querySelector('.hs-meta');
  const svg = root.querySelector('.hs-chart');
  const tooltip = root.querySelector('.hs-tooltip');
  const disabled = new Set();
  let model = null;

  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const temp = v => `${Number(v).toFixed(1)}°`;
  const fmtTime = d => new Intl.DateTimeFormat('nl-NL',{hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Europe/Amsterdam'}).format(d);
  const fmtDateTime = d => new Intl.DateTimeFormat('nl-NL',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Europe/Amsterdam'}).format(d);
  const localParts = d => Object.fromEntries(new Intl.DateTimeFormat('en-US',{
    weekday:'long',hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Europe/Amsterdam'
  }).formatToParts(d).filter(x=>x.type!=='literal').map(x=>[x.type,x.value]));

  function normaliseDay(day) {
    const name = String(day?.day_of_week ?? day?.dayOfWeek ?? day?.DayOfWeek ?? '');
    const idx = Number(name);
    if (Number.isInteger(idx) && idx >= 0 && idx < 7) return DAY_NAMES[idx];
    return name.charAt(0).toUpperCase() + name.slice(1).toLowerCase();
  }

  function switchpoints(day) {
    return day?.switchpoints ?? day?.Switchpoints ?? [];
  }

  function spTime(sp) {
    const raw = sp?.time_of_day ?? sp?.timeOfDay ?? sp?.TimeOfDay;
    if (!raw) return null;
    const [h,m] = String(raw).split(':').map(Number);
    return Number.isFinite(h) && Number.isFinite(m) ? h*60+m : null;
  }

  function spTemp(sp) {
    const v = sp?.heat_setpoint ?? sp?.heatSetpoint;
    return Number.isFinite(Number(v)) ? Number(v) : null;
  }

  function dayPoints(schedule, dayName) {
    if (!Array.isArray(schedule) || !schedule.length) return [];
    const day = schedule.find(d => normaliseDay(d) === dayName);
    return switchpoints(day)
      .map(sp => ({m:spTime(sp),t:spTemp(sp)}))
      .filter(p=>p.m!==null&&p.t!==null)
      .sort((a,b)=>a.m-b.m);
  }

  function weeklyValueAt(schedule, instant) {
    if (!Array.isArray(schedule) || !schedule.length) return null;
    const p = localParts(instant);
    const dayName = p.weekday;
    const minute = Number(p.hour) * 60 + Number(p.minute);
    const today = dayPoints(schedule, dayName);
    let value = null;
    for (const sp of today) {
      if (sp.m > minute) break;
      value = sp.t;
    }
    if (value !== null) return value;

    const idx = DAY_NAMES.indexOf(dayName);
    for (let back=1; back<=7; back++) {
      const prevName = DAY_NAMES[(idx - back + 7) % 7];
      const prev = dayPoints(schedule, prevName);
      if (prev.length) return prev.at(-1).t;
    }
    return today.length ? today[0].t : null;
  }

  function rollingPoints(schedule, start) {
    const out = [];
    let last = null;
    for (let m=0; m<=HORIZON_MINUTES; m++) {
      const instant = new Date(start.getTime() + m * 60000);
      const value = weeklyValueAt(schedule, instant);
      if (value === null) continue;
      if (!out.length || value !== last) {
        out.push({m,t:value});
        last = value;
      }
    }
    if (!out.length) return [];
    if (out[0].m !== 0) out.unshift({m:0,t:out[0].t});
    if (out.at(-1).m !== HORIZON_MINUTES) out.push({m:HORIZON_MINUTES,t:out.at(-1).t});
    return out;
  }

  function plannerStart(payload) {
    const slots = payload?.slots ?? payload?.plan?.actions ?? [];
    const raw = slots[0]?.slot_start_utc ?? slots[0]?.slotStartUtc ?? slots[0]?.start;
    const d = raw ? new Date(raw) : null;
    return d && Number.isFinite(d.getTime()) ? d : null;
  }

  function fallbackStart() {
    const d = new Date();
    d.setSeconds(0,0);
    d.setMinutes(Math.floor(d.getMinutes()/15)*15);
    return d;
  }

  function loadModel(payload, plannerPayload) {
    if (payload?.schema !== 'EMS_PUBLIC_HEATING_SCHEDULE_V0.1') throw new Error(`onverwacht schema ${payload?.schema ?? '—'}`);
    const start = plannerStart(plannerPayload) || fallbackStart();
    const end = new Date(start.getTime() + HORIZON_MINUTES * 60000);
    const rooms = (payload.rooms || []).map((r,i) => ({
      key:r.key,
      name:r.displayName || r.sourceName || r.key,
      color:COLORS[i % COLORS.length],
      baseline:rollingPoints(r.weeklySchedule, start),
      // Phase 2: when the EMS publishes an effective schedule, every small
      // preheat step is preserved as its own setpoint transition.
      effective:rollingPoints(r.effectiveSchedule, start)
    })).filter(r=>r.baseline.length);
    if (!rooms.length) throw new Error('geen geldig Honeywell-schema in rolling horizon');
    return {payload, start, end, rooms, alignedToPlanner:!!plannerStart(plannerPayload)};
  }

  function valueAt(points, minute) {
    let v = points[0]?.t;
    for (const p of points) { if (p.m > minute) break; v = p.t; }
    return v;
  }

  function stairPath(points, x, y) {
    if (!points.length) return '';
    let d = `M ${x(points[0].m)} ${y(points[0].t)}`;
    for (let i=1;i<points.length;i++) d += ` H ${x(points[i].m)} V ${y(points[i].t)}`;
    return d;
  }

  function renderLegend() {
    legend.innerHTML = '';
    model.rooms.forEach(r => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = `hs-legend-item${disabled.has(r.key)?' is-off':''}`;
      b.innerHTML = `<i style="background:${r.color}"></i>${esc(r.name)}`;
      b.onclick = () => { disabled.has(r.key) ? disabled.delete(r.key) : disabled.add(r.key); renderLegend(); renderChart(); };
      legend.append(b);
    });
  }

  function renderChart() {
    const visible = model.rooms.filter(r=>!disabled.has(r.key));
    const allTemps = visible.flatMap(r=>r.baseline.map(p=>p.t).concat(r.effective.map(p=>p.t)));
    const minT = Math.floor((Math.min(...allTemps)-0.5)*2)/2;
    const maxT = Math.ceil((Math.max(...allTemps)+0.5)*2)/2;
    const W=1120,H=390,L=58,R=18,T=18,B=42;
    const x=m=>L+(m/HORIZON_MINUTES)*(W-L-R);
    const y=t=>T+(maxT-t)/(maxT-minT)*(H-T-B);
    svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
    svg.innerHTML='';
    const ns='http://www.w3.org/2000/svg';
    const add=(tag,attrs,text)=>{const e=document.createElementNS(ns,tag);Object.entries(attrs||{}).forEach(([k,v])=>e.setAttribute(k,v));if(text!==undefined)e.textContent=text;svg.append(e);return e;};

    for(let t=minT;t<=maxT+0.001;t+=0.5){
      add('line',{x1:L,y1:y(t),x2:W-R,y2:y(t),class:'hs-grid'});
      add('text',{x:L-9,y:y(t)+4,'text-anchor':'end',class:'hs-axis-label'},temp(t));
    }
    for(let m=0;m<=HORIZON_MINUTES;m+=180){
      const instant = new Date(model.start.getTime() + m * 60000);
      add('line',{x1:x(m),y1:T,x2:x(m),y2:H-B,class:'hs-grid hs-grid-v'});
      add('text',{x:x(m),y:H-16,'text-anchor':m===0?'start':m===HORIZON_MINUTES?'end':'middle',class:'hs-axis-label'},fmtTime(instant));
    }

    visible.forEach(r=>{
      add('path',{d:stairPath(r.baseline,x,y),fill:'none',stroke:r.color,'stroke-width':2.2,class:'hs-room-line','data-room':r.key});
      if(r.effective.length){
        add('path',{d:stairPath(r.effective,x,y),fill:'none',stroke:r.color,'stroke-width':4,'stroke-dasharray':'5 3',class:'hs-effective-line','data-room':r.key});
      }
    });

    const nowMinute = (Date.now() - model.start.getTime()) / 60000;
    if (nowMinute >= 0 && nowMinute <= HORIZON_MINUTES) {
      add('line',{x1:x(nowMinute),y1:T,x2:x(nowMinute),y2:H-B,class:'hs-now'});
      add('text',{x:x(nowMinute)+4,y:T+12,class:'hs-now-label'},'NU');
    }

    const resetHighlight=()=>{
      svg.querySelectorAll('.hs-room-line,.hs-effective-line').forEach(p=>{
        p.style.opacity='';
        p.style.filter='';
        p.setAttribute('stroke-width',p.classList.contains('hs-effective-line')?'4':'2.2');
      });
    };
    const highlightRoom=key=>{
      svg.querySelectorAll('.hs-room-line,.hs-effective-line').forEach(p=>{
        const selected=p.dataset.room===key;
        p.style.opacity=selected?'1':'0.22';
        p.style.filter=selected?'drop-shadow(0 0 1.5px currentColor)':'';
        p.setAttribute('stroke-width',selected?(p.classList.contains('hs-effective-line')?'5':'3.6'):(p.classList.contains('hs-effective-line')?'4':'2.2'));
      });
    };

    const hit=add('rect',{x:L,y:T,width:W-L-R,height:H-T-B,fill:'transparent',class:'hs-hit'});
    hit.addEventListener('mousemove',e=>{
      const rect=svg.getBoundingClientRect();
      const sx=(e.clientX-rect.left)*(W/rect.width);
      const sy=(e.clientY-rect.top)*(H/rect.height);
      const minute=Math.max(0,Math.min(HORIZON_MINUTES-1,Math.round((sx-L)/(W-L-R)*HORIZON_MINUTES)));
      const candidates=visible.map(r=>{
        const baselineTemp=valueAt(r.baseline,minute);
        const effectiveTemp=r.effective.length?valueAt(r.effective,minute):null;
        const baselineDistance=Math.abs(sy-y(baselineTemp));
        const effectiveDistance=effectiveTemp===null?Infinity:Math.abs(sy-y(effectiveTemp));
        const useEffective=effectiveDistance<baselineDistance;
        return {room:r,value:useEffective?effectiveTemp:baselineTemp,kind:useEffective?'EMS effectief':'Honeywell baseline',distance:Math.min(baselineDistance,effectiveDistance)};
      }).sort((a,b)=>a.distance-b.distance);
      const nearest=candidates[0];
      if(!nearest)return;
      highlightRoom(nearest.room.key);
      const instant = new Date(model.start.getTime() + minute * 60000);
      tooltip.innerHTML=`<strong>${fmtDateTime(instant)}</strong><div><span><i style="background:${nearest.room.color}"></i>${esc(nearest.room.name)}</span><b>${temp(nearest.value)}</b></div>${nearest.kind==='EMS effectief'?`<small>${esc(nearest.kind)}</small>`:''}`;
      tooltip.hidden=false;
      const host=root.querySelector('.hs-canvas-wrap').getBoundingClientRect();
      tooltip.style.left=`${Math.min(e.clientX-host.left+12,host.width-230)}px`;
      tooltip.style.top=`${Math.max(8,e.clientY-host.top-20)}px`;
    });
    hit.addEventListener('mouseleave',()=>{tooltip.hidden=true;resetHighlight();});
  }

  Promise.all([
    fetch(`${DATA_URL}?ts=${Date.now()}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`Honeywell HTTP ${r.status}`);return r.json();}),
    fetch(`${PLANNER_URL}?ts=${Date.now()}`,{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null)
  ])
    .then(([p,plannerPayload])=>{
      model=loadModel(p,plannerPayload);
      meta.textContent=`Honeywell baseline · rolling ${fmtDateTime(model.start)} → ${fmtDateTime(model.end)}${model.alignedToPlanner?' · gelijk aan Pi-planner':''} · gegenereerd ${new Date(p.generatedAt).toLocaleString('nl-NL',{timeZone:'Europe/Amsterdam'})}`;
      status.remove();wrap.hidden=false;renderLegend();renderChart();
    })
    .catch(err=>{
      status.className='hs-status hs-error';
      status.textContent=`Honeywell warmteplanning nog niet beschikbaar: ${err.message}`;
    });
})();
