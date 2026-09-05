# Planner

<div id="planner-minimal" class="planner-minimal">
  <div class="pm-status" id="pm-status">Plannerdata laden…</div>
  <div class="pm-content" id="pm-content" hidden>
    <section class="pm-section">
      <h2>24-uurs forecast</h2>
      <p class="pm-note">Base load, PV en verwachte import/export. Positief = import; negatief = export.</p>
      <div class="pm-legend">
        <span><i class="pm-key base"></i>Base load</span>
        <span><i class="pm-key pv"></i>PV</span>
        <span><i class="pm-key net"></i>Verwachte import/export</span>
      </div>
      <div class="pm-balance-chart" id="pm-forecast" aria-label="24-uurs forecastgrafiek"></div>
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
  .pm-section{margin:1.1rem 0 1.5rem}
  .pm-section h2{font-size:.9rem;margin:0 0 .3rem}
  .pm-note{margin:.15rem 0 .45rem;color:var(--md-default-fg-color--light);font-size:.7rem}
  .pm-legend{display:flex;flex-wrap:wrap;gap:.35rem .7rem;margin-bottom:.4rem}
  .pm-legend span{font-size:.64rem;display:inline-flex;align-items:center;gap:.25rem}
  .pm-key{display:inline-block;width:.62rem;height:.62rem;border-radius:2px}
  .pm-key.base,.pm-bar.base{background:#6e7f90}
  .pm-key.pv,.pm-bar.pv{background:#d7a900}
  .pm-key.net,.pm-bar.net.import{background:#3277b3}
  .pm-bar.net.export{background:#2e9b67}
  .pm-balance-chart{display:grid;grid-template-columns:repeat(96,minmax(5px,1fr));gap:1px;height:185px;border:1px solid var(--md-default-fg-color--lightest);border-radius:.45rem;padding:.35rem .2rem .2rem;overflow:hidden;background:color-mix(in srgb,var(--md-default-bg-color) 96%,var(--md-default-fg-color) 4%)}
  .pm-balance-col{min-width:0;display:flex;flex-direction:column;align-items:center;min-height:0}
  .pm-balance-plot{position:relative;width:100%;height:150px}
  .pm-zero{position:absolute;left:0;right:0;top:50%;border-top:1px solid var(--md-default-fg-color--lightest)}
  .pm-bar{position:absolute;width:26%;min-height:2px}
  .pm-bar.base{left:4%;border-radius:2px 2px 0 0}
  .pm-bar.pv{left:36%;border-radius:2px 2px 0 0}
  .pm-bar.net{left:68%}
  .pm-bar.net.import{border-radius:2px 2px 0 0}
  .pm-bar.net.export{border-radius:0 0 2px 2px}
  .pm-time{font-size:.48rem;opacity:.7;white-space:nowrap;transform:translateX(-1px)}
  .pm-slots{display:grid;gap:.22rem}
  .pm-row{display:grid;grid-template-columns:64px minmax(0,1fr);gap:.4rem;align-items:center}
  .pm-row-label{font-size:.62rem;font-weight:700;opacity:.78;text-align:right}
  .pm-track{position:relative;height:24px;border-bottom:1px solid var(--md-default-fg-color--lightest)}
  .pm-segment{position:absolute;top:3px;height:18px;border-radius:.25rem;min-width:2px}
  .pm-segment.tesla{background:#8f4ac7}
  .pm-segment.boiler{background:#2aa9b8}
  .pm-segment.battery{background:#66aa45}
  .pm-empty{font-size:.62rem;opacity:.65;line-height:24px}
  @media(prefers-color-scheme:dark){.pm-key.base,.pm-bar.base{background:#98a8b7}.pm-key.pv,.pm-bar.pv{background:#e4bd35}.pm-key.net,.pm-bar.net.import{background:#69a4d7}.pm-bar.net.export{background:#54b889}}
  @media(max-width:600px){.pm-balance-chart{height:170px;grid-template-columns:repeat(96,minmax(3px,1fr))}.pm-balance-plot{height:135px}.pm-row{grid-template-columns:54px minmax(0,1fr)}.pm-row-label{font-size:.56rem}}
</style>

<script>
(() => {
  const ROOT = document.getElementById('planner-minimal');
  if (!ROOT || ROOT.dataset.initialized === '1') return;
  ROOT.dataset.initialized = '1';

  const DATA_URL = 'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-planner-shadow.json';
  const status = document.getElementById('pm-status');
  const content = document.getElementById('pm-content');
  const forecast = document.getElementById('pm-forecast');
  const slotsEl = document.getElementById('pm-slots');

  const finite = v => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));
  const unwrap = payload => payload?.plan?.plan?.actions ? payload.plan : (payload?.plan || payload || {});
  const hhmm = iso => {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '—' : d.toLocaleTimeString('nl-NL', {hour:'2-digit', minute:'2-digit'});
  };

  function renderForecast(actions) {
    forecast.replaceChildren();
    const values=[];
    actions.forEach(a=>{
      ['baseLoadForecastW','pvForecastW','netBeforeFlexW'].forEach(k=>{if(finite(a[k]))values.push(Math.abs(Number(a[k])));});
    });
    const max=Math.max(1000,...values);

    actions.forEach((a,idx)=>{
      const col=document.createElement('div'); col.className='pm-balance-col';
      const plot=document.createElement('div'); plot.className='pm-balance-plot';
      const zero=document.createElement('div'); zero.className='pm-zero'; plot.append(zero);
      const addBar=(kind,v)=>{
        if(!finite(v))return;
        const n=Number(v), h=Math.max(2,Math.min(48,Math.abs(n)/max*48));
        const b=document.createElement('div'); b.className=`pm-bar ${kind}`;
        b.style.height=`${h}%`;
        if(kind==='net'){
          b.classList.add(n<0?'export':'import');
          b.style.bottom=n<0?`${50-h}%`:'50%';
        } else b.style.bottom='50%';
        b.title=`${hhmm(a.start)} · ${kind==='base'?'Base load':kind==='pv'?'PV':'Verwachte import/export'} ${Math.round(n)} W`;
        plot.append(b);
      };
      addBar('base',a.baseLoadForecastW);
      addBar('pv',a.pvForecastW);
      addBar('net',a.netBeforeFlexW);
      col.append(plot);
      if(idx%12===0){const t=document.createElement('span');t.className='pm-time';t.textContent=hhmm(a.start);col.append(t);}
      forecast.append(col);
    });
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
