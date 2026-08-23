(function(){
  'use strict';

  // DISPLAY ONLY. This module never affects EMS control decisions.
  // Simple presentation policy:
  // - Net = direct P1 measurement.
  // - PV = direct inverter measurement.
  // - House = PV + grid + battery discharge - battery charge, only when physically coherent.
  // - If PV/P1 are not coherent enough, House is unknown ('—'), never estimated or cached.
  // - Direct device cards always keep their own measurements.
  // - Overig is only shown when House is known.
  const TOLERANCE_W=75;

  let latestRaw=null;
  let applying=false;

  const num=v=>Number.isFinite(Number(v))?Number(v):null;
  const pos=v=>Math.max(0,Number(v)||0);
  const fmt=v=>`${Math.round(Number(v)||0).toLocaleString('nl-NL')} W`;
  const findNode=(root,title)=>[...root.querySelectorAll('.energy-node')].find(n=>n.querySelector('.energy-title')?.textContent?.trim()===title);

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

  function clearWarnings(root){root?.querySelectorAll('.energy-balance-warning').forEach(el=>el.remove());}

  function addWarning(root,text){
    const top=root?.querySelector('.energy-topline');
    if(!top)return;
    const w=document.createElement('span');
    w.className='energy-balance-warning energy-stale';
    w.textContent=`● ${text}`;
    top.appendChild(w);
  }

  function setPanel(root,house,assigned,other,coherent){
    const panels=[...root.querySelectorAll('.heating-hybrid-panel .energy-manager-grid > div')];
    const panel=panels.find(x=>x.querySelector('small')?.textContent?.trim()==='ENERGIEBALANS');
    if(!panel)return;
    const strong=panel.querySelector('strong'),span=panel.querySelector('span');
    if(coherent){
      if(strong)strong.textContent=`Woning ${fmt(house)}`;
      if(span)span.textContent=`bekend toegewezen ${fmt(assigned)} · Overig ${fmt(other)}`;
    }else{
      if(strong)strong.textContent='Woning —';
      if(span)span.textContent='PV/P1 tijdelijk niet tijdgelijk';
    }
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

      // One display-only physical check. If export exceeds available PV + battery discharge,
      // or the derived house load would be materially negative, PV and P1 are not time-coherent.
      const coherent=Number.isFinite(candidate)&&candidate>=-TOLERANCE_W&&exportW<=pv+discharge+TOLERANCE_W;
      const houseNode=findNode(root,'Huis');
      const otherNode=findNode(root,'Overig');

      if(coherent){
        const house=Math.max(0,candidate);
        const other=Math.max(0,house-assigned);
        setNode(houseNode,fmt(house),'totaal huisverbruik uit PV + P1/netbalans');
        setNode(otherNode,fmt(other),'rest van Huis na bekende apparaten');
        setPanel(root,house,assigned,other,true);
        root.dataset.balanceStatus='valid';
      }else{
        setNode(houseNode,'—','PV/P1 tijdelijk niet tijdgelijk');
        setNode(otherNode,'—','restverbruik niet berekend zolang Huis onbekend is');
        setPanel(root,null,assigned,null,false);
        addWarning(root,'PV/P1 tijdelijk niet tijdgelijk');
        root.dataset.balanceStatus='async';
      }

      root.dataset.balanceMeasurementPolicy='display-only-simple-p1-pv-house-unknown-when-incoherent';
      root.dataset.balanceControlImpact='none';
      root.dataset.balanceGuardVersion='2.8.130-simple2';
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
