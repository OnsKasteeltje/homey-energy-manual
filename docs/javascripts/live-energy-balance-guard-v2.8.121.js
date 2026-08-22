(function(){
  'use strict';
  const TOLERANCE_W=75;
  let latestRaw=null,rootObserver=null,documentObserver=null,observedRoot=null,scheduled=false,applying=false;
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
  const findNode=(root,title)=>[...root.querySelectorAll('.energy-node')].find(n=>n.querySelector('.energy-title')?.textContent?.trim()===title);
  function setNode(node,value,sub){if(!node)return;const v=node.querySelector('.energy-value'),s=node.querySelector('.energy-sub');if(v)v.textContent=value;if(s)s.textContent=sub;}
  function purgeLegacySourceSkew(root){if(!root)return;root.querySelectorAll('.energy-balance-warning').forEach(el=>{const txt=String(el.textContent||'').toLowerCase();if(txt.includes('balans indicatief')||txt.includes('bronmomenten verschillen'))el.remove();});}
  function setPanel(root,mode,displayHouse,measuredAssigned,estimatedAssigned,other){
    const panels=[...root.querySelectorAll('.heating-hybrid-panel .energy-manager-grid > div')],b=panels.find(x=>x.querySelector('small')?.textContent?.trim()==='ENERGIEBALANS');if(!b)return;
    const strong=b.querySelector('strong'),span=b.querySelector('span');
    if(mode==='valid'){
      if(strong)strong.textContent=`Woning ${fmt(displayHouse)}`;
      if(span){const estimatedPart=estimatedAssigned>0?` · indicatief toegewezen ${fmt(estimatedAssigned)}`:'';span.textContent=`top-level toegewezen ${fmt(measuredAssigned)}${estimatedPart} · Overig ${fmt(other)}`;}
    }else{
      if(strong)strong.textContent=`Woning ~${fmt(displayHouse)}`;
      if(span)span.textContent='indicatief uit P1 + PV · detailbalans onzeker · geen control-impact';
    }
  }
  function setWarning(root,mode){purgeLegacySourceSkew(root);const top=root.querySelector('.energy-topline');if(!top)return;let w=top.querySelector('.energy-balance-warning');if(mode==='valid'){if(w)w.remove();return;}if(!w){w=document.createElement('span');w.className='energy-balance-warning energy-stale';top.appendChild(w);}w.textContent='● weergavebalans onzeker';}

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
      const coreCandidate=num(r.balance?.physical_house_candidate_w);
      const displayHouse=coreCandidate!==null&&coreCandidate>=0?coreCandidate:(Number.isFinite(rawHouse)&&rawHouse>=0?rawHouse:null);
      const directBase=pos(t.power_w)+pos(hw.boiler_power_w)+pos(q.power_w??q.quatt_power_w);
      const loadInfos=[loads.washer,loads.dryer,loads.quooker].map(powerInfo),measuredLoads=loadInfos.filter(x=>!x.estimated).reduce((s,x)=>s+x.value,0),estimatedLoads=loadInfos.filter(x=>x.estimated).reduce((s,x)=>s+x.value,0),measuredAssigned=directBase+measuredLoads,assigned=measuredAssigned+estimatedLoads;
      const physicalValid=Number.isFinite(rawHouse)&&rawHouse>=-TOLERANCE_W&&rawHouse+TOLERANCE_W>=assigned;
      const mode=physicalValid?'valid':'invalid';
      const house=physicalValid?Math.max(0,rawHouse):displayHouse;
      const other=physicalValid?Math.max(0,house-assigned):null;
      const houseNode=findNode(root,'Huis'),otherNode=findNode(root,'Overig');
      if(physicalValid){
        setNode(houseNode,fmt(house),'weergave uit gepubliceerde P1/PV-snapshot');
        setNode(otherNode,fmt(other),estimatedLoads>0?'weergaverest na directe + indicatieve toewijzing':'weergaverest na bekende top-level vermogens');
      }else{
        setNode(houseNode,displayHouse!==null?`~${fmt(displayHouse)}`:'—',displayHouse!==null?'indicatief uit P1 + PV · balans onzeker':'weergavebalans onzeker');
        setNode(otherNode,'—','detailtoewijzing onzeker · geen control-impact');
      }
      setPanel(root,mode,house,measuredAssigned,estimatedLoads,other);setWarning(root,mode);
      root.dataset.balanceStatus=mode;
      root.dataset.balanceMeasurementPolicy='presentation-only-indicative-house';
      root.dataset.balanceControlImpact='none';
      root.dataset.balanceGuardVersion='2.8.121';
    }finally{applying=false;}
  }
  function schedule(){if(scheduled)return;scheduled=true;setTimeout(()=>{scheduled=false;ensureAttached();apply();},0);}
  function ensureAttached(){const root=document.getElementById('live-energy-flow');if(root===observedRoot)return;if(rootObserver)rootObserver.disconnect();observedRoot=root||null;if(root){rootObserver=new MutationObserver(schedule);rootObserver.observe(root,{childList:true,subtree:true,characterData:true});}}
  function reconcile(){ensureAttached();schedule();[80,250,600,1200].forEach(ms=>setTimeout(()=>{ensureAttached();apply();},ms));}
  document.addEventListener('energycorev2state',e=>{latestRaw=presentationSnapshot(e.detail?.raw)||latestRaw;reconcile();});
  document.addEventListener('DOMContentLoaded',reconcile);document.addEventListener('DOMContentSwitch',reconcile);document.addEventListener('appdatarefresh',reconcile);window.addEventListener('pageshow',reconcile);document.addEventListener('visibilitychange',()=>{if(!document.hidden)reconcile();});documentObserver=new MutationObserver(()=>{const root=document.getElementById('live-energy-flow');if(root!==observedRoot)reconcile();});const boot=()=>{if(document.body)documentObserver.observe(document.body,{childList:true,subtree:true});reconcile();};if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
