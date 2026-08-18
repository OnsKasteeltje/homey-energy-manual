(function(){
  'use strict';
  const num=v=>Number.isFinite(Number(v))?Number(v):null;
  const pos=v=>Math.max(0,Number(v)||0);
  const fmt=v=>`${Math.round(Number(v)||0).toLocaleString('nl-NL')} W`;

  function findNode(root,title){
    return [...root.querySelectorAll('.energy-node')].find(g=>[...g.querySelectorAll('text')].some(t=>t.textContent===title));
  }
  function setNode(node,value,sub){
    if(!node)return;
    const texts=node.querySelectorAll('text');
    if(texts[2])texts[2].textContent=value;
    if(sub&&texts[3])texts[3].textContent=sub;
  }
  function knownPower(load){
    return load&&load.power_w!==null&&load.power_w!==undefined&&Number.isFinite(Number(load.power_w))?pos(load.power_w):0;
  }
  function apply(detail){
    const root=document.getElementById('live-energy-flow');
    const r=detail?.raw;
    if(!root||!r)return;
    const p=r.pv||{},g=r.grid||{},b=r.battery||{},t=r.tesla||{},hw=r.hot_water||{},q=r.quatt||r.heating||{},loads=r.loads||{},eb=r.energy_budget||{};
    const pv=num(p.total_w)!==null?pos(p.total_w):pos(p.solaredge_w)+pos(p.goodwe_4200_w)+pos(p.goodwe_2000_w);
    const grid=num(g.power_w)??0;
    const batt=num(b.power_w);
    const charge=batt!==null&&batt>0?batt:0;
    const discharge=batt!==null&&batt<0?Math.abs(batt):0;
    const physical=pv+grid+discharge-charge;
    const core=num(eb.house_load_w);
    const tolerance=75;
    const physicalValid=Number.isFinite(physical)&&physical>=0;
    const coreValid=core!==null&&core>=0;
    let house=null;
    if(physicalValid&&coreValid&&Math.abs(physical-core)<=tolerance)house=Math.max(0,core);
    else if(physicalValid)house=Math.max(0,physical);
    else if(coreValid&&core>0)house=core;

    const houseNode=findNode(root,'Huis');
    const otherNode=findNode(root,'Overig');
    if(house===null){
      setNode(houseNode,'—','onvolledige energiebalans');
      setNode(otherNode,'—','wacht op sluitende snapshot');
      return;
    }

    const tesla=pos(t.power_w),boiler=pos(hw.boiler_power_w),quatt=pos(q.power_w??q.quatt_power_w);
    const washer=knownPower(loads.washer),dryer=knownPower(loads.dryer),dishwasher=knownPower(loads.dishwasher),quooker=knownPower(loads.quooker);
    const other=Math.max(0,house-tesla-boiler-quatt-washer-dryer-dishwasher-quooker);
    setNode(houseNode,fmt(house),'centrale energiebalans');
    setNode(otherNode,fmt(other),'rest na bekende vermogens');

    const panels=[...root.querySelectorAll('.heating-hybrid-panel .energy-manager-grid > div')];
    const balance=panels.find(x=>x.querySelector('small')?.textContent==='ENERGIEBALANS');
    if(balance){
      const strong=balance.querySelector('strong'),span=balance.querySelector('span');
      const assigned=tesla+boiler+quatt+washer+dryer+dishwasher+quooker;
      if(strong)strong.textContent=`Woning ${fmt(house)}`;
      if(span)span.textContent=`bekend toegewezen ${fmt(assigned)} · Overig ${fmt(other)}`;
    }
  }
  document.addEventListener('energycorev2state',e=>setTimeout(()=>apply(e.detail),40));
  document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>{if(window.EnergyCoreV2?.state)apply(window.EnergyCoreV2.state);},700));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(()=>{if(window.EnergyCoreV2?.state)apply(window.EnergyCoreV2.state);},300));
})();