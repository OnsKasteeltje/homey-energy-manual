(function(){
  'use strict';

  const Model=window.LiveEnergyModel;
  if(!Model){
    console.error('LiveEnergyModel ontbreekt; Live Energy renderer niet gestart.');
    return;
  }

  const {ACTIVE_THRESHOLD_W,n,fmt,activeW,isActive,buildViewModel}=Model;
  const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[m]));
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));

  function icon(name,x,y,s=1){
    const a=[];
    if(name==='pv') a.push('<rect x="-25" y="-12" width="50" height="30" rx="2"/><path d="M-20-12 L-26 18 M-7-12 L-10 18 M7-12 L10 18 M20-12 L26 18 M-25 3 H25 M0 18 V30 M-10 30 H10"/><circle cx="25" cy="-22" r="7"/><path d="M25-35 V-31 M25-13 V-9 M12-22 H16 M34-22 H38 M16-31 L19-28 M31-16 L34-13 M34-31 L31-28 M19-16 L16-13"/>');
    else if(name==='battery') a.push('<rect x="-20" y="-30" width="40" height="60" rx="6"/><rect x="-8" y="-37" width="16" height="7" rx="2"/><path d="M-12-15 H12 M-12 0 H12 M-12 15 H12"/>');
    else if(name==='grid') a.push('<path d="M0-35 L-24 28 M0-35 L24 28 M-18 12 H18 M-13-2 H13 M-8-16 H8 M-28 28 H28 M0-35 V30"/>');
    else if(name==='house') a.push('<path d="M-28 0 L0-27 L28 0 V28 H8 V6 H-8 V28 H-28 Z"/>');
    else if(name==='car') a.push('<path d="M-25 9 L-18-10 H18 L25 9 V20 H17 V14 H-17 V20 H-25 Z M-14 8 H14 M-12-10 L-7-18 H7 L12-10"/><circle cx="-14" cy="13" r="3"/><circle cx="14" cy="13" r="3"/>');
    else if(name==='boiler') a.push('<path d="M-8-28 C-20-10-20 2-8 9 C4 2 4-10-8-28 Z M9-18 V18 M3-18 H15 M3 18 H15"/>');
    else if(name==='heat') a.push('<path d="M-22 15 V-7 L0-25 L22-7 V15 H8 V2 H-8 V15 Z M-15 26 C-21 20-8 16-15 10 M0 26 C-6 20 7 16 0 10 M15 26 C9 20 22 16 15 10"/>');
    else if(name==='washer') a.push('<rect x="-22" y="-28" width="44" height="56" rx="3"/><circle cx="0" cy="5" r="14"/><path d="M-14-18 H4 M12-18 H15"/>');
    else if(name==='dryer') a.push('<rect x="-22" y="-28" width="44" height="56" rx="3"/><circle cx="0" cy="5" r="14"/><path d="M-14-18 H4 M12-18 H15 M-7 5 C-2-3 4-3 9 5 C4 13-2 13-7 5"/>');
    else if(name==='more') a.push('<circle cx="-14" cy="0" r="3"/><circle cx="0" cy="0" r="3"/><circle cx="14" cy="0" r="3"/>');
    return `<g class="energy-icon energy-icon-${name}" transform="translate(${x} ${y}) scale(${s})">${a.join('')}</g>`;
  }

  function node(x,y,w,h,title,value,sub,cls,ico){
    return `<g class="energy-node ${cls}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="18"/>${icon(ico,x+52,y+h/2,0.9)}<text x="${x+96}" y="${y+34}" class="energy-title">${esc(title)}</text><text x="${x+96}" y="${y+69}" class="energy-value">${esc(value)}</text><text x="${x+96}" y="${y+94}" class="energy-sub">${esc(sub)}</text></g>`;
  }

  function smallNode(x,y,w,h,title,value,sub,cls,ico,active){
    return `<g class="energy-node ${cls} ${active?'flow-active':'flow-idle'}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="16"/>${icon(ico,x+w/2,y+37,0.72)}<text x="${x+w/2}" y="${y+78}" text-anchor="middle" class="energy-title">${esc(title)}</text><text x="${x+w/2}" y="${y+105}" text-anchor="middle" class="energy-value">${esc(value)}</text><text x="${x+w/2}" y="${y+126}" text-anchor="middle" class="energy-sub">${esc(sub)}</text></g>`;
  }

  function path(d,w,kind='grid',active=true,extra='',arrow=true){
    const width=active?clamp(3+Math.abs(n(w))/850,3.5,8.5):2.0;
    return `<path class="energy-path energy-${kind} ${active?'is-active':'is-idle'} ${extra}" d="${d}" style="stroke-width:${width}"${arrow&&active?` marker-end="url(#arrow-${kind})"`:''}/>`;
  }

  function busPath(d,w,extra=''){
    const active=isActive(w),shown=activeW(w);
    return path(d,shown,'grid',active,`energy-consumption-segment ${extra}`,false);
  }

  function renderRaw(raw,freshness){
    const root=document.getElementById('live-energy-flow');
    if(!root||!raw) return;

    const vm=buildViewModel(raw,freshness);
    if(!vm) return;

    const {
      pv,grid,importW,exportW,charge,discharge,house,tesla,boiler,quatt,
      washer,dryer,other,heatSub,quattFlowActive,cvRequested,cvKnown,cvFlame,
      cvState,cvDiag,quattState,assigned,consumers,bus,fresh,meta,raw:source
    }=vm;

    const W=1500,H=900;
    let svg=`<svg class="energy-svg energy-dashboard concept-layout" viewBox="0 0 ${W} ${H}" role="img" aria-label="Live energiestroom"><defs><marker id="arrow-pv" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L0,8 L8,4 z" class="arrow-pv"/></marker><marker id="arrow-grid" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L0,8 L8,4 z" class="arrow-grid"/></marker><marker id="arrow-battery" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L0,8 L8,4 z" class="arrow-battery"/></marker><marker id="arrow-topology-start" markerWidth="9" markerHeight="9" refX="1" refY="4" orient="auto"><path d="M8,0 L8,8 L0,4 z" class="arrow-topology"/></marker><marker id="arrow-topology-end" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L0,8 L8,4 z" class="arrow-topology"/></marker></defs>`;

    svg+=node(90,55,360,125,'PV Opwek',fmt(pv),'SolarEdge + GoodWe','source','pv');
    svg+=node(570,55,360,125,'Batterij',charge?fmt(charge):discharge?fmt(discharge):'0 W',charge?'laden':discharge?'ontladen':'niet actief','battery','battery');
    svg+=node(1050,55,360,125,'Net',fmt(Math.abs(grid)),grid<0?'export':grid>0?'import':'in balans','grid','grid');
    svg+=node(570,285,360,125,'Huis',fmt(house),'netto woningverbruik','house','house');

    svg+=path('M450 118 H570',pv,'pv',pv>0);
    svg+=path('M270 180 V347 H570',pv,'pv',pv>0);
    if(charge>0) svg+=path('M750 180 V285',charge,'battery',true);
    else if(discharge>0) svg+=path('M750 285 V180',discharge,'battery',true);
    else svg+=path('M750 180 V285',0,'battery',false);

    if(importW>0) svg+=path('M1230 180 V347 H930',importW,'grid',true);
    else if(exportW>0) svg+=path('M930 347 H1230 V180',exportW,'grid',true);
    else svg+=path('M1230 180 V347 H930',0,'grid',false);

    svg+=`<path class="energy-grid-battery-link" d="M930 118 H1050" marker-start="url(#arrow-topology-start)" marker-end="url(#arrow-topology-end)"/>`;
    svg+=`<text x="990" y="99" text-anchor="middle" class="energy-topology-label">AC-bus</text>`;

    const busY=505;
    svg+=busPath(`M750 410 V${busY}`,bus.total,'energy-feed');
    svg+=busPath(`M750 ${busY} H630`,bus.leftHeat,'energy-left-to-heating');
    svg+=busPath(`M630 ${busY} H390`,bus.leftBoiler,'energy-heating-to-boiler');
    svg+=busPath(`M390 ${busY} H150`,bus.leftTesla,'energy-boiler-to-tesla');
    svg+=busPath(`M750 ${busY} H870`,bus.rightWasher,'energy-right-to-washer');
    svg+=busPath(`M870 ${busY} H1110`,bus.rightDryer,'energy-washer-to-dryer');
    svg+=busPath(`M1110 ${busY} H1350`,bus.rightOther,'energy-dryer-to-other');

    consumers.forEach(c=>{
      const cx=c.x+95;
      svg+=path(`M${cx} ${busY} V570`,activeW(c.w),'grid',c.active,'',true);
      svg+=smallNode(c.x,570,190,145,c.title,c.value,c.sub,c.title==='Overig'?'load residual':'load',c.ico,c.active);
    });

    svg+=`<g class="energy-legend"><rect x="55" y="760" width="650" height="105" rx="15"/><line x1="82" y1="793" x2="126" y2="793" class="legend-pv"/><text x="145" y="798">Opwek / laden / export</text><line x1="82" y1="825" x2="126" y2="825" class="legend-grid"/><text x="145" y="830">Actief verbruik &gt; ${ACTIVE_THRESHOLD_W} W</text><line x1="380" y1="793" x2="424" y2="793" class="legend-topology"/><text x="443" y="798">Net ↔ accu via AC-bus</text><text x="380" y="830" class="legend-note">≤ ${ACTIVE_THRESHOLD_W} W = stand-by/laag · geen actieve pijl</text></g>`;
    svg+=`<text x="750" y="886" text-anchor="middle" class="energy-rule">Waarden blijven meetkundig zichtbaar; actieve verbruiksstromen worden pas boven ${ACTIVE_THRESHOLD_W} W gemarkeerd.</text></svg>`;

    const hybrid=`<div class="energy-manager-panel heating-hybrid-panel"><div class="energy-manager-title"><strong>Verwarmingsopwekking · Quatt Hybrid</strong><span>één functioneel verwarmingssysteem</span></div><div class="energy-manager-grid"><div><small>QUATT WARMTEPOMP</small><strong>${fmt(quatt)} elektrisch</strong><span>${esc(quattState)}</span></div><div><small>CV-KETEL</small><strong>${esc(cvState)}</strong><span>${esc(cvDiag)}</span></div><div><small>ENERGIEBALANS</small><strong>Woning ${fmt(house)}</strong><span>bekend toegewezen ${fmt(assigned)} · Overig ${fmt(other)}</span></div></div></div>`;
    const manager=`<div class="energy-manager-panel"><div class="energy-manager-title"><strong>Energiemanager</strong><span>functionele status</span></div><div class="energy-manager-grid"><div><small>TESLA</small><strong>${isActive(tesla)?'● Laden':'○ Niet actief'}</strong><span>${esc(source.tesla.need||source.manager.decision||'HOLD')}</span></div><div><small>BOILER</small><strong>${source.hotWater.day_state?.goalReachedToday||source.hotWater.day_state?.goalReached?'● Dagdoel bereikt':isActive(boiler)?'● Verwarmt':'○ Geen actief verbruik'}</strong><span>${esc(source.hotWater.control?.reason||'')}</span></div><div><small>RUIMTEVERWARMING</small><strong>${quattFlowActive&&cvRequested?'● Hybride':quattFlowActive?'● Quatt verwarmt':cvRequested?'● CV gevraagd':'○ Geen actief elektrisch verbruik'}</strong><span>${esc(heatSub)}</span></div></div></div>`;

    root.innerHTML=`<div class="energy-topline"><span><strong>EM v2 revision ${meta.state_revision??'?'}</strong> · bron ${meta.source_sample_at?new Date(meta.source_sample_at).toLocaleString('nl-NL'):'onbekend'}</span><span class="${fresh?'energy-ok':'energy-stale'}">${fresh?'● actueel':'● vertraagd'}</span></div>${svg}${hybrid}${manager}`;
    root.dataset.activeConsumptionThresholdW=String(ACTIVE_THRESHOLD_W);
  }

  function renderDetail(detail){
    renderRaw(detail?.raw,detail?.stateFresh&&detail?.heartbeatFresh);
  }

  async function fallback(){
    try{
      const url=new URL('../data/energy-state-v2.json',location.href);
      url.searchParams.set('v',Date.now());
      const response=await fetch(url,{cache:'no-store'});
      if(!response.ok) throw new Error('HTTP '+response.status);
      const raw=await response.json();
      const age=Date.now()-Date.parse(raw?.meta?.source_sample_at||raw?.meta?.generated_at||'');
      renderRaw(raw,Number.isFinite(age)&&age<12*60*1000);
    }catch(error){
      const root=document.getElementById('live-energy-flow');
      if(root) root.innerHTML=`<p><strong>Live energiestroom kon niet worden geladen.</strong><br><small>${esc(error.message||error)}</small></p>`;
    }
  }

  function boot(){
    if(!document.getElementById('live-energy-flow')) return;
    if(window.EnergyCoreV2?.state) renderDetail(window.EnergyCoreV2.state);
    else fallback();
  }

  document.addEventListener('energycorev2state',event=>renderDetail(event.detail));
  document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,200));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(boot,100));
  setTimeout(boot,800);
})();
