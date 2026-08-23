(function(){
  'use strict';
  const TOLERANCE_W=75;
  let latestRaw=null,applying=false;
  const num=v=>Number.isFinite(Number(v))?Number(v):null;
  const pos=v=>Math.max(0,Number(v)||0);
  const fmt=v=>`${Math.round(Number(v)||0).toLocaleString('nl-NL')} W`;

  // PRESENTATION BOUNDARY: House is the authoritative total-consumption bucket.
  // Direct device measurements remain authoritative for their own device card, even when
  // the P1/PV-derived house total is temporarily asynchronous. Only residual allocation
  // (Overig) depends on a coherent house balance.
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
    // IMPORTANT: never blank Tesla/Boiler/Quatt/etc. here. Their own direct device source
    // remains valid independently of P1/PV synchronization. Only Overig is a residual.
    const otherNode=findNode(root,'Overig');
    setNode(otherNode,'—','restverbruik tijdelijk niet betrouwbaar te bepalen');
  }
  function setPanel(root,mode,house,measuredAssigned,estimatedAssigned,other,breakdownCoherent){
    const panels=[...root.querySelectorAll('.heating-hybrid-panel .energy-manager-grid > div')],b=panels.find(x=>x.querySelector('small')?.textContent?.trim()==='ENERGIEBALANS');if(!b)return;
    const strong=b.querySelector('strong'),span=b.querySelector('span');
    if(mode==='valid'){
      if(strong)strong.textContent=`Woning ${fmt(house)}`;
      if(span){const estimatedPart=estimatedAssigned>0?` · indicatief toegewezen ${fmt(estimatedAssigned)}`:'';span.textContent=`top-level toegewezen ${fmt(measuredAssigned)}${estimatedPart} · Overig ${fmt(other)}`;}
    }else if(mode==='async'){
      if(strong)strong.textContent=house!==null?`Woning ≈ ${fmt(house)}`:'Woning —';
      if(span)span.textContent=house===null?'P1/PV niet tijdgelijk · huisbalans niet beschikbaar · directe apparaatmetingen blijven geldig':breakdownCoherent?'P1/PV niet tijdgelijk · huistotaal indicatief · uitsplitsing binnen totaal':'P1/PV niet tijdgelijk · directe apparaatmetingen blijven zichtbaar · Overig onderdrukt';
    }else{
      if(strong)strong.textContent='Woning —';
      if(span)span.textContent='weergavebalans onzeker · directe apparaatmetingen blijven geldig · geen control-impact';
    }
  }
  function setWarning(root,mode,breakdownCoherent){
    purgeLegacySourceSkew(root);const top=root.querySelector('.energy-topline');if(!top||mode==='valid')return;
    const w=document.createElement('span');w.className='energy-balance-warning energy-stale';
    w.textContent=mode==='async'?(breakdownCoherent?'● P1/PV niet tijdgelijk':'● restbalans niet tijdgelijk'):'● weergavebalans onzeker';
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

      // P1/net balance determines the house total. Device measurements are NEVER added on top.
      // Conversely, an uncertain house reconstruction may NEVER invalidate a valid direct device reading.
      const rawHouse=grid!==null?pv+grid+discharge-charge:NaN;
      const directBase=pos(t.power_w)+pos(hw.boiler_power_w)+pos(q.power_w??q.quatt_power_w);
      const loadInfos=[loads.washer,loads.dryer,loads.quooker].map(powerInfo),measuredLoads=loadInfos.filter(x=>!x.estimated).reduce((s,x)=>s+x.value,0),estimatedLoads=loadInfos.filter(x=>x.estimated).reduce((s,x)=>s+x.value,0),measuredAssigned=directBase+measuredLoads,assigned=measuredAssigned+estimatedLoads;
      const gate=derivedGate(r);
      const sourceAsync=gate===false&&(r.balance?.reason==='ASYNC_PV_RECONSTRUCTION_UNCERTAIN'||r.balance?.source_timing?.synchronized===false||r.balance?.source_timing?.warning==='SOURCE_SKEW_WARNING');
      const rawHousePlausible=Number.isFinite(rawHouse)&&rawHouse>=-TOLERANCE_W;
      const allocationFits=rawHousePlausible&&assigned<=Math.max(0,rawHouse)+TOLERANCE_W;
      const physicalValid=gate===false?false:(rawHousePlausible&&allocationFits);
      const mode=physicalValid?'valid':sourceAsync?'async':'invalid';
      const house=(physicalValid||(sourceAsync&&rawHousePlausible))?Math.max(0,rawHouse):null;
      const breakdownCoherent=house!==null&&assigned<=house+TOLERANCE_W;
      const other=physicalValid?Math.max(0,house-assigned):null;
      const houseNode=findNode(root,'Huis'),otherNode=findNode(root,'Overig');

      if(physicalValid){
        setNode(houseNode,fmt(house),'totaal verbruik uit P1/netbalans');
        setNode(otherNode,fmt(other),estimatedLoads>0?'rest van Huis na directe + indicatieve toewijzing':'rest van Huis na bekende apparaten');
      }else if(sourceAsync){
        if(house!==null)setNode(houseNode,`≈ ${fmt(house)}`,'totaal verbruik uit P1/netbalans; PV/P1 niet tijdgelijk');
        else setNode(houseNode,'—','huisverbruik tijdelijk niet betrouwbaar te bepalen');
        if(breakdownCoherent)setNode(otherNode,fmt(Math.max(0,house-assigned)),'rest van Huis; bronnen niet tijdgelijk');
        else suppressResidual(root);
      }else{
        setNode(houseNode,'—','weergavebalans onzeker');
        suppressResidual(root);
      }

      setPanel(root,mode,house,measuredAssigned,estimatedLoads,other,breakdownCoherent);setWarning(root,mode,breakdownCoherent);
      root.dataset.balanceStatus=mode;
      root.dataset.breakdownCoherent=String(Boolean(breakdownCoherent));
      root.dataset.balanceMeasurementPolicy='p1-house-total-direct-device-independent-residual-guarded';
      root.dataset.balanceControlImpact='none';
      root.dataset.balanceGuardVersion='2.8.130-hotfix1';
    }finally{applying=false;}
  }

  document.addEventListener('energycorev2state',e=>{latestRaw=presentationSnapshot(e.detail?.raw)||latestRaw;});
  document.addEventListener('liveenergyrendered',()=>{apply();setTimeout(apply,0);});
  document.addEventListener('DOMContentSwitch',()=>{apply();setTimeout(apply,0);});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{apply();setTimeout(apply,0);},{once:true});
  else{apply();setTimeout(apply,0);}
})();
