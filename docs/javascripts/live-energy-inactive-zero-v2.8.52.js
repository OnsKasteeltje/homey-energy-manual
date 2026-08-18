(function(){
  'use strict';
  function normalizeInactiveLoads(){
    const root=document.getElementById('live-energy-flow');
    if(!root)return;
    root.querySelectorAll('.energy-node').forEach(node=>{
      const title=node.querySelector('.energy-title')?.textContent?.trim();
      const sub=node.querySelector('.energy-sub')?.textContent?.trim();
      const value=node.querySelector('.energy-value');
      if((title==='Wasmachine'||title==='Droger')&&sub==='niet actief'&&value&&value.textContent.trim()==='—') value.textContent='0 W';
    });
  }
  document.addEventListener('energycorev2state',()=>setTimeout(normalizeInactiveLoads,0));
  document.addEventListener('DOMContentLoaded',()=>{setTimeout(normalizeInactiveLoads,250);setTimeout(normalizeInactiveLoads,900);});
  document.addEventListener('DOMContentSwitch',()=>setTimeout(normalizeInactiveLoads,150));
})();
