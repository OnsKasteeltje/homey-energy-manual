(function(){
  'use strict';
  const n=v=>Number.isFinite(Number(v))?Math.max(0,Number(v)):0;
  const width=w=>w>0?Math.max(3.5,Math.min(8.5,3+w/850)):2.2;
  let latestRaw=null;
  function addSegment(svg,d,w,extra=''){
    const p=document.createElementNS('http://www.w3.org/2000/svg','path');
    p.setAttribute('d',d);
    p.setAttribute('class',`energy-consumption-segment energy-path energy-grid ${w>0?'is-active':'is-idle'} ${extra}`);
    p.style.strokeWidth=String(width(w));
    p.style.fill='none';
    p.style.strokeLinecap='square';
    p.style.strokeLinejoin='miter';
    svg.appendChild(p);
  }
  function knownPower(load){
    return load&&load.power_w!==null&&load.power_w!==undefined&&Number.isFinite(Number(load.power_w))?n(load.power_w):0;
  }
  function apply(){
    const root=document.getElementById('live-energy-flow');
    const svg=root?.querySelector('svg.energy-dashboard.concept-layout');
    const r=latestRaw||window.EnergyCoreV2?.state?.raw;
    if(!root||!svg||!r)return;
    svg.querySelectorAll('.energy-consumption-segment').forEach(el=>el.remove());
    [...svg.querySelectorAll('.energy-consumption-bus')].forEach(el=>el.style.display='none');
    const t=n(r.tesla?.power_w);
    const boiler=n(r.hot_water?.boiler_power_w);
    const heat=r.quatt||r.heating||{};
    const q=n(heat.power_w??heat.quatt_power_w);
    const washer=knownPower(r.loads?.washer);
    const dryer=knownPower(r.loads?.dryer);
    const extras=knownPower(r.loads?.dishwasher)+knownPower(r.loads?.quooker);
    const eb=r.energy_budget||{};
    const house=Number.isFinite(Number(eb.house_load_w))?n(eb.house_load_w):0;
    const other=Math.max(0,house-t-boiler-q-washer-dryer-extras);
    const left1=t+boiler+q;
    const left2=t+boiler;
    const left3=t;
    const right1=washer+dryer+other;
    const right2=dryer+other;
    const right3=other;
    const total=left1+right1;
    addSegment(svg,'M750 410 V505',total,'energy-consumption-feed');
    addSegment(svg,'M750 505 H630',left1,'energy-consumption-left-1');
    addSegment(svg,'M630 505 H390',left2,'energy-consumption-left-2');
    addSegment(svg,'M390 505 H150',left3,'energy-consumption-left-3');
    addSegment(svg,'M750 505 H870',right1,'energy-consumption-right-1');
    addSegment(svg,'M870 505 H1110',right2,'energy-consumption-right-2');
    addSegment(svg,'M1110 505 H1350',right3,'energy-consumption-right-3');
  }
  const schedule=()=>setTimeout(apply,20);
  document.addEventListener('energycorev2state',e=>{latestRaw=e.detail?.raw||latestRaw;schedule();});
  document.addEventListener('DOMContentLoaded',()=>{setTimeout(apply,300);setTimeout(apply,1000);});
  document.addEventListener('DOMContentSwitch',()=>setTimeout(apply,180));
})();
