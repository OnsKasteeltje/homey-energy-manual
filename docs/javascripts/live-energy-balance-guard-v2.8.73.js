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
  function setBalancePanel(root,mode,house,assigned,other){
    const panels=[...root.querySelectorAll('.heating-hybrid-panel .energy-manager-grid > div')];
    const balance=panels.find(x=>x.querySelector('small')?.textContent?.trim()==='ENERGIEBALANS');
    if(!balance)return;
    const strong=balance.querySelector('strong'),span=balance.querySelector('span');
    if(mode==='valid'){
      if(strong)strong.textContent=`Woning ${fmt(house)}`;
      if(span)span.textContent=`bekend toegewezen ${fmt(assigned)} · Overig ${fmt(other)}`;
    }else if(mode==='source-skew'){
      if(strong)strong.textContent=`Woning ≈ ${fmt(house)}`;
      if(span)span.textContent=`indicatief · bronmomenten verschillen · Overig ≈ ${fmt(other)}`;
    }else{
      if(strong)strong.textContent='Woning —';
      if(span)span.textContent='fysieke balans sluit niet · wacht op nieuwe snapshot';
    }
  }
  function setTopWarning(root,mode){
    const top=root.querySelector('.energy-topline');
    if(!top)return;
    let warn=top.querySelector('.energy-balance-warning');
    if(mode==='valid'){
      if(warn)warn.remove();
      return;
    }
    if(!warn){
      warn=document.createElement('span');
      warn.className='energy-balance-warning energy-stale';
      top.appendChild(warn);
    }
    warn.textContent=mode==='source-skew'?'● balans indicatief · bronmomenten verschillen':'● balans ongeldig';
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

      // Device activity and measured power are deliberately separate concepts.
      // A RUNNING appliance with power_w=null remains part of Overig and must not invalidate the balance.
      const physicalValid=Number.isFinite(rawHouse)&&rawHouse>=-TOLERANCE_W&&rawHouse+TOLERANCE_W>=assigned;
      const coreBalance=r.balance||{};
      const coreReason=String(coreBalance.reason||'').toUpperCase();
      const sourceSkewOnly=physicalValid&&coreBalance.valid===false&&coreReason==='SOURCE_SKEW';
      const mode=physicalValid?(sourceSkewOnly?'source-skew':'valid'):'invalid';
      const house=physicalValid?Math.max(0,rawHouse):null;
      const other=physicalValid?Math.max(0,house-assigned):null;
      const houseNode=findNode(root,'Huis'),otherNode=findNode(root,'Overig');

      if(physicalValid){
        setNode(houseNode,mode==='source-skew'?`≈ ${fmt(house)}`:fmt(house),mode==='source-skew'?'indicatief · bronmomenten verschillen':'centrale energiebalans');
        setNode(otherNode,mode==='source-skew'?`≈ ${fmt(other)}`:fmt(other),mode==='source-skew'?'incl. niet apart gemeten actieve apparaten':'rest na bekende vermogens');
      }else{
        setNode(houseNode,'—','fysieke balans sluit niet');
        setNode(otherNode,'—','wacht op nieuwe snapshot');
      }
      setBalancePanel(root,mode,house,assigned,other);
      setTopWarning(root,mode);
      root.dataset.balanceStatus=mode;
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
