(function(){
  'use strict';
  const n=v=>Number.isFinite(Number(v))?Number(v):0;
  const pos=v=>Math.max(0,n(v));
  const fmt=v=>`${Math.round(Number(v)||0).toLocaleString('nl-NL')} W`;
  const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  function node(x,y,w,h,kicker,title,value,sub='',cls=''){
    return `<g class="energy-node ${cls}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="14"/><text x="${x+w/2}" y="${y+21}" text-anchor="middle" class="energy-kicker">${esc(kicker)}</text><text x="${x+w/2}" y="${y+46}" text-anchor="middle" class="energy-title">${esc(title)}</text><text x="${x+w/2}" y="${y+72}" text-anchor="middle" class="energy-value">${esc(value)}</text>${sub?`<text x="${x+w/2}" y="${y+94}" text-anchor="middle" class="energy-sub">${esc(sub)}</text>`:''}</g>`;
  }
  function path(d,w,kind='grid',active=true,label='',lx=0,ly=0){
    const width=active?clamp(2.5+Math.abs(n(w))/750,3,9):2;
    return `<g><path class="energy-path energy-${kind} ${active?'is-active':'is-idle'}" d="${d}" style="stroke-width:${width}" marker-end="url(#arrow-${kind})"/>${label?`<text x="${lx}" y="${ly}" text-anchor="middle" class="energy-edge-label">${esc(label)}</text>`:''}</g>`;
  }
  function appliance(load){
    const known=!!(load&&load.power_w!==null&&load.power_w!==undefined&&Number.isFinite(Number(load.power_w)));
    const power=known?pos(load.power_w):0;
    const active=load?.active===true;
    return {known,power,active,value:known?fmt(power):'—',sub:active?(known?'actief':'actief · vermogen niet apart gemeten'):'niet actief'};
  }
  function renderRaw(r,freshness){
    const root=document.getElementById('live-energy-flow'); if(!root||!r)return;
    const g=r.grid||{},p=r.pv||{},t=r.tesla||{},hw=r.hot_water||{},q=r.quatt||r.heating||{},b=r.battery||{},loads=r.loads||{},m=r.meta||{},eb=r.energy_budget||{};
    const se=pos(p.solaredge_w),gw42=pos(p.goodwe_4200_w),gw20=pos(p.goodwe_2000_w),pv=pos(p.total_w)||se+gw42+gw20;
    const grid=n(g.power_w),importW=Math.max(0,grid),exportW=Math.max(0,-grid);
    const batt=n(b.power_w),charge=batt>0?batt:0,discharge=batt<0?Math.abs(batt):0;
    const house=Number.isFinite(Number(eb.house_load_w))?pos(eb.house_load_w):Math.max(0,pv+grid+discharge-charge);
    const tesla=pos(t.power_w),boiler=pos(hw.boiler_power_w),quatt=pos(q.power_w??q.quatt_power_w);
    const washer=appliance(loads.washer),dryer=appliance(loads.dryer);
    const otherKnownExtras=['dishwasher','quooker'].reduce((sum,k)=>{const x=loads[k];return sum+(x&&x.power_w!==null&&x.power_w!==undefined&&Number.isFinite(Number(x.power_w))?pos(x.power_w):0);},0);
    const other=Math.max(0,house-tesla-boiler-quatt-washer.power-dryer.power-otherKnownExtras);
    const thermal=pos(q.thermal_power_w),thermo=q.thermostat_heating_on===true,cvReq=q.cv_requested===true,cvKnown=typeof q.cv_flame==='boolean',cvFlame=q.cv_flame===true;
    const working=[q.working_mode_1,q.working_mode_2].some(v=>String(v??'0')!=='0'&&String(v??'').toLowerCase()!=='unknown');
    const quattActive=thermal>100||working||(quatt>100&&thermo);
    let heatSub='geen warmtevraag';
    if(quattActive&&cvFlame)heatSub='Quatt + CV · hybride'; else if(quattActive&&cvReq&&!cvKnown)heatSub='Quatt · CV ondersteuning gevraagd'; else if(quattActive)heatSub='Quatt actief'; else if(cvFlame)heatSub='CV verwarmt'; else if(cvReq)heatSub='CV ondersteuning gevraagd'; else if(thermo)heatSub='warmtevraag';
    const uncertain=[!washer.known&&washer.active?'wasmachine':'',!dryer.known&&dryer.active?'droger':''].filter(Boolean);
    const otherSub=uncertain.length?`incl. niet-gemeten ${uncertain.join(' + ')}`:'rest na bekende vermogens';
    const fresh=freshness!==false;

    const W=1500,H=760;
    let svg=`<svg class="energy-svg energy-dashboard" viewBox="0 0 ${W} ${H}" role="img" aria-label="Live energiestroom"><defs><marker id="arrow-pv" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L0,8 L8,4 z" class="arrow-pv"/></marker><marker id="arrow-grid" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L0,8 L8,4 z" class="arrow-grid"/></marker><marker id="arrow-battery" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L0,8 L8,4 z" class="arrow-battery"/></marker></defs>`;

    svg+=node(40,25,400,110,'PRODUCTIE','SolarEdge SE3680H',fmt(se),'PV-omvormer','source');
    svg+=node(550,25,400,110,'PRODUCTIE','GoodWe GW4200D-NS',fmt(gw42),'PV-omvormer','source');
    svg+=node(1060,25,400,110,'PRODUCTIE','GoodWe GW2000-XS',fmt(gw20),'PV-omvormer','source');
    svg+=path('M240 135 V180 H750 V245',se,'pv',se>0);
    svg+=path('M750 135 V245',gw42,'pv',gw42>0);
    svg+=path('M1260 135 V180 H750 V245',gw20,'pv',gw20>0);

    svg+=node(95,270,340,125,'NET / METER (P1)','Grid',fmt(Math.abs(grid)),grid>0?'import':grid<0?'export':'in balans','grid');
    svg+=node(580,270,340,125,'WONING','Huis',fmt(house),'centrale energiebalans','house');
    svg+=node(1065,270,340,125,'BATTERIJ','Victron batterij',charge?`Laden ${fmt(charge)}`:discharge?`Ontladen ${fmt(discharge)}`:'Niet actief',charge||discharge?'live energiestroom':'voorbereid op ESS','battery');
    if(importW>0)svg+=path('M435 332 H580',importW,'grid',true,`Grid → Huis · ${fmt(importW)}`,507,316);else if(exportW>0)svg+=path('M580 332 H435',exportW,'grid',true,`Huis → Grid · ${fmt(exportW)}`,507,316);else svg+=path('M435 332 H580',0,'grid',false,'in balans',507,316);
    if(charge>0)svg+=path('M920 332 H1065',charge,'battery',true,`Huis → Accu · ${fmt(charge)}`,992,316);else if(discharge>0)svg+=path('M1065 332 H920',discharge,'battery',true,`Accu → Huis · ${fmt(discharge)}`,992,316);else svg+=path('M920 332 H1065',0,'battery',false,'inactief',992,316);

    const consumers=[
      {x:15,title:'Tesla',value:fmt(tesla),sub:t.charging?'laden':(t.connected?'aangesloten':'niet aangesloten'),w:tesla,active:tesla>0,sx:610},
      {x:260,title:'Boiler',value:fmt(boiler),sub:hw.boiler_on?'aan':'uit',w:boiler,active:boiler>0,sx:665},
      {x:505,title:'Ruimteverwarming',value:fmt(quatt),sub:heatSub,w:quatt,active:quatt>0,sx:720},
      {x:750,title:'Wasmachine',value:washer.value,sub:washer.sub,w:washer.power,active:washer.known&&washer.power>0,sx:780},
      {x:995,title:'Droger',value:dryer.value,sub:dryer.sub,w:dryer.power,active:dryer.known&&dryer.power>0,sx:835},
      {x:1240,title:'Overig',value:fmt(other),sub:otherSub,w:other,active:other>0,sx:890}
    ];
    consumers.forEach(c=>{const cx=c.x+115;svg+=path(`M${c.sx} 395 V475 H${cx} V535`,c.w,'grid',c.active);svg+=node(c.x,535,230,115,'VERBRUIK',c.title,c.value,c.sub,c.title==='Overig'?'load residual':'load');});
    svg+=`<text x="750" y="710" text-anchor="middle" class="energy-rule">Zes onafhankelijke verbruikstakken op één rij · Overig blijft de restcategorie na alle betrouwbaar bekende vermogens.</text></svg>`;

    const manager=`<div class="energy-manager-panel"><div class="energy-manager-title"><strong>Energiemanager</strong><span>functionele status</span></div><div class="energy-manager-grid"><div><small>TESLA</small><strong>${t.charging?'● Laden':'○ Niet laden'}</strong><span>${esc(t.need||r.manager?.decision||'HOLD')}</span></div><div><small>BOILER</small><strong>${hw.day_state?.goalReachedToday||hw.day_state?.goalReached?'● Dagdoel bereikt':hw.boiler_on?'● Verwarmt':'○ Dagdoel open'}</strong><span>${esc(hw.control?.reason||'')}</span></div><div><small>RUIMTEVERWARMING</small><strong>${quattActive&&cvReq?'● Hybride':quattActive?'● Quatt verwarmt':cvReq?'● CV gevraagd':'○ Geen warmtevraag'}</strong><span>${esc(heatSub)}${thermal?` · thermisch ${fmt(thermal)}`:''}</span></div></div></div>`;
    root.innerHTML=`<div class="energy-topline"><span><strong>EM v2 revision ${m.state_revision??'?'}</strong> · bron ${m.source_sample_at?new Date(m.source_sample_at).toLocaleString('nl-NL'):'onbekend'}</span><span class="${fresh?'energy-ok':'energy-stale'}">${fresh?'● actueel':'● vertraagd'}</span></div>${svg}${manager}`;
  }
  function renderDetail(d){renderRaw(d?.raw,d?.stateFresh&&d?.heartbeatFresh);}
  async function fallback(){try{const u=new URL('../data/energy-state-v2.json',location.href);u.searchParams.set('v',Date.now());const res=await fetch(u,{cache:'no-store'});if(!res.ok)throw new Error('HTTP '+res.status);const raw=await res.json();const age=Date.now()-Date.parse(raw?.meta?.source_sample_at||raw?.meta?.generated_at||'');renderRaw(raw,Number.isFinite(age)&&age<12*60*1000);}catch(e){const root=document.getElementById('live-energy-flow');if(root)root.innerHTML=`<p><strong>Live energiestroom kon niet worden geladen.</strong><br><small>${esc(e.message||e)}</small></p>`;}}
  function boot(){if(!document.getElementById('live-energy-flow'))return;if(window.EnergyCoreV2?.state)renderDetail(window.EnergyCoreV2.state);else fallback();}
  document.addEventListener('energycorev2state',e=>renderDetail(e.detail));
  document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,200));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(boot,100));
  setTimeout(boot,800);
})();
