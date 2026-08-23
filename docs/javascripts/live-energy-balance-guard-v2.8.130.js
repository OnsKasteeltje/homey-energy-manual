(function(){
  'use strict';

  // DISPLAY ONLY. This module never affects EMS control decisions.
  // Simple presentation policy:
  // - Net = direct P1 measurement.
  // - PV = direct sum/current PV measurement.
  // - House = PV + grid + battery discharge - battery charge, but never negative.
  // - Direct device cards always keep their own measurements.
  // - Overig is only shown when the house balance is physically coherent.
  const TOLERANCE_W=75;
  const LAST_HOUSE_KEY='hems:last-valid-house';
  const LAST_HOUSE_MAX_AGE_MS=10*60*1000;

  let latestRaw=null;
  let applying=false;
  let lastValidHouse=null;

  const num=v=>Number.isFinite(Number(v))?Number(v):null;
  const pos=v=>Math.max(0,Number(v)||0);
  const fmt=v=>`${Math.round(Number(v)||0).toLocaleString('nl-NL')} W`;
  const findNode=(root,title)=>[...root.querySelectorAll('.energy-node')].find(n=>n.querySelector('.energy-title')?.textContent?.trim()===title);

  try{
    const cached=JSON.parse(localStorage.getItem(LAST_HOUSE_KEY)||'null');
    if(cached&&Number.isFinite(Number(cached.w))&&Number.isFinite(Number(cached.at)))lastValidHouse={w:Math.max(0,Number(cached.w)),at:Number(cached.at)};
  }catch(_){/* optional cache */}

  function clone(raw){
    if(!raw)return null;
    try{return typeof structuredClone==='function'?structuredClone(raw):JSON.parse(JSON.stringify(raw));}
    catch(_){return null;}
  }

  function setNode(node,value,sub){
    if(!node)return;
    const v=node.querySelector('.energy-value'),s=node.querySelector('.energy-sub');
    if(v)v.textContent=value;
    if(s)s.textContent=sub;
  }

  function directAssigned(r){
    const t=r.tesla||{},hw=r.hot_water||{},q=r.quatt||r.heating||{},loads=r.loads||{};
    const loadPower=load=>load&&load.power_w!==null&&load.power_w!==undefined&&Number.isFinite(Number(load.power_w))?pos(load.power_w):0;
    return pos(t.power_w)+pos(hw.boiler_power_w)+pos(q.power_w??q.quatt_power_w)+loadPower(loads.washer)+loadPower(loads.dryer)+loadPower(loads.quooker);
  }

  function rememberHouse(w){
    if(!Number.isFinite(w)||w<0)return;
    lastValidHouse={w,at:Date.now()};
    try{localStorage.setItem(LAST_HOUSE_KEY,JSON.stringify(lastValidHouse));}catch(_){/* optional cache */}
  }

  function fallbackHouse(assigned){
    if(lastValidHouse&&Date.now()-lastValidHouse.at<=LAST_HOUSE_MAX_AGE_MS)return {value:Math.max(lastValidHouse.w,assigned),prefix:'≈',note:'laatste geldige huistotaal; PV/P1 tijdelijk niet tijdgelijk'};
    return {value:Math.max(0,assigned),prefix:'≥',note:'minimaal direct gemeten verbruik; PV/P1 tijdelijk niet tijdgelijk'};
  }

  function clearWarnings(root){
    root?.querySelectorAll('.energy-balance-warning').forEach(el=>el.remove());
  }

  function addWarning(root,text){
    const top=root?.querySelector('.energy-topline');
    if(!top)return;
    const w=document.createElement('span');
    w.className='energy-balance-warning energy-stale';
    w.textContent=`● ${text}`;
    top.appendChild(w);
  }

  function setPanel(root,house,assigned,other,coherent,fallback){
    const panels=[...root.querySelectorAll('.heating-hybrid-panel .energy-manager-grid > div')];
    const panel=panels.find(x=>x.querySelector('small')?.textContent?.trim()==='ENERGIEBALANS');
    if(!panel)return;
    const strong=panel.querySelector('strong'),span=panel.querySelector('span');
    if(strong)strong.textContent=`Woning ${fallback?fallback.prefix:''}${fallback?' ':''}${fmt(house)}`;
    if(span)span.textContent=coherent?`bekend toegewezen ${fmt(assigned)} · Overig ${fmt(other)}`:fallback?.note||'PV/P1 tijdelijk niet tijdgelijk';
  }

  function apply(){
    const root=document.getElementById('live-energy-flow');
    const r=clone(latestRaw||window.EnergyCoreV2?.state?.raw);
    if(!root||!r||applying)return;
    applying=true;
    try{
      clearWarnings(root);

      const p=r.pv||{},g=r.grid||{},b=r.battery||{};
      const pv=num(p.total_w)!==null?pos(p.total_w):pos(p.solaredge_w)+pos(p.goodwe_4200_w)+pos(p.goodwe_2000_w);
      const grid=num(g.power_w);
      const batt=num(b.power_w);
      const charge=batt!==null&&batt>0?batt:0;
      const discharge=batt!==null&&batt<0?Math.abs(batt):0;
      const exportW=grid!==null?Math.max(0,-grid):0;
      const assigned=directAssigned(r);
      const candidate=grid!==null?pv+grid+discharge-charge:NaN;

      // One physical presentation check only. Without battery discharge, export cannot
      // exceed PV by more than measurement tolerance. A negative candidate means the same:
      // PV and P1 are not simultaneous enough to derive House for display.
      const coherent=Number.isFinite(candidate)&&candidate>=-TOLERANCE_W&&exportW<=pv+discharge+TOLERANCE_W;
      const houseNode=findNode(root,'Huis');
      const otherNode=findNode(root,'Overig');

      if(coherent){
        const house=Math.max(0,candidate);
        const other=Math.max(0,house-assigned);
        rememberHouse(house);
        setNode(houseNode,fmt(house),'totaal huisverbruik uit PV + P1/netbalans');
        setNode(otherNode,fmt(other),'rest van Huis na bekende apparaten');
        setPanel(root,house,assigned,other,true,null);
        root.dataset.balanceStatus='valid';
      }else{
        const fallback=fallbackHouse(assigned);
        setNode(houseNode,`${fallback.prefix} ${fmt(fallback.value)}`,fallback.note);
        setNode(otherNode,'—','restverbruik niet berekend zolang PV/P1 niet tijdgelijk zijn');
        setPanel(root,fallback.value,assigned,null,false,fallback);
        addWarning(root,'PV/P1 tijdelijk niet tijdgelijk');
        root.dataset.balanceStatus='async';
      }

      root.dataset.balanceMeasurementPolicy='display-only-simple-p1-pv-house-residual';
      root.dataset.balanceControlImpact='none';
      root.dataset.balanceGuardVersion='2.8.130-simple1';
    }finally{
      applying=false;
    }
  }

  document.addEventListener('energycorev2state',e=>{latestRaw=clone(e.detail?.raw)||latestRaw;});
  document.addEventListener('liveenergyrendered',()=>{apply();setTimeout(apply,0);});
  document.addEventListener('DOMContentSwitch',()=>{apply();setTimeout(apply,0);});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{apply();setTimeout(apply,0);},{once:true});
  else{apply();setTimeout(apply,0);}
})();
