(function(){
  'use strict';
  const SVG_NS='http://www.w3.org/2000/svg';
  const ACTIVE_THRESHOLD_W=20;
  const n=v=>Number.isFinite(Number(v))?Math.max(0,Number(v)):0;
  const activePower=w=>n(w)>ACTIVE_THRESHOLD_W?n(w):0;
  const width=w=>w>0?Math.max(3.5,Math.min(8.5,3+w/850)):2.0;
  let latestRaw=null,observer=null,scheduled=false;

  function knownPower(load){
    return load&&load.power_w!==null&&load.power_w!==undefined&&Number.isFinite(Number(load.power_w))?n(load.power_w):0;
  }
  function segment(svg,d,w,cls){
    const p=document.createElementNS(SVG_NS,'path');
    p.setAttribute('d',d);
    p.setAttribute('class',`energy-consumption-segment energy-${w>0?'active':'idle'} ${cls}`);
    p.style.strokeWidth=String(width(w));
    svg.appendChild(p);
  }
  function setBranch(svg,x,w){
    const d=`M${x} 505 V570`;
    const p=[...svg.querySelectorAll('path.energy-path.energy-grid')].find(el=>(el.getAttribute('d')||'')===d);
    if(!p)return;
    const active=w>0;
    p.classList.toggle('is-active',active);
    p.classList.toggle('is-idle',!active);
    p.style.strokeWidth=String(width(w));
    if(active) p.setAttribute('marker-end','url(#arrow-grid)');
    else p.removeAttribute('marker-end');
  }
  function apply(){
    scheduled=false;
    const root=document.getElementById('live-energy-flow');
    const svg=root?.querySelector('svg.energy-dashboard.concept-layout');
    const r=latestRaw||window.EnergyCoreV2?.state?.raw;
    if(!root||!svg||!r)return;

    svg.querySelectorAll('.energy-consumption-segment').forEach(el=>el.remove());

    const teslaRaw=n(r.tesla?.power_w);
    const boilerRaw=n(r.hot_water?.boiler_power_w);
    const heat=r.quatt||r.heating||{};
    const quattRaw=n(heat.power_w??heat.quatt_power_w);
    const washerRaw=knownPower(r.loads?.washer);
    const dryerRaw=knownPower(r.loads?.dryer);
    const extrasRaw=knownPower(r.loads?.dishwasher)+knownPower(r.loads?.quooker);
    const house=Number.isFinite(Number(r.energy_budget?.house_load_w))?n(r.energy_budget.house_load_w):0;
    const otherRaw=Math.max(0,house-teslaRaw-boilerRaw-quattRaw-washerRaw-dryerRaw-extrasRaw);

    const tesla=activePower(teslaRaw);
    const boiler=activePower(boilerRaw);
    const quatt=activePower(quattRaw);
    const washer=activePower(washerRaw);
    const dryer=activePower(dryerRaw);
    const other=activePower(otherRaw);

    const leftHeat=tesla+boiler+quatt;
    const leftBoiler=tesla+boiler;
    const leftTesla=tesla;
    const rightWasher=washer+dryer+other;
    const rightDryer=dryer+other;
    const rightOther=other;
    const total=leftHeat+rightWasher;

    segment(svg,'M750 410 V505',total,'energy-feed');
    segment(svg,'M750 505 H630',leftHeat,'energy-left-to-heating');
    segment(svg,'M630 505 H390',leftBoiler,'energy-heating-to-boiler');
    segment(svg,'M390 505 H150',leftTesla,'energy-boiler-to-tesla');
    segment(svg,'M750 505 H870',rightWasher,'energy-right-to-washer');
    segment(svg,'M870 505 H1110',rightDryer,'energy-washer-to-dryer');
    segment(svg,'M1110 505 H1350',rightOther,'energy-dryer-to-other');

    setBranch(svg,150,tesla);
    setBranch(svg,390,boiler);
    setBranch(svg,630,quatt);
    setBranch(svg,870,washer);
    setBranch(svg,1110,dryer);
    setBranch(svg,1350,other);

    root.dataset.activeConsumptionThresholdW=String(ACTIVE_THRESHOLD_W);
  }
  function schedule(){if(scheduled)return;scheduled=true;requestAnimationFrame(apply);}
  function attach(){
    const root=document.getElementById('live-energy-flow');
    if(!root)return;
    if(observer)observer.disconnect();
    observer=new MutationObserver(schedule);
    observer.observe(root,{childList:true,subtree:true});
    schedule();
  }
  document.addEventListener('energycorev2state',e=>{latestRaw=e.detail?.raw||latestRaw;schedule();});
  document.addEventListener('DOMContentLoaded',()=>setTimeout(attach,250));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(attach,120));
  setTimeout(attach,900);
})();
