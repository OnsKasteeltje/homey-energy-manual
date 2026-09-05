# Planner

<div id="planner-minimal" class="planner-minimal">
  <div class="pm-status" id="pm-status">Plannerdata laden…</div>
  <div class="pm-content" id="pm-content" hidden>
    <section class="pm-section">
      <h2>24-uurs forecast</h2>
      <p class="pm-note">Base load, PV en net vóór flex. Positief net = import; negatief net = export.</p>
      <div class="pm-timeline" id="pm-forecast-wrap">
        <svg id="pm-forecast" class="pm-forecast" viewBox="0 0 960 260" preserveAspectRatio="none" role="img" aria-label="24-uurs forecastgrafiek"></svg>
        <div class="pm-time-axis" id="pm-time-axis"></div>
      </div>
    </section>

    <section class="pm-section">
      <h2>Geplande tijdsvakken</h2>
      <div class="pm-slots" id="pm-slots"></div>
    </section>
  </div>
</div>

<style>
  .planner-minimal{max-width:1200px;margin:0 auto}
  .pm-status{padding:1rem 0;color:var(--md-default-fg-color--light)}
  .pm-status.pm-error{color:var(--md-typeset-color)}
  .pm-section{margin:1.25rem 0 2rem}
  .pm-section h2{margin-bottom:.25rem}
  .pm-note{margin:.25rem 0 1rem;color:var(--md-default-fg-color--light);font-size:.9rem}
  .pm-timeline{width:100%;min-width:0}
  .pm-forecast{display:block;width:100%;height:260px;background:var(--md-code-bg-color);border-radius:.45rem;overflow:visible}
  .pm-time-axis{display:grid;grid-template-columns:repeat(8,1fr);font-size:.72rem;color:var(--md-default-fg-color--light);margin-top:.35rem}
  .pm-time-axis span:last-child{text-align:right}
  .pm-slots{display:grid;gap:.8rem}
  .pm-row{display:grid;grid-template-columns:78px minmax(0,1fr);align-items:center;gap:.75rem}
  .pm-row-label{font-weight:600;font-size:.85rem}
  .pm-track{position:relative;height:34px;background:var(--md-code-bg-color);border-radius:.4rem;overflow:hidden}
  .pm-segment{position:absolute;top:5px;height:24px;border-radius:.3rem;background:var(--md-accent-fg-color);min-width:2px}
  .pm-segment.boiler{opacity:.75}
  .pm-segment.battery{opacity:.5}
  .pm-empty{font-size:.85rem;color:var(--md-default-fg-color--light);padding:.45rem .6rem}
  .pm-legend{display:flex;flex-wrap:wrap;gap:.8rem;margin:.6rem 0 .8rem;font-size:.8rem;color:var(--md-default-fg-color--light)}
  .pm-key{display:inline-flex;align-items:center;gap:.35rem}
  .pm-key i{display:inline-block;width:18px;height:3px;border-radius:3px;background:currentColor}
  .pm-key.base{color:#7e57c2}.pm-key.pv{color:#2e7d32}.pm-key.net{color:#c62828}
  @media(max-width:600px){.pm-forecast{height:220px}.pm-row{grid-template-columns:64px minmax(0,1fr);gap:.5rem}.pm-row-label{font-size:.78rem}.pm-time-axis{font-size:.66rem}}
</style>

<script>
(() => {
  const ROOT = document.getElementById('planner-minimal');
  if (!ROOT || ROOT.dataset.initialized === '1') return;
  ROOT.dataset.initialized = '1';

  const DATA_URL = 'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-planner-shadow.json';
  const status = document.getElementById('pm-status');
  const content = document.getElementById('pm-content');
  const svg = document.getElementById('pm-forecast');
  const axis = document.getElementById('pm-time-axis');
  const slotsEl = document.getElementById('pm-slots');
  const NS = 'http://www.w3.org/2000/svg';

  const finite = v => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));
  const unwrap = payload => payload?.plan?.plan?.actions ? payload.plan : (payload?.plan || payload || {});
  const hhmm = iso => {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '—' : d.toLocaleTimeString('nl-NL', {hour:'2-digit', minute:'2-digit'});
  };
  const svgEl = (name, attrs={}) => {
    const n = document.createElementNS(NS, name);
    Object.entries(attrs).forEach(([k,v]) => n.setAttribute(k, v));
    return n;
  };

  function linePath(actions, key, maxAbs) {
    const pts = [];
    actions.forEach((a,i) => {
      if (!finite(a[key])) return;
      const x = actions.length > 1 ? i * 960 / (actions.length - 1) : 0;
      const y = 130 - (Number(a[key]) / maxAbs) * 108;
      pts.push(`${pts.length ? 'L' : 'M'} ${x.toFixed(2)} ${Math.max(12,Math.min(248,y)).toFixed(2)}`);
    });
    return pts.join(' ');
  }

  function renderForecast(actions) {
    svg.replaceChildren();
    const all = [];
    for (const a of actions) for (const k of ['baseLoadForecastW','pvForecastW','netBeforeFlexW']) if (finite(a[k])) all.push(Math.abs(Number(a[k])));
    const maxAbs = Math.max(1000, ...all);

    svg.append(svgEl('line',{x1:0,y1:130,x2:960,y2:130,stroke:'currentColor','stroke-opacity':'.25','stroke-width':'1'}));
    for (let i=0;i<=8;i++) {
      const x=i*120;
      svg.append(svgEl('line',{x1:x,y1:0,x2:x,y2:260,stroke:'currentColor','stroke-opacity':'.08','stroke-width':'1'}));
    }

    const series = [
      ['baseLoadForecastW','#7e57c2'],
      ['pvForecastW','#2e7d32'],
      ['netBeforeFlexW','#c62828']
    ];
    series.forEach(([key,color]) => {
      const d=linePath(actions,key,maxAbs);
      if (!d) return;
      svg.append(svgEl('path',{d,fill:'none',stroke:color,'stroke-width':'2.4','vector-effect':'non-scaling-stroke'}));
    });

    const legend=document.createElement('div'); legend.className='pm-legend';
    [['base','Base load'],['pv','PV'],['net','Net vóór flex']].forEach(([c,t])=>{const s=document.createElement('span');s.className=`pm-key ${c}`;s.innerHTML='<i></i>'+t;legend.append(s);});
    svg.parentElement.insertBefore(legend,svg);

    axis.replaceChildren();
    for(let h=0;h<=21;h+=3){const s=document.createElement('span');s.textContent=String(h).padStart(2,'0')+':00';axis.append(s);}
  }

  function actionActive(asset,a) {
    const raw = String(a?.[asset] ?? 'HOLD').toUpperCase();
    return !(raw === 'HOLD' || raw === 'NONE' || raw === 'OFF' || raw === '0' || raw === '');
  }

  function addRow(label, asset, cssClass, actions) {
    const row=document.createElement('div'); row.className='pm-row';
    const name=document.createElement('div'); name.className='pm-row-label'; name.textContent=label;
    const track=document.createElement('div'); track.className='pm-track';
    row.append(name,track);

    let start=null;
    const flush=end=>{
      if(start===null)return;
      const seg=document.createElement('div'); seg.className=`pm-segment ${cssClass}`;
      seg.style.left=`${start/actions.length*100}%`;
      seg.style.width=`${(end-start)/actions.length*100}%`;
      const first=actions[start], last=actions[end-1];
      seg.title=`${label}: ${hhmm(first.start)}–${hhmm(last.end || new Date(new Date(last.start).getTime()+15*60000).toISOString())}`;
      track.append(seg);
    };
    for(let i=0;i<=actions.length;i++){
      const active=i<actions.length && actionActive(asset,actions[i]);
      if(active && start===null) start=i;
      if(!active && start!==null){flush(i);start=null;}
    }
    if(!track.children.length){const e=document.createElement('div');e.className='pm-empty';e.textContent='geen tijdsvakken';track.append(e);}
    slotsEl.append(row);
  }

  async function load() {
    try {
      const r = await fetch(`${DATA_URL}?ts=${Date.now()}`, {cache:'no-store'});
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const payload = await r.json();
      const p = unwrap(payload);
      const actions = Array.isArray(p?.plan?.actions) ? p.plan.actions : [];
      if (!actions.length) throw new Error('geen kwartierslots in plannerdata');
      renderForecast(actions);
      slotsEl.replaceChildren();
      addRow('Tesla','tesla','tesla',actions);
      addRow('Boiler','warmWater','boiler',actions);
      if(actions.some(a=>actionActive('battery',a))) addRow('Accu','battery','battery',actions);
      status.remove();
      content.hidden=false;
    } catch (e) {
      status.className='pm-status pm-error';
      status.textContent=`Plannerdata laden mislukt: ${e.message}`;
    }
  }

  load();
})();
</script>
