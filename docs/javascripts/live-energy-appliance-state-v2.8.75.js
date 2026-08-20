(function(){
  'use strict';

  function setPathActive(path, active){
    if(!path) return;
    path.classList.toggle('is-active', !!active);
    path.classList.toggle('is-idle', !active);
    if(active){ path.style.strokeWidth='3.5'; path.setAttribute('marker-end','url(#arrow-grid)'); }
    else { path.style.strokeWidth='2'; path.removeAttribute('marker-end'); }
  }

  function setBusNeutral(path){
    if(!path) return;
    path.classList.remove('is-active'); path.classList.add('is-idle');
    path.style.strokeWidth='2'; path.removeAttribute('marker-end');
  }

  function confidenceLabel(v){
    const c=String(v||'NONE').toUpperCase();
    if(c==='HIGH') return 'hoge betrouwbaarheid';
    if(c==='MEDIUM') return 'middelmatige betrouwbaarheid';
    if(c==='LOW') return 'lage betrouwbaarheid';
    return 'onvoldoende bewijs';
  }

  function findNode(title){
    const root=document.getElementById('live-energy-flow');
    if(!root) return null;
    return [...root.querySelectorAll('g.energy-node.load')].find(g=>[...g.querySelectorAll('text.energy-title')].some(t=>t.textContent.trim()===title))||null;
  }

  function patchNode(title, load){
    const node=findNode(title);
    if(!node || !load) return;
    const active=load.active===true;
    node.classList.toggle('flow-active',active); node.classList.toggle('flow-idle',!active);
    const connector=node.previousElementSibling;
    if(connector?.matches('path.energy-path')) setPathActive(connector,active);
    const value=node.querySelector('text.energy-value');
    const sub=node.querySelector('text.energy-sub');
    const numeric=load.power_w!==null && load.power_w!==undefined && Number.isFinite(Number(load.power_w));

    if(!active){
      // Een betrouwbaar inactief apparaat wordt in de live UI consequent als 0 W weergegeven.
      // Dit voorkomt dat de 5-seconden state-patch de aparte inactive-zero normalisatie overschrijft.
      if(value) value.textContent='0 W';
      if(sub) sub.textContent='niet actief';
      node.removeAttribute('data-power-estimated'); node.removeAttribute('title');
      return;
    }

    if(!numeric){
      if(value) value.textContent='—';
      if(sub) sub.textContent='actief · vermogen niet apart gemeten';
      node.removeAttribute('data-power-estimated'); node.removeAttribute('title');
      return;
    }

    if(load.power_estimated===true){
      const watts=Math.round(Number(load.power_w));
      if(value) value.textContent=`~${watts.toLocaleString('nl-NL')} W`;
      if(sub) sub.textContent=`geschat · ${confidenceLabel(load.power_confidence)}`;
      node.setAttribute('data-power-estimated','true');
      const phase=load.phase?` · ${load.phase}`:'';
      const evidence=Number(load.evidence_count)||0;
      node.setAttribute('title',`P1-overgangsmodel${phase} · ${evidence} bewijsmetingen`);
      return;
    }

    if(value) value.textContent=`${Math.round(Number(load.power_w)).toLocaleString('nl-NL')} W`;
    if(sub) sub.textContent='actief';
    node.removeAttribute('data-power-estimated'); node.removeAttribute('title');
  }

  function apply(detail){
    const raw=detail?.raw || window.EnergyCoreV2?.state?.raw || null;
    const loads=raw?.loads;
    const root=document.getElementById('live-energy-flow');
    if(!loads || !root) return;
    patchNode('Wasmachine',loads.washer); patchNode('Droger',loads.dryer);
    setBusNeutral(root.querySelector('path.energy-right-to-washer'));
    setBusNeutral(root.querySelector('path.energy-washer-to-dryer'));
    setBusNeutral(root.querySelector('path.energy-dryer-to-other'));
  }

  document.addEventListener('energycorev2state',e=>setTimeout(()=>apply(e.detail),0));
  document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>apply(),500));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(()=>apply(),250));
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)setTimeout(()=>apply(),100);});
  setInterval(()=>apply(),5000);
})();
