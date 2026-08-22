(function(){
  'use strict';
  const TOLERANCE_W=75;
  let latestRaw=null,applying=false;
  const num=v=>Number.isFinite(Number(v))?Number(v):null;
  const pos=v=>Math.max(0,Number(v)||0);
  const fmt=v=>`${Math.round(Number(v)||0).toLocaleString('nl-NL')} W`;

  // PRESENTATION BOUNDARY: display-only. Never feed presentation values back into Core/control.
  function presentationSnapshot(raw){
    if(!raw)return null;
    try{return typeof structuredClone==='function'?structuredClone(raw):JSON.parse(JSON.stringify(raw));}
    catch(_){return null;}
  }
  function powerInfo(load){
    const value=load&&load.power_w!==null&&load.power_w!==undefined&&Number.isFinite(Number(load.power_w))?pos(load.power_w):0;
    const estimated=Boolean(load&&(load.power_estimated===true||String(load.power_source||'').toUpperCase()==='P1_TRANSITION_MODEL'));
    return{value,estimated};
  }
  function derivedGate(raw){
    const gate=raw?.balance?.control_gate?.derived_house_balance_valid;
    if(typeof gate==='boolean')return gate;
    const budgetGate=raw?.energy_budget?.derived_house_balance_valid;
    return typeof budgetGate==='boolean'?budgetGate:null;
  }
  const findNode=(root,title)=>[...root.querySelectorAll('.energy-node')].find(n=>n.querySelector('.energy-title')?.textContent?.trim()===title);
  function setNode(node,value,sub){if(!node)return;const v=node.querySelector('.energy-value'),s=node.querySelector('.energy-sub');if(v)v.textContent=value;if(s)s.textContent=sub;}
  function purgeLegacySourceSkew(root){if(!root)return;root.querySelectorAll('.energy-balance-warning').forEach(el=>el.remove());}
  function setPanel(root,mode,house,measuredAssigned,estimatedAssigned,other){
    const panels=[...root.querySelectorAll('.heating-hybrid-panel .energy-manager-grid > div')],b=panels.find(x=>x.querySelector('small')?.textContent?.trim()==='ENERGIEBALANS');if(!b)return;
    const strong=b.querySelector('strong'),span=b.querySelector('span');
    if(mode==='valid'){
      if(strong)strong.textContent=`Woning ${fmt(house)}`;
      if(span){const estimatedPart=estimatedAssigned>0?` · indicatief toegewezen ${fmt(estimatedAssigned)}`:'';span.textContent=`top-level toegewezen ${fmt(measuredAssigned)}${estimatedPart} · Overig ${fmt(other)}`;}
    }else if(mode==='async'){
      if(strong)strong.textContent='Woning —';
      if(span)span.textContent='P1/PV niet tijdgelijk · Huis/Overig niet betrouwbaar te reconstrueren · geen control-impact';
    }else{
      if(strong)strong.textContent='Woning —';
      if(span)span.textContent='weergavebalans onzeker · geen control-impact';
    }
  }
  function setWarning(root,mode){purgeLegacySourceSkew(root);const top=root.querySelector('.energy-topline');if(!top||mode==='valid')return;const w=document.createElement('span');w.className='energy-balance-warning energy-stale';w.textContent=mode==='async'?'● P1/PV niet tijdgelijk':'● weergavebalans onzeker';top.appendChild(w);}

  function apply(){
    const root=document.getElementById('live-energy-flow');
    const source=latestRaw||window.EnergyCoreV2?.state?.raw;
    const r=presentationSnapshot(source);
    if(!root||!r||applying)return;
    applying=true;
    try{
      purgeLegacySourceSkew(root);
      const p=r.pv||{},g=r.grid||{},b=r.battery||{},t=r.tesla||{},hw=r.hot_water||{},q=r.quatt||r.heating||{},loads=r.loads||{};
      const pv=num(p.total_w)!==null?pos(p.total_w):pos(p.solaredge_w)+pos(p.goodwe_4200_w)+pos(p.goodwe_2000_w),grid=num(g.power_w),batt=num(b.power_w),charge=batt!==null&&batt>0?batt:0,discharge=batt!==null&&batt<0?Math.abs(batt):0;
      const rawHouse=grid!==null?pv+grid+discharge-charge:NaN;
      const directBase=pos(t.power_w)+pos(hw.boiler_power_w)+pos(q.power_w??q.quatt_power_w);
      const loadInfos=[loads.washer,loads.dryer,loads.quooker].map(powerInfo),measuredLoads=loadInfos.filter(x=>!x.estimated).reduce((s,x)=>s+x.value,0),estimatedLoads=loadInfos.filter(x=>x.estimated).reduce((s,x)=>s+x.value,0),measuredAssigned=directBase+measuredLoads,assigned=measuredAssigned+estimatedLoads;
      const gate=derivedGate(r);
      const sourceAsync=gate===false&&(r.balance?.reason==='ASYNC_PV_RECONSTRUCTION_UNCERTAIN'||r.balance?.source_timing?.synchronized===false||r.balance?.source_timing?.warning==='SOURCE_SKEW_WARNING');
      const physicalValid=gate===false?false:(Number.isFinite(rawHouse)&&rawHouse>=-TOLERANCE_W&&rawHouse+TOLERANCE_W>=assigned);
      const mode=physicalValid?'valid':sourceAsync?'async':'invalid';
      const house=physicalValid?Math.max(0,rawHouse):null;
      const other=physicalValid?Math.max(0,house-assigned):null;
      const houseNode=findNode(root,'Huis'),otherNode=findNode(root,'Overig');
      if(physicalValid){
        setNode(houseNode,fmt(house),'weergave uit gepubliceerde P1/PV-snapshot');
        setNode(otherNode,fmt(other),estimatedLoads>0?'weergaverest na directe + indicatieve toewijzing':'weergaverest na bekende top-level vermogens');
      }else if(sourceAsync){
        setNode(houseNode,'—','P1/PV niet tijdgelijk · weergave uitgesteld');
        setNode(otherNode,'—','restverbruik niet betrouwbaar te bepalen');
      }else{
        setNode(houseNode,'—','weergavebalans onzeker');
        setNode(otherNode,'—','detailtoewijzing onzeker · geen control-impact');
      }
      setPanel(root,mode,house,measuredAssigned,estimatedLoads,other);setWarning(root,mode);
      root.dataset.balanceStatus=mode;
      root.dataset.balanceMeasurementPolicy='core-derived-gate-authoritative';
      root.dataset.balanceControlImpact='none';
      root.dataset.balanceGuardVersion='2.8.124';
    }finally{applying=false;}
  }

  // Core determines whether derived House/Overig is trustworthy. The presentation layer
  // may become stricter, but must never resurrect a diagnostic candidate after Core gated it off.
  document.addEventListener('energycorev2state',e=>{latestRaw=presentationSnapshot(e.detail?.raw)||latestRaw;});
  document.addEventListener('liveenergyrendered',apply);
  document.addEventListener('DOMContentSwitch',apply);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',apply,{once:true});
  else apply();
})();
