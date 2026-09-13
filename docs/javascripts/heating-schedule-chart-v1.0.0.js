(() => {
  const DATA_URL = 'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/honeywell-schedule.json';
  const DAY_NAMES = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
  const COLORS = ['#2f9e87','#2e86b7','#8d6cab','#d08b33','#4778bd','#b75d74','#6d9b45','#8a6f4d'];

  const planner = document.getElementById('planner-list');
  if (!planner) return;

  const root = document.createElement('section');
  root.className = 'hs-section';
  root.innerHTML = `
    <h2>Warmteplanning per ruimte</h2>
    <p class="hs-note">Honeywell is de baseline. De lijnen tonen het geplande setpoint per ruimte; wijzigingen zijn echte stapmomenten, geen interpolatie.</p>
    <div class="hs-status">Honeywell-schema laden…</div>
    <div class="hs-chart-wrap" hidden>
      <div class="hs-legend"></div>
      <div class="hs-meta"></div>
      <div class="hs-canvas-wrap">
        <svg class="hs-chart" role="img" aria-label="Honeywell warmteplanning per ruimte"></svg>
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
  const hhmm = m => `${String(Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`;
  const temp = v => `${Number(v).toFixed(1)}°`;
  const todayName = () => new Intl.DateTimeFormat('en-US',{weekday:'long',timeZone:'Europe/Amsterdam'}).format(new Date());
  const minuteNow = () => {
    const p = Object.fromEntries(new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Europe/Amsterdam'}).formatToParts(new Date()).filter(x=>x.type!=='literal').map(x=>[x.type,x.value]));
    return Number(p.hour) * 60 + Number(p.minute);
  };

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

  function pointsFor(schedule, dayName) {
    if (!Array.isArray(schedule) || !schedule.length) return [];
    const idx = DAY_NAMES.indexOf(dayName);
    const today = schedule.find(d => normaliseDay(d) === dayName);
    const prevName = DAY_NAMES[(idx + 6) % 7];
    const prev = schedule.find(d => normaliseDay(d) === prevName);
    const prevPts = switchpoints(prev).map(sp => ({m:spTime(sp),t:spTemp(sp)})).filter(p=>p.m!==null&&p.t!==null).sort((a,b)=>a.m-b.m);
    const todayPts = switchpoints(today).map(sp => ({m:spTime(sp),t:spTemp(sp)})).filter(p=>p.m!==null&&p.t!==null).sort((a,b)=>a.m-b.m);
    const initial = prevPts.length ? prevPts.at(-1).t : (todayPts.length ? todayPts[0].t : null);
    if (initial === null) return [];
    const out = [{m:0,t:initial}];
    for (const p of todayPts) {
      if (p.m === 0) out[0] = p;
      else out.push(p);
    }
    out.push({m:1440,t:out.at(-1).t});
    return out;
  }

  function loadModel(payload) {
    if (payload?.schema !== 'EMS_PUBLIC_HEATING_SCHEDULE_V0.1') throw new Error(`onverwacht schema ${payload?.schema ?? '—'}`);
    const day = todayName();
    const rooms = (payload.rooms || []).map((r,i) => ({
      key:r.key,
      name:r.displayName || r.sourceName || r.key,
      color:COLORS[i % COLORS.length],
      baseline:pointsFor(r.weeklySchedule, day),
      // Phase 2: when the EMS publishes an effective schedule, every small
      // preheat step is preserved as its own setpoint transition.
      effective:pointsFor(r.effectiveSchedule, day)
    })).filter(r=>r.baseline.length);
    if (!rooms.length) throw new Error(`geen geldig Honeywell-schema voor ${day}`);
    return {payload, day, rooms};
  }

  function valueAt(points, minute) {
    let v = points[0]?.t;
    for (const p of points) { if (p.m > minute) break; v = p.t; }
    return v;
  }

  function stairPath(points, x, y) {
    if (!points.length) return '';
    let d = `M ${x(points[0].m)} ${y(points[0].t)}`;
    for (let i=1;i<points.length;i++) {
      d += ` H ${x(points[i].m)} V ${y(points[i].t)}`;
    }
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
    const x=m=>L+(m/1440)*(W-L-R);
    const y=t=>T+(maxT-t)/(maxT-minT)*(H-T-B);
    svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
    svg.innerHTML='';
    const ns='http://www.w3.org/2000/svg';
    const add=(tag,attrs,text)=>{const e=document.createElementNS(ns,tag);Object.entries(attrs||{}).forEach(([k,v])=>e.setAttribute(k,v));if(text!==undefined)e.textContent=text;svg.append(e);return e;};

    for(let t=minT;t<=maxT+0.001;t+=0.5){
      add('line',{x1:L,y1:y(t),x2:W-R,y2:y(t),class:'hs-grid'});
      add('text',{x:L-9,y:y(t)+4,'text-anchor':'end',class:'hs-axis-label'},temp(t));
    }
    for(let h=0;h<=24;h+=3){
      add('line',{x1:x(h*60),y1:T,x2:x(h*60),y2:H-B,class:'hs-grid hs-grid-v'});
      add('text',{x:x(h*60),y:H-16,'text-anchor':h===0?'start':h===24?'end':'middle',class:'hs-axis-label'},`${String(h).padStart(2,'0')}:00`);
    }

    visible.forEach(r=>{
      add('path',{d:stairPath(r.baseline,x,y),fill:'none',stroke:r.color,'stroke-width':2.2,class:'hs-room-line','data-room':r.key});
      if(r.effective.length){
        add('path',{d:stairPath(r.effective,x,y),fill:'none',stroke:r.color,'stroke-width':4,'stroke-dasharray':'5 3',class:'hs-effective-line','data-room':r.key});
      }
    });

    const now=minuteNow();
    add('line',{x1:x(now),y1:T,x2:x(now),y2:H-B,class:'hs-now'});
    add('text',{x:x(now)+4,y:T+12,class:'hs-now-label'},'NU');

    const hit=add('rect',{x:L,y:T,width:W-L-R,height:H-T-B,fill:'transparent',class:'hs-hit'});
    hit.addEventListener('mousemove',e=>{
      const rect=svg.getBoundingClientRect();
      const sx=(e.clientX-rect.left)*(W/rect.width);
      const minute=Math.max(0,Math.min(1439,Math.round((sx-L)/(W-L-R)*1440)));
      const rows=visible.map(r=>`<div><span><i style="background:${r.color}"></i>${esc(r.name)}</span><b>${temp(valueAt(r.baseline,minute))}</b></div>`).join('');
      tooltip.innerHTML=`<strong>${hhmm(minute)}</strong>${rows}`;
      tooltip.hidden=false;
      const host=root.querySelector('.hs-canvas-wrap').getBoundingClientRect();
      tooltip.style.left=`${Math.min(e.clientX-host.left+12,host.width-230)}px`;
      tooltip.style.top=`${Math.max(8,e.clientY-host.top-20)}px`;
    });
    hit.addEventListener('mouseleave',()=>tooltip.hidden=true);
  }

  fetch(`${DATA_URL}?ts=${Date.now()}`,{cache:'no-store'})
    .then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();})
    .then(p=>{
      model=loadModel(p);
      meta.textContent=`Honeywell baseline · ${model.day} · gegenereerd ${new Date(p.generatedAt).toLocaleString('nl-NL',{timeZone:'Europe/Amsterdam'})}`;
      status.remove();wrap.hidden=false;renderLegend();renderChart();
    })
    .catch(err=>{
      status.className='hs-status hs-error';
      status.textContent=`Honeywell warmteplanning nog niet beschikbaar: ${err.message}`;
    });
})();
