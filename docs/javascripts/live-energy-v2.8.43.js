(function(){
  'use strict';
  const fmt=v=>`${Math.round(Number(v)||0).toLocaleString('nl-NL')} W`;
  const n=v=>Number.isFinite(Number(v))?Number(v):0;
  const pos=v=>Math.max(0,n(v));
  const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const measured=x=>x&&x.power_w!==null&&x.power_w!==undefined&&Number.isFinite(Number(x.power_w));
  const active=x=>x?.active===true;
  function card(title,value,sub){return `<div class="energy-node load"><div class="energy-kicker">VERBRUIK</div><div class="energy-title">${esc(title)}</div><div class="energy-value">${esc(value)}</div><div class="energy-sub">${esc(sub||'')}</div></div>`;}
  function applianceCard(title,x){
    if(measured(x)) return card(title,fmt(pos(x.power_w)),active(x)?'actief · gemeten vermogen':'niet actief · gemeten vermogen');
    return card(title,'—',active(x)?'● actief · vermogen niet apart gemeten':'○ niet actief · geen aparte wattmeting');
  }
  function renderRaw(r,freshness){
    const root=document.getElementById('live-energy-flow'); if(!root||!r)return;
    const g=r.grid||{},p=r.pv||{},t=r.tesla||{},hw=r.hot_water||{},q=r.quatt||r.heating||{},b=r.battery||{},loads=r.loads||{},m=r.meta||{};
    const pv=pos(p.total_w)||pos(p.solaredge_w)+pos(p.goodwe_4200_w)+pos(p.goodwe_2000_w);
    const grid=n(g.power_w),batt=n(b.power_w),battCharge=batt>0?batt:0,battDischarge=batt<0?Math.abs(batt):0;
    const house=Math.max(0,pv+grid+battDischarge-battCharge);
    const tesla=pos(t.power_w),boiler=pos(hw.boiler_power_w),quatt=pos(q.power_w??q.quatt_power_w);
    const washer=loads.washer||null,dryer=loads.dryer||null;
    const knownLoadKeys=['washer','dryer','dishwasher','quooker']; let knownAppliances=0; const unmetered=[];
    for(const k of knownLoadKeys){const x=loads[k];if(!x)continue;if(measured(x))knownAppliances+=pos(x.power_w);else if(active(x))unmetered.push(k);}
    const other=Math.max(0,house-tesla-boiler-quatt-knownAppliances);
    const thermal=pos(q.thermal_power_w),thermo=q.thermostat_heating_on===true,cvReq=q.cv_requested===true,cvKnown=typeof q.cv_flame==='boolean',cvFlame=q.cv_flame===true;
    const working=[q.working_mode_1,q.working_mode_2].some(v=>String(v??'0')!=='0'&&String(v??'').toLowerCase()!=='unknown');
    const quattActive=thermal>100||working||(quatt>100&&thermo);
    let heatSub='geen warmtevraag';
    if(quattActive&&cvFlame)heatSub='Quatt + CV · hybride';else if(quattActive&&cvReq&&!cvKnown)heatSub='Quatt · CV ondersteuning gevraagd';else if(quattActive)heatSub='Quatt actief';else if(cvFlame)heatSub='CV verwarmt';else if(cvReq)heatSub='CV ondersteuning gevraagd';else if(thermo)heatSub='warmtevraag · systeem wacht/start';
    const otherSub=unmetered.length?`rest; bevat actief maar niet watt-gemeten: ${unmetered.join(', ')}`:'rest na alle bekende vermogens';
    const fresh=freshness!==false;
    root.innerHTML=`
      <div class="energy-topline"><span><strong>EM v2 revision ${m.state_revision??'?'}</strong> · bron ${m.source_sample_at?new Date(m.source_sample_at).toLocaleString('nl-NL'):'onbekend'}</span><span class="${fresh?'energy-ok':'energy-stale'}">${fresh?'● actueel':'● vertraagd'}</span></div>
      <div class="energy-summary"><div><strong>PV</strong><br>${fmt(pv)}</div><div><strong>Woning</strong><br>${fmt(house)}</div><div><strong>Grid</strong><br>${grid>=0?`${fmt(grid)} import`:`${fmt(Math.abs(grid))} export`}</div><div><strong>Accu</strong><br>${battCharge?`${fmt(battCharge)} laden`:battDischarge?`${fmt(battDischarge)} ontladen`:'inactief'}</div></div>
      <div class="energy-manager-panel"><div class="energy-manager-title"><strong>Elektrisch verbruik woning</strong><span>bekende verbruikers + residu</span></div><div class="energy-manager-grid energy-load-grid">
        ${card('Tesla',fmt(tesla),t.charging?'laden':(t.connected?'aangesloten':'niet aangesloten'))}
        ${card('Boiler',fmt(boiler),hw.boiler_on?'aan':'uit')}
        ${card('Ruimteverwarming',fmt(quatt),heatSub)}
        ${applianceCard('Wasmachine',washer)}
        ${applianceCard('Droger',dryer)}
        ${card('Overig',fmt(other),otherSub)}
      </div></div>
      <div class="energy-manager-panel"><div class="energy-manager-title"><strong>Energiemanager</strong><span>functionele status</span></div><div class="energy-manager-grid"><div><small>TESLA</small><strong>${t.charging?'● Laden':'○ Niet laden'}</strong><span>${esc(t.need||r.manager?.decision||'HOLD')}</span></div><div><small>BOILER</small><strong>${hw.day_state?.goalReachedToday||hw.day_state?.goalReached?'● Dagdoel bereikt':hw.boiler_on?'● Verwarmt':'○ Dagdoel open'}</strong><span>${esc(hw.control?.reason||'')}</span></div><div><small>RUIMTEVERWARMING</small><strong>${quattActive&&cvReq?'● Hybride':quattActive?'● Quatt verwarmt':cvReq?'● CV gevraagd':'○ Geen warmtevraag'}</strong><span>${esc(heatSub)}${thermal?` · thermisch ${fmt(thermal)}`:''}</span></div></div></div>
      <p class="energy-rule">Overig = woning − Tesla − boiler − Quatt − alle overige individueel gemeten <code>loads.*.power_w</code>. Wasmachine en droger worden altijd expliciet getoond; zonder wattmeting blijven ze status-only en zit hun daadwerkelijke verbruik nog in Overig.</p>`;
  }
  function renderDetail(detail){renderRaw(detail?.raw,detail?.stateFresh&&detail?.heartbeatFresh);}
  async function fallback(){try{const u=new URL('../data/energy-state-v2.json',location.href);u.searchParams.set('v',Date.now());const res=await fetch(u,{cache:'no-store'});if(!res.ok)throw new Error('HTTP '+res.status);const raw=await res.json();const age=Date.now()-Date.parse(raw?.meta?.source_sample_at||raw?.meta?.generated_at||'');renderRaw(raw,Number.isFinite(age)&&age<12*60*1000);}catch(e){const root=document.getElementById('live-energy-flow');if(root)root.innerHTML=`<p><strong>Live energiestroom kon niet worden geladen.</strong><br><small>${esc(e.message||e)}</small></p>`;}}
  function boot(){if(!document.getElementById('live-energy-flow'))return;if(window.EnergyCoreV2?.state)renderDetail(window.EnergyCoreV2.state);else fallback();}
  document.addEventListener('energycorev2state',e=>renderDetail(e.detail));
  document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,200));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(boot,100));
  setTimeout(boot,800);
})();
