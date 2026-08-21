(function(){
  'use strict';
  // v2.0.5: homepage uses Energy Core Tesla lifecycle, including post-deadline target completion.
  const fmtW=w=>{w=Number(w||0);return Math.abs(w)>=1000?`${(w/1000).toLocaleString('nl-NL',{maximumFractionDigits:2})} kW`:`${Math.round(w)} W`;};
  const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[m]));
  const fmtTime=value=>{const s=String(value||'').trim();if(!s)return '';const local=s.match(/T(\d{2}):(\d{2})(?::\d{2})?$/);if(local&&!/[zZ]|[+-]\d\d:?\d\d$/.test(s))return `${local[1]}:${local[2]}`;const d=new Date(s);return Number.isFinite(d.getTime())?new Intl.DateTimeFormat('nl-NL',{timeZone:'Europe/Amsterdam',hour:'2-digit',minute:'2-digit',hour12:false}).format(d):'';};
  const fmtKWh=value=>Number(value).toLocaleString('nl-NL',{maximumFractionDigits:2});
  const deadlinePast=value=>{const s=String(value||'').trim();if(!s)return false;const d=new Date(s.replace(' ','T'));return Number.isFinite(d.getTime())&&Date.now()>=d.getTime();};
  function teslaLifecycle(t){
    const status=String(t.deadline_status||t.lifecycle_status||'').toUpperCase();
    const remaining=Math.max(0,Number(t.remaining_kwh)||0);
    const amps=Math.max(0,Number(t.requested_a)||0);
    if(t.deadline_active===true)return {kind:'active',status,remaining,amps};
    if(status==='DEADLINE_REACHED')return {kind:'reached',status,remaining,amps};
    if(status==='DOEL_GEHAALD_NA_DEADLINE')return {kind:'missed_done',status,remaining,amps};
    if(status.includes('DEADLINE_MISSED'))return {kind:remaining>0.01?'missed_open':'missed_done',status,remaining,amps};
    if(deadlinePast(t.deadline_at)&&remaining>0.01)return {kind:'missed_open',status,remaining,amps};
    return {kind:'none',status,remaining,amps};
  }
  function render(detail){
    const root=document.getElementById('home-architecture');if(!root||!detail?.raw)return;
    const r=detail.raw,p=r.pv||{},g=r.grid||{},t=r.tesla||{},hw=r.hot_water||{},m=r.manager||{},meta=r.meta||{};
    const pv=Number(p.total_w)||0,p1=Number(g.power_w)||0,home=Math.max(0,pv+p1),ww=hw.day_state||{},ctrl=hw.control||{};
    const goalReachedToday=ww.goalReachedToday===true||ww.goal_reached_today===true||ww.goalReached===true||ww.goal_reached===true;
    const remainingFallback=ww.remainingFallbackMin??ww.remaining_fallback_min;
    const goalReachedAt=ww.goalReachedAt??ww.goal_reached_at??null;
    const wwGoal=goalReachedToday
      ? ['Dagdoel bereikt',goalReachedAt?`OP_TEMPERATUUR bereikt · geen heropwarming meer vandaag`:'OP_TEMPERATUUR vandaag bereikt · geen heropwarming meer vandaag','ok']
      : hw.boiler_power_w>1500
        ? ['Opwarmen bezig','Warmwatercyclus actief','warn']
        : ['Dagdoel nog bewaken',remainingFallback!=null?`${Math.round(remainingFallback)} min fallback resterend`:'Warmwaterstate wordt opgebouwd','off'];
    const teslaState=t.charging?`Laadt nu · ${fmtW(t.power_w)}`:t.connected?'Aangesloten · wacht op opportunity':'Niet aangesloten';
    const rawTeslaNeed=String(t.need||m.decision||'HOLD');
    const lifecycle=teslaLifecycle(t),deadlineParts=[];
    if(lifecycle.kind==='active'&&t.deadline_at){const time=fmtTime(t.deadline_at);if(time)deadlineParts.push(`Deadline ${time}`);}
    if(lifecycle.kind==='active'&&t.latest_start_at){const time=fmtTime(t.latest_start_at);if(time)deadlineParts.push(`uiterlijk starten ${time}`);}
    if(lifecycle.kind==='active'&&Number.isFinite(Number(t.remaining_kwh)))deadlineParts.push(`nog ${fmtKWh(t.remaining_kwh)} kWh`);
    let teslaNeedText='';
    if(lifecycle.kind==='active')teslaNeedText=deadlineParts.join(' · ')||rawTeslaNeed;
    else if(lifecycle.kind==='reached')teslaNeedText='Tesla gereed · doel vóór deadline gehaald';
    else if(lifecycle.kind==='missed_open')teslaNeedText=`Deadline gemist · doel wordt nog afgemaakt${lifecycle.amps?` · ${Math.round(lifecycle.amps)} A`:''}${lifecycle.remaining?` · ${fmtKWh(lifecycle.remaining)} kWh resterend`:''}`;
    else if(lifecycle.kind==='missed_done')teslaNeedText='Tesla gereed · deadline gemist';
    else teslaNeedText=rawTeslaNeed.toUpperCase()==='HOLD'?'Geen actieve laadopdracht':rawTeslaNeed;
    const fresh=detail.stateFresh&&detail.heartbeatFresh;
    root.innerHTML=`<div class="ha-shell"><div class="ha-head"><div><h2>Overzicht</h2><p>Energy Core v2 — centrale state, beslissing, shadow en publicatie.</p></div><div class="ha-health"><strong>${fresh?'✓ Energy Core v2 actueel':'⚠ Energy Core v2 vertraagd'}</strong><span>Revision ${meta.state_revision??'?'} · ${meta.source_sample_at?new Date(meta.source_sample_at).toLocaleString('nl-NL'):'geen brontijd'}</span></div></div><div class="ha-main">
      <section class="ha-stage measure"><div class="ha-title"><span class="ha-num">1</span>Meten & observeren</div><div class="ha-question">Wat weten we nu?</div><div class="ha-list"><div class="ha-row"><span>P1 / Net</span><span>${fmtW(p1)}</span></div><div class="ha-row"><span>PV · SolarEdge</span><span>${fmtW(p.solaredge_w)}</span></div><div class="ha-row"><span>PV · GoodWe 4,2kW</span><span>${fmtW(p.goodwe_4200_w)}</span></div><div class="ha-row"><span>PV · GoodWe 2kW</span><span>${fmtW(p.goodwe_2000_w)}</span></div><div class="ha-row"><span>Boiler</span><span>${hw.boiler_power_w>100?`verwarmen · ${fmtW(hw.boiler_power_w)}`:hw.boiler_on?'aan · thermostaat af':'uit'}</span></div></div><a class="ha-link" href="live-energie/">→ Naar energie-overzicht</a></section>
      <section class="ha-stage context"><div class="ha-title"><span class="ha-num">2</span>Context & forecast</div><div class="ha-question">Wat beïnvloedt onze keuzes?</div><div class="ha-list"><div class="ha-row"><span>Prijs & PV forecast</span><span>via EM2 context</span></div><div class="ha-row"><span>Auto beschikbaar</span><span>${t.connected?'ja / aangesloten':'nee'}</span></div><div class="ha-row"><span>Warmwatermodus</span><span>${hw.mode?'elektrische boiler':'CV / niet-elektrisch'}</span></div><div class="ha-row"><span>Datacontract</span><span>v${esc(meta.schema_version||'2.x')}</span></div></div></section>
      <section class="ha-stage decision"><div class="ha-title"><span class="ha-num">3</span>Energy Manager</div><div class="ha-question">Wat moet er gebeuren?</div><div class="ha-goals"><div class="ha-goal"><div class="ha-goal-icon">🚗</div><div><strong>Tesla laden</strong><span class="ha-goal-state ${t.charging?'ok':t.connected?'warn':'off'}">${teslaState}</span><small>${esc(teslaNeedText)}</small></div></div><div class="ha-goal"><div class="ha-goal-icon">💧</div><div><strong>Warm water</strong><span class="ha-goal-state ${wwGoal[2]}">${wwGoal[0]}</span><small>${wwGoal[1]}</small></div></div><div class="ha-goal"><div class="ha-goal-icon">◷</div><div><strong>Managerstatus</strong><span class="ha-goal-state">${esc(m.state||'UNKNOWN')}</span><small>${esc(m.reason||'')}</small></div></div></div></section>
      <section class="ha-stage shadow"><div class="ha-title"><span class="ha-num">4</span>Shadow / validatie</div><div class="ha-question">Revision-consistente vergelijking</div><div class="ha-list"><div class="ha-row"><span>State revision</span><span>${meta.state_revision??'?'}</span></div><div class="ha-row"><span>Decision revision</span><span>${meta.decision_revision??'?'}</span></div><div class="ha-row"><span>Shadow revision</span><span>${meta.shadow_revision??'?'}</span></div><div class="ha-row"><span>Tesla shadow</span><span>${esc(r.shadow?.comparison?.tesla||'—')}</span></div></div></section>
      <section class="ha-stage control"><div class="ha-title"><span class="ha-num">5</span>Aansturing</div><div class="ha-question">Wat zou v2 sturen?</div><div class="ha-list"><div class="ha-row"><span>Warm water</span><span>${ctrl.action?`${esc(ctrl.action)} · ${esc(ctrl.priority||'')}`:'shadow-state wordt opgebouwd'}</span></div><div class="ha-row"><span>Warmwater write</span><span>${ctrl.readOnly===false||ctrl.read_only===false?'actief':'read-only / SHADOW'}</span></div><div class="ha-row"><span>Tesla</span><span>deadline-regeling via Easee / Homey</span></div><div class="ha-row"><span>Victron</span><span>voorbereid / toekomst</span></div></div></section></div>
      <div class="ha-lanes"><div class="ha-lane"><div class="ha-lane-title"><strong>6 · Publicatie & historie</strong><span>Website leest alleen GitHub-data</span></div><div class="ha-chip"><strong>Publisher ${esc(meta.publisher_version||'')}</strong><span>${esc(meta.publish_reason||'')}</span></div><div class="ha-chip"><strong>Energiehistorie</strong><span>v2 5-minutenreeks</span></div><div class="ha-chip"><strong>Website</strong><span>geen Homey-call</span></div></div><div class="ha-lane"><div class="ha-lane-title"><strong>7 · Platform & infrastructuur</strong><span>Structureel lage Homey-load</span></div><div class="ha-chip"><strong>Collector</strong><span>1 centrale device-scan / 5 min</span></div><div class="ha-chip"><strong>Decision/Control</strong><span>Logic-only</span></div><div class="ha-chip"><strong>GitHub</strong><span>gebufferde state-publicatie</span></div></div></div>
      <div class="ha-kpis"><div class="ha-kpi"><span>PV-productie nu</span><strong>${fmtW(pv)}</strong></div><div class="ha-kpi"><span>Verbruik woning nu</span><strong>${fmtW(home)}</strong></div><div class="ha-kpi"><span>Netto net nu</span><strong>${fmtW(p1)}</strong></div><div class="ha-kpi"><span>Energy Manager</span><strong>${esc(m.state||'UNKNOWN')}</strong></div><div class="ha-kpi"><span>Warmwater dagdoel</span><strong>${goalReachedToday?'Bereikt':hw.boiler_power_w>100?'Verwarmen':'Nog bewaken'}</strong></div></div><div class="ha-foot">Dit overzicht gebruikt uitsluitend de gedeelde Energy Core v2-browserstate. De Tesla-deadlinekaart volgt de door Homey gepubliceerde deadline-lifecycle; een oude website-opdracht kan de actieve status niet overschrijven.</div></div>`;
  }
  function current(){if(window.EnergyCoreV2?.state)render(window.EnergyCoreV2.state);}
  document.addEventListener('energycorev2state',e=>render(e.detail));document.addEventListener('DOMContentLoaded',()=>setTimeout(current,250));document.addEventListener('DOMContentSwitch',()=>setTimeout(current,100));
})();
