(function(){
  'use strict';
  const TOLERANCE_W=75;
  let latestRaw=null,rootObserver=null,documentObserver=null,observedRoot=null,scheduled=false,applying=false;
  const num=v=>Number.isFinite(Number(v))?Number(v):null;
  const pos=v=>Math.max(0,Number(v)||0);
  const fmt=v=>`${Math.round(Number(v)||0).toLocaleString('nl-NL')} W`;
  const knownPower=load=>load&&load.power_w!==null&&load.power_w!==undefined&&Number.isFinite(Number(load.power_w))?pos(load.power_w):0;
  const findNode=(root,title)=>[...root.querySelectorAll('.energy-node')].find(n=>n.querySelector('.energy-title')?.textContent?.trim()===title);
  function setNode(node,value,sub){if(!node)return;const v=node.querySelector('.energy-value'),s=node.querySelector('.energy-sub');if(v)v.textContent=value;if(s)s.textContent=sub;}
  function setPanel(root,mode,house,assigned,other){const panels=[...root.querySelectorAll('.heating-hybrid-panel .energy-manager-grid > div')],b=panels.find(x=>x.querySelector('small')?.textContent?.trim()==='ENERGIEBALANS');if(!b)return;const strong=b.querySelector('strong'),span=b.querySelector('span');if(mode==='valid'){if(strong)strong.textContent=`Woning ${fmt(house)}`;if(span)span.textContent=`bekend toegewezen ${fmt(assigned)} · Overig ${fmt(other)}`;}else if(mode==='source-skew'){if(strong)strong.textContent=`Woning ≈ ${fmt(house)}`;if(span)span.textContent=`indicatief · bronmomenten verschillen · Overig ≈ ${fmt(other)}`;}else{if(strong)strong.textContent='Woning —';if(span)span.textContent='fysieke balans sluit niet · wacht op nieuwe snapshot';}}
  function setWarning(root,mode){const top=root.querySelector('.energy-topline');if(!top)return;let w=top.querySelector('.energy-balance-warning');if(mode==='valid'){if(w)w.remove();return;}if(!w){w=document.createElement('span');w.className='energy-balance-warning energy-stale';top.appendChild(w);}w.textContent=mode==='source-skew'?'● balans indicatief · bronmomenten verschillen':'● balans ongeldig';}
  function apply(){const root=document.getElementById('live-energy-flow'),r=latestRaw||window.EnergyCoreV2?.state?.raw;if(!root||!r||applying)return;applying=true;try{const p=r.pv||{},g=r.grid||{},b=r.battery||{},t=r.tesla||{},hw=r.hot_water||{},q=r.quatt||r.heating||{},loads=r.loads||{};const pv=num(p.total_w)!==null?pos(p.total_w):pos(p.solaredge_w)+pos(p.goodwe_4200_w)+pos(p.goodwe_2000_w),grid=num(g.power_w)??0,batt=num(b.power_w),charge=batt!==null&&batt>0?batt:0,discharge=batt!==null&&batt<0?Math.abs(batt):0,rawHouse=pv+grid+discharge-charge,assigned=pos(t.power_w)+pos(hw.boiler_power_w)+pos(q.power_w??q.quatt_power_w)+knownPower(loads.washer)+knownPower(loads.dryer)+knownPower(loads.dishwasher)+knownPower(loads.quooker);const physicalValid=Number.isFinite(rawHouse)&&rawHouse>=-TOLERANCE_W&&rawHouse+TOLERANCE_W>=assigned,core=r.balance||{},reason=String(core.reason||'').toUpperCase(),sourceSkew=physicalValid&&core.valid===false&&reason==='SOURCE_SKEW',mode=physicalValid?(sourceSkew?'source-skew':'valid'):'invalid',house=physicalValid?Math.max(0,rawHouse):null,other=physicalValid?Math.max(0,house-assigned):null,houseNode=findNode(root,'Huis'),otherNode=findNode(root,'Overig');if(physicalValid){setNode(houseNode,sourceSkew?`≈ ${fmt(house)}`:fmt(house),sourceSkew?'indicatief · bronmomenten verschillen':'centrale energiebalans');setNode(otherNode,sourceSkew?`≈ ${fmt(other)}`:fmt(other),sourceSkew?'incl. niet apart gemeten actieve apparaten':'rest na bekende vermogens');}else{setNode(houseNode,'—','fysieke balans sluit niet');setNode(otherNode,'—','wacht op nieuwe snapshot');}setPanel(root,mode,house,assigned,other);setWarning(root,mode);root.dataset.balanceStatus=mode;}finally{applying=false;}}
  function schedule(){if(scheduled)return;scheduled=true;setTimeout(()=>{scheduled=false;ensureAttached();apply();},0);}
  function ensureAttached(){const root=document.getElementById('live-energy-flow');if(root===observedRoot)return;if(rootObserver)rootObserver.disconnect();observedRoot=root||null;if(root){rootObserver=new MutationObserver(schedule);rootObserver.observe(root,{childList:true,subtree:true,characterData:true});}}
  function reconcile(){ensureAttached();schedule();[80,250,600,1200].forEach(ms=>setTimeout(()=>{ensureAttached();apply();},ms));}
  document.addEventListener('energycorev2state',e=>{latestRaw=e.detail?.raw||latestRaw;reconcile();});
  document.addEventListener('DOMContentLoaded',reconcile);
  document.addEventListener('DOMContentSwitch',reconcile);
  document.addEventListener('appdatarefresh',reconcile);
  window.addEventListener('pageshow',reconcile);
  window.addEventListener('popstate',reconcile);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)reconcile();});
  documentObserver=new MutationObserver(()=>{const root=document.getElementById('live-energy-flow');if(root!==observedRoot)reconcile();});
  const boot=()=>{if(document.body)documentObserver.observe(document.body,{childList:true,subtree:true});reconcile();};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
