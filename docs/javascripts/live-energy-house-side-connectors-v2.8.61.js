(function(){
  'use strict';
  function alignHouseSideConnectors(){
    const svg=document.querySelector('#live-energy-flow svg.energy-dashboard.concept-layout');
    if(!svg)return;
    const paths=[...svg.querySelectorAll('path.energy-path')];
    paths.forEach(p=>{
      const d=p.getAttribute('d')||'';
      // PV ↔ Huis: laatste traject horizontaal op de linker zijkant van Huis.
      if(d==='M270 180 V245 H570 V347') p.setAttribute('d','M270 180 V347 H570');
      // Net → Huis: laatste traject horizontaal op de rechter zijkant van Huis.
      if(d==='M1230 180 V245 H930 V347') p.setAttribute('d','M1230 180 V347 H930');
      // Huis → Net heeft al een horizontaal eerste traject vanaf de rechter zijkant;
      // dezelfde geometrie blijft behouden zodat de richting bij export correct is.
    });
  }
  const schedule=()=>setTimeout(alignHouseSideConnectors,0);
  document.addEventListener('energycorev2state',schedule);
  document.addEventListener('DOMContentLoaded',()=>setTimeout(alignHouseSideConnectors,250));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(alignHouseSideConnectors,120));
  setTimeout(alignHouseSideConnectors,900);
})();
