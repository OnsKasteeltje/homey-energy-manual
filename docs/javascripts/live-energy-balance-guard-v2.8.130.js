(function(){
  'use strict';
  const TOLERANCE_W=75;
  const HOUSE_CACHE_KEY='hems:last-valid-house-w';
  let latestRaw=null,applying=false;
  let lastValidHouseW=null;
  const num=v=>Number.isFinite(Number(v))?Number(v):null;
  const pos=v=>Math.max(0,Number(v)||0);
  const fmt=v=>`${Math.round(Number(v)||0).toLocaleString('nl-NL')} W`;

  try{
    const cached=Number(localStorage.getItem(HOUSE_CACHE_KEY));
    if(Number.isFinite(cached)&&cached>=0)lastValidHouseW=cached;
  }catch(_){/* storage is optional */}

  // PRESENTATION BOUNDARY:
  // 1) House is always a non-negative consumption number; never render '-'.
  // 2) Direct device measurements remain authoritative for their own cards.
  // 3) Without battery discharge, displayed net export may never numerically exceed a
  //    trustworthy simultaneous PV value. If it does, the PV sample is stale/asynchronous
  //    and is suppressed rather than presenting a physically impossible energy balance.
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
  function suppressResidual(root){
    const otherNode=findNode(root,'Overig');
    setNode(otherNode,'—','restverbruik tijdelijk niet betrouwbaar te bepalen');
  }
  function rememberValidHouse(value){
    if(!Number.isFinite(value)||value<0)return;
    lastValidHouseW=value;
    try{localStorage.setItem(HOUSE_CACHE_KEY,String(Math.round(value)));}catch(_){/* optional */}
  }
  function fallbackHouse(assigned,rawCandidate){
    const candidate=Number(rawCandidate);
    const floor=Math.max(0,Number(assigned)||0);
    if(Number.isFinite(candidate)&&candidate>=0)return Math.max(candidate,floor);
    if(Number.isFinite(lastValidHouseW))return Math.max(lastValidHouseW,floor);
    return floor;
  }
  function setPanel(root,mode,house,measuredAssigned,estimatedAssigned,other,breakdownCoherent,physicalMismatch){
    const panels=[...root.querySelectorAll('.heating-hybrid-panel .energy-manager-grid > div')],b=panels.find(x=>x.querySelector('small')?.textContent?.trim()==='ENERGIEBALANS');if(!b)return;
    const strong=b.querySelector('strong'),span=b.querySelector('span');
    if(mode==='valid'){
      if(strong)strong.textContent=`Woning ${fmt(house)}`;
      if(span){const estimatedPart=estimatedAssigned>0?` · indicatief toegewezen ${fmt(estimatedAssigned)}`:'';span.textContent=`top-level toegewezen ${fmt(measuredAssigned)}${estimatedPart} · Overig ${fmt(other)}`;}
    }else{
      if(strong)strong.textContent=`Woning ≈ ${fmt(house)}`;
      if(span)span.textContent=physicalMismatch?'PV/P1 niet tijdgelijk · fysiek onmogelijke PV/export-combinatie onderdrukt · Huis via veilige fallback':breakdownCoherent?'P1/PV niet tijdgelijk · huistotaal indicatief · uitsplitsing binnen totaal':'P1/PV niet tijdgelijk · directe apparaatmetingen blijven zichtbaar · Overig onderdrukt';
    }
  }
  function setWarning(root,mode,breakdownCoherent,physicalMismatch){
    purgeLegacySourceSkew(root);const top=root.querySelector('.energy-topline');if(!top||mode==='valid')return;
    const w=document.createElement('span');w.className='energy-balance-warning energy-stale';
    w.textContent=physicalMismatch?'● PV/P1 fysiek inconsistent':(breakdownCoherent?'● P1/PV niet tijdgelijk':'● restbalans niet tijdgelijk');
    top.appendChild(w);
  }

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
      const importW=grid!==null?Math.max(0,grid):0,exportW=grid!==null?Math.max(0,-grid):0;

      const rawHouse=grid!==null?pv+grid+discharge-charge:NaN;
      const directBase=pos(t.power_w)+pos(hw.boiler_power_w)+pos(q.power_w??q.quatt_power_w);
      const loadInfos=[loads.washer,loads.dryer,loads.quooker].map(powerInfo),measuredLoads=loadInfos.filter(x=>!x.estimated).reduce((s,x)=>s+x.value,0),estimatedLoads=loadInfos.filter(x=>x.estimated).reduce((s,x)=>s+x.value,0),measuredAssigned=directBase+measuredLoads,assigned=measuredAssigned+estimatedLoads;
      const gate=derivedGate(r);
      const sourceAsync=gate===false&&(r.balance?.reason==='ASYNC_PV_RECONSTRUCTION_UNCERTAIN'||r.balance?.source_timing?.synchronized===false||r.balance?.source_timing?.warning==='SOURCE_SKEW_WARNING');

      // Physical invariant: without battery discharge, export cannot exceed current PV
      // (allowing only a small measurement tolerance). Such a sample means PV and P1 are
      // not simultaneous; never present that impossible pair as if it were a valid balance.
      const physicalMismatch=exportW>0&&exportW>pv+discharge+TOLERANCE_W;
      const rawHousePlausible=Number.isFinite(rawHouse)&&rawHouse>=-TOLERANCE_W&&!physicalMismatch;
      const allocationFits=rawHousePlausible&&assigned<=Math.max(0,rawHouse)+TOLERANCE_W;
      const physicalValid=gate===false?false:(rawHousePlausible&&allocationFits);

      let house;
      if(physicalValid){
        house=Math.max(0,rawHouse);
        rememberValidHouse(house);
      }else{
        house=fallbackHouse(assigned,r.balance?.physical_house_candidate_w);
      }
      const mode=physicalValid?'valid':'async';
      const breakdownCoherent=physicalValid&&assigned<=house+TOLERANCE_W;
      const other=physicalValid?Math.max(0,house-assigned):null;
      const houseNode=findNode(root,'Huis'),otherNode=findNode(root,'Overig'),pvNode=findNode(root,'PV Opwek');

      if(physicalMismatch){
        setNode(pvNode,'—','PV-bronnen niet tijdgelijk met P1; waarde onderdrukt');
      }

      if(physicalValid){
        setNode(houseNode,fmt(house),'totaal verbruik uit P1/netbalans');
        setNode(otherNode,fmt(other),estimatedLoads>0?'rest van Huis na directe + indicatieve toewijzing':'rest van Huis na bekende apparaten');
      }else{
        setNode(houseNode,`≈ ${fmt(house)}`,physicalMismatch?'huisverbruik kan niet negatief zijn · veilige fallback op laatste geldige/gekende belasting':'totaal huisverbruik indicatief; P1/PV niet tijdgelijk');
        suppressResidual(root);
      }

      setPanel(root,mode,house,measuredAssigned,estimatedLoads,other,breakdownCoherent,physicalMismatch);setWarning(root,mode,breakdownCoherent,physicalMismatch);
      root.dataset.balanceStatus=mode;
      root.dataset.breakdownCoherent=String(Boolean(breakdownCoherent));
      root.dataset.physicalPvExportMismatch=String(Boolean(physicalMismatch));
      root.dataset.balanceMeasurementPolicy='house-never-negative-p1-grid-authoritative-pv-export-physical-invariant-direct-devices-independent';
      root.dataset.balanceControlImpact='none';
      root.dataset.balanceGuardVersion='2.8.130-hotfix2';
    }finally{applying=false;}
  }

  document.addEventListener('energycorev2state',e=>{latestRaw=presentationSnapshot(e.detail?.raw)||latestRaw;});
  document.addEventListener('liveenergyrendered',()=>{apply();setTimeout(apply,0);});
  document.addEventListener('DOMContentSwitch',()=>{apply();setTimeout(apply,0);});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{apply();setTimeout(apply,0);},{once:true});
  else{apply();setTimeout(apply,0);}
})();
