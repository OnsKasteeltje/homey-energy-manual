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

  function confidenceLabel(v){
    const c=String(v||'NONE').toUpperCase();
    if(c==='HIGH') return 'hoge betrouwbaarheid';
    if(c==='MEDIUM') return 'middelmatige betrouwbaarheid';
    if(c==='LOW') return 'lage betrouwbaarheid';
    return 'onvoldoende bewijs';
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

    const value=node.querySelector('text.energy-value');
    const sub=node.querySelector('text.energy-sub');
    const numeric=load.power_w!==null && load.power_w!==undefined && Number.isFinite(Number(load.power_w));

    if(active && !numeric){
      if(value) value.textContent='—';
      if(sub) sub.textContent='actief · vermogen niet apart gemeten';
      node.removeAttribute('data-power-estimated');
      node.removeAttribute('title');
      return;
    }

    if(active && numeric && load.power_estimated===true){
      const watts=Math.round(Number(load.power_w));
      if(value) value.textContent=`${watts.toLocaleString('nl-NL')} W`;
      if(sub) sub.textContent=`geschat · ${confidenceLabel(load.power_confidence)}`;
      node.setAttribute('data-power-estimated','true');
      const phase=load.phase?` · ${load.phase}`:'';
      const evidence=Number(load.evidence_count)||0;
      node.setAttribute('title',`P1-overgangsmodel${phase} · ${evidence} bewijsmetingen`);
      return;
    }

    node.removeAttribute('data-power-estimated');
    node.removeAttribute('title');
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
