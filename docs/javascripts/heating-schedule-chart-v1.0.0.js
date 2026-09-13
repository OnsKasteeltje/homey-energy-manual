(() => {
  const plannerList = document.getElementById('planner-list');
  if (!plannerList || document.getElementById('heating-schedule-panel')) return;

  const NS = 'http://www.w3.org/2000/svg';
  const dataUrl = new URL('data/heating-schedule.json', document.baseURI).toString();
  const colors = ['#2f83b8','#2e9b67','#8f4ac7','#d78b1f','#b84b6a','#4f8b45','#7b6cc2','#b55f2a'];
  const panel = document.createElement('section');
  panel.id = 'heating-schedule-panel';
  panel.className = 'hs-panel';
  panel.innerHTML = `
    <div class="hs-head">
      <div>
        <h2>Warmteplanning per ruimte</h2>
        <p class="hs-note">Honeywell setpoints per ruimte. EMS-opportunistisch voorverwarmen wordt als afwijkend trapsegment getoond.</p>
      </div>
      <div class="hs-meta" aria-live="polite"></div>
    </div>
    <div class="hs-legend" role="group" aria-label="Ruimtes"></div>
    <div class="hs-chart-wrap">
      <div class="hs-status">Warmteschema laden…</div>
      <svg class="hs-chart" viewBox="0 0 1200 380" role="img" aria-label="Geplande temperatuur per ruimte" hidden></svg>
      <div class="hs-tooltip" hidden></div>
    </div>
    <div class="hs-foot"><span class="hs-baseline-key"></span> Honeywell schema <span class="hs-preheat-key"></span> EMS PV-preheat</div>`;
  plannerList.insertAdjacentElement('afterend', panel);

  const svg = panel.querySelector('.hs-chart');
  const status = panel.querySelector('.hs-status');
  const legend = panel.querySelector('.hs-legend');
  const tooltip = panel.querySelector('.hs-tooltip');
  const meta = panel.querySelector('.hs-meta');
  const hiddenRooms = new Set();
  let payload = null;

  const finite = v => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));
  const minute = s => {
    const m = String(s || '').match(/^(\d{1,2}):(\d{2})$/);
    if (!m) return null;
    const n = Number(m[1]) * 60 + Number(m[2]);
    return n >= 0 && n <= 1440 ? n : null;
  };
  const hhmm = n => `${String(Math.floor(n / 60) % 24).padStart(2,'0')}:${String(Math.round(n % 60)).padStart(2,'0')}`;
  const temp = v => `${Number(v).toFixed(1).replace('.', ',')} °C`;
  const make = (name, attrs={}) => {
    const e = document.createElementNS(NS, name);
    Object.entries(attrs).forEach(([k,v]) => e.setAttribute(k, String(v)));
    return e;
  };
  const normalize = arr => (Array.isArray(arr) ? arr : [])
    .map(x => ({...x, m: minute(x.at), temp: Number(x.temp)}))
    .filter(x => x.m !== null && finite(x.temp))
    .sort((a,b) => a.m - b.m);
  const valueAt = (arr, m) => {
    if (!arr.length) return null;
    let v = arr[0].temp;
    for (const p of arr) {
      if (p.m > m) break;
      v = p.temp;
    }
    return v;
  };
  const reasonAt = (arr, m) => {
    let p = null;
    for (const x of arr) {
      if (x.m > m) break;
      p = x;
    }
    return p;
  };

  function stepPath(arr, x, y) {
    if (!arr.length) return '';
    const pts = arr.slice();
    if (pts[0].m > 0) pts.unshift({...pts[0], m:0});
    let d = `M ${x(pts[0].m)} ${y(pts[0].temp)}`;
    for (let i=1;i<pts.length;i++) {
      d += ` H ${x(pts[i].m)} V ${y(pts[i].temp)}`;
    }
    d += ` H ${x(1440)}`;
    return d;
  }

  function deviationPath(base, effective, x, y) {
    if (!base.length || !effective.length) return '';
    const bounds = [...new Set([0,1440,...base.map(p=>p.m),...effective.map(p=>p.m)])].sort((a,b)=>a-b);
    let d = '';
    let previousEnd = null;
    let previousEff = null;
    for (let i=0;i<bounds.length-1;i++) {
      const a=bounds[i], b=bounds[i+1];
      if (b <= a) continue;
      const bv=valueAt(base,a), ev=valueAt(effective,a);
      if (!finite(bv) || !finite(ev) || Math.abs(ev-bv)<0.001) {
        previousEnd=null; previousEff=null; continue;
      }
      if (previousEnd===a && finite(previousEff)) d += ` M ${x(a)} ${y(previousEff)} V ${y(ev)} H ${x(b)}`;
      else d += ` M ${x(a)} ${y(ev)} H ${x(b)}`;
      previousEnd=b; previousEff=ev;
    }
    return d;
  }

  function localToday() {
    const parts = new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Amsterdam',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
    const map = Object.fromEntries(parts.map(p=>[p.type,p.value]));
    return `${map.year}-${map.month}-${map.day}`;
  }
  function localMinutesNow() {
    const parts = new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Amsterdam',hour:'2-digit',minute:'2-digit',hour12:false}).formatToParts(new Date());
    const map = Object.fromEntries(parts.map(p=>[p.type,p.value]));
    return Number(map.hour)*60+Number(map.minute);
  }

  function render() {
    const rooms = (payload?.rooms || []).map((r,i) => ({...r, color:r.color || colors[i % colors.length], baseline:normalize(r.baseline), effective:normalize(r.effective)}));
    const drawable = rooms.filter(r => r.baseline.length);
    legend.innerHTML = '';
    rooms.forEach(room => {
      const b=document.createElement('button');
      b.type='button'; b.className='hs-room-key'; b.dataset.room=room.id;
      b.innerHTML=`<i style="--room-color:${room.color}"></i><span>${room.name}</span>`;
      if (hiddenRooms.has(room.id)) b.classList.add('is-off');
      b.addEventListener('click',()=>{hiddenRooms.has(room.id)?hiddenRooms.delete(room.id):hiddenRooms.add(room.id);render();});
      legend.append(b);
    });

    if (!drawable.length) {
      svg.hidden=true;
      status.hidden=false;
      status.textContent='Visualisatie gereed; nog geen Honeywell-schemadata ontvangen. Zodra de Pi baseline-overgangen publiceert, verschijnen de kamerlijnen hier automatisch.';
      meta.textContent=payload?.status ? `bron: ${payload.status}` : '';
      return;
    }

    status.hidden=true; svg.hidden=false; svg.innerHTML='';
    const W=1200,H=380, L=66,R=20,T=18,B=48;
    const allTemps=drawable.flatMap(r=>r.baseline.concat(r.effective)).map(p=>p.temp).filter(finite);
    let minT=Math.floor((Math.min(...allTemps)-0.5)*2)/2;
    let maxT=Math.ceil((Math.max(...allTemps)+0.5)*2)/2;
    if (maxT-minT<2) { minT-=1; maxT+=1; }
    const x=m=>L+(m/1440)*(W-L-R);
    const y=t=>T+(maxT-t)/(maxT-minT)*(H-T-B);

    for (let t=Math.ceil(minT); t<=Math.floor(maxT); t++) {
      const gy=y(t), line=make('line',{x1:L,x2:W-R,y1:gy,y2:gy,class:'hs-grid'}); svg.append(line);
      const tx=make('text',{x:L-10,y:gy+4,'text-anchor':'end',class:'hs-axis-label'}); tx.textContent=`${t}°`; svg.append(tx);
    }
    for (let m=0;m<=1440;m+=180) {
      const gx=x(m), line=make('line',{x1:gx,x2:gx,y1:T,y2:H-B,class:'hs-grid hs-vgrid'}); svg.append(line);
      const tx=make('text',{x:gx,y:H-20,'text-anchor':m===0?'start':m===1440?'end':'middle',class:'hs-axis-label'}); tx.textContent=m===1440?'24:00':hhmm(m); svg.append(tx);
    }
    const yTitle=make('text',{x:15,y:(T+H-B)/2,transform:`rotate(-90 15 ${(T+H-B)/2})`,'text-anchor':'middle',class:'hs-axis-title'}); yTitle.textContent='Schema temperatuur (°C)'; svg.append(yTitle);

    drawable.forEach(room=>{
      if (hiddenRooms.has(room.id)) return;
      const g=make('g',{'data-room':room.id});
      const p=make('path',{d:stepPath(room.baseline,x,y),class:'hs-room-line',stroke:room.color}); g.append(p);
      const dd=deviationPath(room.baseline,room.effective,x,y);
      if (dd) g.append(make('path',{d:dd,class:'hs-preheat-line','data-room':room.id}));
      svg.append(g);
    });

    if (payload?.date && payload.date===localToday()) {
      const nm=localMinutesNow(), nx=x(nm);
      svg.append(make('line',{x1:nx,x2:nx,y1:T,y2:H-B,class:'hs-now'}));
      const ntext=make('text',{x:nx+4,y:T+11,class:'hs-now-label'}); ntext.textContent='NU'; svg.append(ntext);
    }

    const hit=make('rect',{x:L,y:T,width:W-L-R,height:H-T-B,class:'hs-hit'}); svg.append(hit);
    const hover=make('line',{x1:L,x2:L,y1:T,y2:H-B,class:'hs-hover',visibility:'hidden'}); svg.append(hover);
    hit.addEventListener('mousemove',e=>{
      const rect=svg.getBoundingClientRect();
      const sx=(e.clientX-rect.left)/rect.width*W, sy=(e.clientY-rect.top)/rect.height*H;
      const m=Math.max(0,Math.min(1440,(sx-L)/(W-L-R)*1440));
      const visible=drawable.filter(r=>!hiddenRooms.has(r.id));
      let best=null;
      visible.forEach(r=>{
        const bv=valueAt(r.baseline,m), ev=valueAt(r.effective,m), vals=[{kind:'Honeywell',v:bv}];
        if (finite(ev)&&finite(bv)&&Math.abs(ev-bv)>0.001) vals.push({kind:'EMS',v:ev});
        vals.forEach(c=>{if(!finite(c.v))return;const d=Math.abs(y(c.v)-sy);if(!best||d<best.d)best={r,c,d,bv,ev};});
      });
      if (!best) return;
      const mm=Math.round(m), px=x(m);
      hover.setAttribute('x1',px);hover.setAttribute('x2',px);hover.setAttribute('visibility','visible');
      const reason=reasonAt(best.r.effective,m);
      tooltip.innerHTML=`<strong>${best.r.name} · ${hhmm(mm)}</strong><div><span>Honeywell</span><b>${temp(best.bv)}</b></div>${finite(best.ev)&&Math.abs(best.ev-best.bv)>0.001?`<div><span>EMS doel</span><b>${temp(best.ev)}</b></div><div class="hs-tip-reason">${reason?.reason==='PV_OPPORTUNITY'?'PV opportunity · ':''}opportunistisch voorverwarmen</div>`:''}`;
      tooltip.hidden=false;
      const wrap=panel.querySelector('.hs-chart-wrap').getBoundingClientRect();
      let left=e.clientX-wrap.left+14, top=e.clientY-wrap.top+14;
      if(left+tooltip.offsetWidth>wrap.width-8) left-=tooltip.offsetWidth+28;
      tooltip.style.left=`${Math.max(8,left)}px`; tooltip.style.top=`${Math.max(8,top)}px`;
    });
    hit.addEventListener('mouseleave',()=>{tooltip.hidden=true;hover.setAttribute('visibility','hidden');});

    const generated=payload?.generatedAt ? new Date(payload.generatedAt).toLocaleString('nl-NL',{timeZone:'Europe/Amsterdam',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}) : null;
    meta.textContent=[payload?.date, generated?`gegenereerd ${generated}`:null].filter(Boolean).join(' · ');
  }

  fetch(`${dataUrl}?ts=${Date.now()}`,{cache:'no-store'})
    .then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();})
    .then(d=>{payload=d;render();})
    .catch(err=>{status.textContent=`Warmteschema laden mislukt: ${err.message}`;status.classList.add('hs-error');});
})();
