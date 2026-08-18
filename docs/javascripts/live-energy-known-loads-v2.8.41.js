(function(){
  'use strict';
  const n=v=>Number.isFinite(Number(v))?Math.max(0,Number(v)):0;
  const fmt=v=>`${Math.round(v).toLocaleString('nl-NL')} W`;
  function apply(detail){
    const root=document.getElementById('live-energy-flow');
    if(!root||!detail?.raw)return;
    const r=detail.raw,g=r.grid||{},p=r.pv||{},t=r.tesla||{},hw=r.hot_water||{},b=r.battery||{},q=r.quatt||r.heating||r.space_heating||{},loads=r.loads||{};
    const pv=n(p.total_w)||n(p.solaredge_w)+n(p.goodwe_4200_w)+n(p.goodwe_2000_w);
    const grid=Number(g.power_w)||0;
    const batt=Number(b.power_w);
    const charge=Number.isFinite(batt)&&batt>0?batt:0,discharge=Number.isFinite(batt)&&batt<0?Math.abs(batt):0;
    const house=Math.max(0,pv+grid+discharge-charge);
    const known={tesla:n(t.power_w),boiler:n(hw.boiler_power_w),quatt:n(q.power_w??q.quatt_power_w)};
    const applianceNames=['washer','dryer','dishwasher','quooker'];
    let applianceKnownW=0;
    const unmeteredActive=[];
    applianceNames.forEach(k=>{const x=loads[k];if(!x)return;const raw=x.power_w;if(raw!==null&&raw!==undefined&&Number.isFinite(Number(raw)))applianceKnownW+=n(raw);else if(x.active===true)unmeteredActive.push(k);});
    const other=Math.max(0,house-known.tesla-known.boiler-known.quatt-applianceKnownW);
    const nodes=[...root.querySelectorAll('.energy-node')];
    const overig=nodes.find(g=>[...g.querySelectorAll('text')].some(t=>t.textContent==='Overig'));
    if(overig){const texts=overig.querySelectorAll('text');if(texts[2])texts[2].textContent=fmt(other);if(texts[3])texts[3].textContent=unmeteredActive.length?`rest; actief maar niet watt-gemeten: ${unmeteredActive.join(', ')}`:'rest na alle bekende vermogens';}
  }
  document.addEventListener('energycorev2state',e=>setTimeout(()=>apply(e.detail),25));
  document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>{if(window.EnergyCoreV2?.state)apply(window.EnergyCoreV2.state);},500));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(()=>{if(window.EnergyCoreV2?.state)apply(window.EnergyCoreV2.state);},250));
})();
