(function(){
  'use strict';
  const THRESHOLD_W=20;
  const n=v=>Number.isFinite(Number(v))?Math.max(0,Number(v)):0;
  const activeW=v=>n(v)>THRESHOLD_W?n(v):0;
  const width=w=>activeW(w)>0?Math.max(3.5,Math.min(8.5,3+activeW(w)/850)):2;

  const TITLES=['Tesla','Boiler','Ruimteverwarming','Wasmachine','Droger','Quooker','Overig'];
  const CENTERS={Tesla:120,Boiler:325,Ruimteverwarming:530,Wasmachine:735,Droger:940,Quooker:1145,Overig:1350};
  const HUB_X=750,BUS_Y=505;

  function nodePower(root,title){
    const node=[...root.querySelectorAll('g.energy-node')].find(g=>g.querySelector('text.energy-title')?.textContent?.trim()===title);
    const text=node?.querySelector('text.energy-value')?.textContent||'';
    const m=text.replace(/\./g,'').replace(',','.').match(/-?\d+(?:\.\d+)?/);
    return m?n(m[0]):0;
  }

  function setPath(path,w){
    if(!path) return;
    const on=activeW(w)>0;
    path.classList.toggle('is-active',on);
    path.classList.toggle('is-idle',!on);
    path.classList.toggle('energy-active',on);
    path.classList.toggle('energy-idle',!on);
    path.style.strokeWidth=String(width(w));
    path.style.opacity=on?'.98':'.36';
  }

  function apply(){
    const root=document.getElementById('live-energy-flow');
    if(!root) return;
    const svg=root.querySelector('svg.energy-dashboard.concept-layout');
    if(!svg) return;

    const powers=Object.fromEntries(TITLES.map(t=>[t,activeW(nodePower(root,t))]));
    const total=TITLES.reduce((sum,t)=>sum+powers[t],0);
    setPath(svg.querySelector('path.energy-feed'),total);

    const left=['Wasmachine','Ruimteverwarming','Boiler','Tesla'];
    let remaining=left.reduce((sum,t)=>sum+powers[t],0);
    left.forEach((title,index)=>{
      setPath(svg.querySelector(`path.energy-left-segment-${index}`),remaining);
      remaining-=powers[title];
    });

    const right=['Droger','Quooker','Overig'];
    remaining=right.reduce((sum,t)=>sum+powers[t],0);
    right.forEach((title,index)=>{
      setPath(svg.querySelector(`path.energy-right-segment-${index}`),remaining);
      remaining-=powers[title];
    });

    TITLES.forEach(title=>{
      const cx=CENTERS[title];
      const branch=[...svg.querySelectorAll('path.energy-path.energy-grid')].find(p=>p.getAttribute('d')===`M${cx} ${BUS_Y} V570`);
      setPath(branch,powers[title]);
    });

    root.dataset.consumptionBusSync='2.8.82';
  }

  const later=()=>{setTimeout(apply,60);setTimeout(apply,220);};
  document.addEventListener('energycorev2state',later);
  document.addEventListener('DOMContentLoaded',later);
  document.addEventListener('DOMContentSwitch',later);
  document.addEventListener('appdatarefresh',later);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)later();});
  setInterval(apply,2000);
})();
