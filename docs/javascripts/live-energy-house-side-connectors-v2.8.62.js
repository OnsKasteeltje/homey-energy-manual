(function(){
  'use strict';
  let observer=null;
  let scheduled=false;

  function applyHouseSideGeometry(){
    const root=document.getElementById('live-energy-flow');
    const svg=root?.querySelector('svg.energy-dashboard.concept-layout');
    if(!svg)return;

    const paths=[...svg.querySelectorAll('path.energy-path')];
    for(const p of paths){
      const d=p.getAttribute('d')||'';

      // PV -> Huis: verticale aanvoer links, laatste segment horizontaal in linkerzijde Huis.
      if(d==='M270 180 V245 H570 V347' || d==='M270 180 V347 H570'){
        p.setAttribute('d','M270 180 V347 H570');
      }

      // Net -> Huis: verticale aanvoer rechts, laatste segment horizontaal in rechterzijde Huis.
      if(d==='M1230 180 V245 H930 V347' || d==='M1230 180 V347 H930'){
        p.setAttribute('d','M1230 180 V347 H930');
      }

      // Huis -> Net: begin horizontaal uit rechterzijde Huis, daarna pas omhoog naar Net.
      if(d==='M930 347 H1230 V180'){
        p.setAttribute('d','M930 347 H1230 V180');
      }
    }
  }

  function schedule(){
    if(scheduled)return;
    scheduled=true;
    requestAnimationFrame(()=>{
      scheduled=false;
      applyHouseSideGeometry();
    });
  }

  function attach(){
    const root=document.getElementById('live-energy-flow');
    if(!root)return;
    observer?.disconnect();
    observer=new MutationObserver(schedule);
    observer.observe(root,{childList:true,subtree:true});
    schedule();
  }

  document.addEventListener('energycorev2state',schedule);
  document.addEventListener('DOMContentLoaded',()=>setTimeout(attach,100));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(attach,50));
  setTimeout(attach,700);
})();
