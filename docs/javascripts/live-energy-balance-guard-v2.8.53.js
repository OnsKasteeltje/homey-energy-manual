(function(){
  'use strict';
  const TOLERANCE_W=75;
  let latestRaw=null,observer=null,scheduled=false,applying=false;
  const num=v=>Number.isFinite(Number(v))?Number(v):null;
  const pos=v=>Math.max(0,Number(v)||0);
  const fmt=v=>`${Math.round(Number(v)||0).toLocaleString('nl-NL')} W`;

  function knownPower(load){
    return load&&load.power_w!==null&&load.power_w!==undefined&&Number.isFinite(Number(load.power_w))?pos(load.power_w):0;
  }
  function findNode(root,title){
    return [...root.querySelectorAll('.energy-node')].find(node=>node.querySelector('.energy-title')?.textContent?.trim()===title);
  }
  function setNode(node,value,sub){
    if(!node)return;
    const val=node.querySelector('.energy-value');
    const txt=node.querySelector('.energy-sub');
    if(val)val.textContent=value;
    if(txt)txt.textContent=sub;
  }
  function setBalancePanel(root,valid,house,assigned,other){
    const panels=[...root.querySelectorAll('.heating-hybrid-panel .energy-manager-grid > div')];
    const balance=panels.find(x=>x.querySelector('small')?.textContent?.trim()==='ENERGIEBALANS');
    if(!balance)return;
    const strong=balance.querySelector('strong'),span=balance.querySelector('span');
    if(valid){
      if(strong)strong.textContent=`Woning ${fmt(house)}`;
      if(span)span.textContent=`bekend toegewezen ${fmt(assigned)} · Overig ${fmt(other)}`;
    }else{
      if(strong)strong.textContent='Woning —';
      if(span)span.textContent='PV/P1-bronnen niet tijdgelijk · wacht op sluitende snapshot';
    }
  }
  function setTopWarning(root,invalid){
    const top=root.querySelector('.energy-topline');
    if(!top)return;
    let warn=top.querySelector('.energy-balance-warning');
    if(invalid){
      if(!warn){
        warn=document.createElement('span');
        warn.className='energy-balance-warning energy-stale';
        top.appendChild(warn);
      }
      warn.textContent='● balans ongeldig';
    }else if(warn)warn.remove();
  }
  function apply(){
    const root=document.getElementById('live-energy-flow');
    const r=latestRaw||window.EnergyCoreV2?.state?.raw;
    if(!root||!r||applying)return;
    applying=true;
    if(observer)observer.disconnect();
    try{
      const p=r.pv||{},g=r.grid||{},b=r.battery||{},t=r.tesla||{},hw=r.hot_water||{},q=r.quatt||r.heating||{},loads=r.loads||{};
      const pv=num(p.total_w)!==null?pos(p.total_w):pos(p.solaredge_w)+pos(p.goodwe_4200_w)+pos(p.goodwe_2000_w);
      const grid=num(g.power_w)??0;
      const batt=num(b.power_w);
      const charge=batt!==null&&batt>0?batt:0;
      const discharge=batt!==null&&batt<0?Math.abs(batt):0;
      const rawHouse=pv+grid+discharge-charge;
      const assigned=pos(t.power_w)+pos(hw.boiler_power_w)+pos(q.power_w??q.quatt_power_w)
        +knownPower(loads.washer)+knownPower(loads.dryer)+knownPower(loads.dishwasher)+knownPower(loads.quooker);
      // A snapshot is only physically usable when the inferred house load is non-negative
      // and can at least contain all loads that are independently measured in that same payload.
      const valid=Number.isFinite(rawHouse)&&rawHouse>=-TOLERANCE_W&&rawHouse+TOLERANCE_W>=assigned;
      const house=valid?Math.max(0,rawHouse):null;
      const other=valid?Math.max(0,house-assigned):null;
      const houseNode=findNode(root,'Huis'),otherNode=findNode(root,'Overig');
      if(valid){
        setNode(houseNode,fmt(house),'centrale energiebalans');
        setNode(otherNode,fmt(other),'rest na bekende vermogens');
      }else{
        setNode(houseNode,'—','brondata niet tijdgelijk');
        setNode(otherNode,'—','wacht op sluitende snapshot');
      }
      setBalancePanel(root,valid,house,assigned,other);
      setTopWarning(root,!valid);
      root.dataset.balanceStatus=valid?'valid':'invalid-source-alignment';
    }finally{
      applying=false;
      if(observer)observer.observe(root,{childList:true,subtree:true,characterData:true});
    }
  }
  function schedule(){
    if(scheduled)return;
    scheduled=true;
    setTimeout(()=>{scheduled=false;apply();},0);
  }
  function attach(){
    const root=document.getElementById('live-energy-flow');
    if(!root)return;
    if(observer)observer.disconnect();
    observer=new MutationObserver(schedule);
    observer.observe(root,{childList:true,subtree:true,characterData:true});
    schedule();
  }
  document.addEventListener('energycorev2state',e=>{latestRaw=e.detail?.raw||latestRaw;schedule();});
  document.addEventListener('DOMContentLoaded',()=>setTimeout(attach,250));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(attach,120));
  setTimeout(attach,900);
})();
