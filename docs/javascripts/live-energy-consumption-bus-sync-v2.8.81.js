(function(){
  'use strict';
  const THRESHOLD_W=20;
  const n=v=>Number.isFinite(Number(v))?Math.max(0,Number(v)):0;
  const width=w=>w>THRESHOLD_W?Math.max(3.5,Math.min(8.5,3+w/850)):2;

  function nodePower(title){
    const root=document.getElementById('live-energy-flow');
    if(!root) return 0;
    const node=[...root.querySelectorAll('g.energy-node')].find(g=>g.querySelector('text.energy-title')?.textContent?.trim()===title);
    const text=node?.querySelector('text.energy-value')?.textContent||'';
    const m=text.replace(/\./g,'').replace(',','.').match(/-?\d+(?:\.\d+)?/);
    return m?n(m[0]):0;
  }

  function setSegment(root,cls,w){
    const p=root.querySelector(`path.${cls}`);
    if(!p) return;
    const on=w>THRESHOLD_W;
    // Normaliseer beide klassenschema's die in oudere en nieuwere renderers voorkomen.
    p.classList.toggle('is-active',on);
    p.classList.toggle('is-idle',!on);
    p.classList.toggle('energy-active',on);
    p.classList.toggle('energy-idle',!on);
    p.style.strokeWidth=String(width(w));
    p.style.opacity=on?'.98':'.36';
  }

  function apply(){
    const root=document.getElementById('live-energy-flow');
    if(!root) return;
    const washer=nodePower('Wasmachine');
    const dryer=nodePower('Droger');
    const other=nodePower('Overig');
    setSegment(root,'energy-dryer-to-other',other);
    setSegment(root,'energy-washer-to-dryer',dryer+other);
    setSegment(root,'energy-right-to-washer',washer+dryer+other);
  }

  const later=()=>{setTimeout(apply,80);setTimeout(apply,350);};
  document.addEventListener('energycorev2state',later);
  document.addEventListener('DOMContentLoaded',later);
  document.addEventListener('DOMContentSwitch',later);
  document.addEventListener('appdatarefresh',later);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)later();});
  setInterval(apply,2000);
})();
