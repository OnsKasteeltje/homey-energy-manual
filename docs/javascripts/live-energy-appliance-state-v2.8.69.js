(function(){
  'use strict';

  function setPathActive(path, active){
    if(!path) return;
    path.classList.toggle('is-active', !!active);
    path.classList.toggle('is-idle', !active);
    if(active){
      path.style.strokeWidth='3.5';
      path.setAttribute('marker-end','url(#arrow-grid)');
    } else {
      path.removeAttribute('marker-end');
    }
  }

  function patchNode(title, load){
    const root=document.getElementById('live-energy-flow');
    if(!root || !load) return;
    const active=load.active===true;
    const nodes=[...root.querySelectorAll('g.energy-node.load')];
    const node=nodes.find(g=>[...g.querySelectorAll('text.energy-title')].some(t=>t.textContent.trim()===title));
    if(!node) return;

    node.classList.toggle('flow-active',active);
    node.classList.toggle('flow-idle',!active);

    const connector=node.previousElementSibling;
    if(connector?.matches('path.energy-path')) setPathActive(connector,active);

    if(active && (load.power_w===null || load.power_w===undefined || !Number.isFinite(Number(load.power_w)))){
      const value=node.querySelector('text.energy-value');
      const sub=node.querySelector('text.energy-sub');
      if(value) value.textContent='—';
      if(sub) sub.textContent='actief · vermogen niet apart gemeten';
    }
  }

  function apply(detail){
    const raw=detail?.raw || window.EnergyCoreV2?.state?.raw || null;
    const loads=raw?.loads;
    if(!loads) return;
    patchNode('Wasmachine',loads.washer);
    patchNode('Droger',loads.dryer);

    const root=document.getElementById('live-energy-flow');
    if(root && (loads.washer?.active===true || loads.dryer?.active===true)){
      const branch=root.querySelector('path.energy-right-to-washer');
      if(branch){
        branch.classList.add('is-active');
        branch.classList.remove('is-idle');
        branch.style.strokeWidth='3.5';
      }
    }
  }

  document.addEventListener('energycorev2state',e=>setTimeout(()=>apply(e.detail),0));
  document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>apply(),500));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(()=>apply(),250));
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)setTimeout(()=>apply(),100);});
  setInterval(()=>apply(),5000);
})();
