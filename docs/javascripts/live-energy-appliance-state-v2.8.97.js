(function(){
  'use strict';

  const ACTIVE_THRESHOLD_W=20;

  function setPathActive(path,active){
    if(!path)return;
    path.classList.toggle('is-active',!!active);
    path.classList.toggle('is-idle',!active);
    if(active){path.style.strokeWidth='3.5';path.setAttribute('marker-end','url(#arrow-grid)');}
    else{path.style.strokeWidth='2';path.removeAttribute('marker-end');}
  }

  function confidenceLabel(v){
    const c=String(v||'NONE').toUpperCase();
    if(c==='HIGH')return 'hoge betrouwbaarheid';
    if(c==='MEDIUM')return 'middelmatige betrouwbaarheid';
    if(c==='LOW')return 'lage betrouwbaarheid';
    return 'onvoldoende bewijs';
  }

  function findNode(title){
    const root=document.getElementById('live-energy-flow');
    if(!root)return null;
    return [...root.querySelectorAll('g.energy-node.load')].find(g=>[...g.querySelectorAll('text.energy-title')].some(t=>t.textContent.trim()===title))||null;
  }

  function patchNode(title,load){
    const node=findNode(title);
    if(!node||!load)return;

    const stateActive=load.active===true;
    const numeric=load.power_w!==null&&load.power_w!==undefined&&Number.isFinite(Number(load.power_w));
    const watts=numeric?Math.max(0,Number(load.power_w)):null;
    const electricalActive=numeric&&watts>ACTIVE_THRESHOLD_W;

    // Electrical activity alone controls orange icon and active flow. Device state is descriptive only.
    node.classList.toggle('flow-active',electricalActive);
    node.classList.toggle('flow-idle',!electricalActive);
    const connector=node.previousElementSibling;
    if(connector?.matches('path.energy-path'))setPathActive(connector,electricalActive);

    const value=node.querySelector('text.energy-value');
    const sub=node.querySelector('text.energy-sub');

    if(!numeric){
      if(value)value.textContent=stateActive?'—':'0 W';
      if(sub)sub.textContent=stateActive?'draait · vermogen niet apart gemeten':'niet actief';
      node.removeAttribute('data-power-estimated');
      node.removeAttribute('title');
      return;
    }

    const displayWatts=Math.round(watts).toLocaleString('nl-NL');
    if(load.power_estimated===true){
      if(value)value.textContent=`~${displayWatts} W`;
      if(sub){
        if(electricalActive)sub.textContent=`geschat actief · ${confidenceLabel(load.power_confidence)}`;
        else if(stateActive)sub.textContent=`draait · geschat ≤ ${ACTIVE_THRESHOLD_W} W`;
        else sub.textContent='niet actief';
      }
      node.setAttribute('data-power-estimated','true');
      const phase=load.phase?` · ${load.phase}`:'';
      const evidence=Number(load.evidence_count)||0;
      node.setAttribute('title',`P1-overgangsmodel${phase} · ${evidence} bewijsmetingen`);
      return;
    }

    if(value)value.textContent=`${displayWatts} W`;
    if(sub){
      if(electricalActive&&stateActive)sub.textContent='actief';
      else if(electricalActive&&!stateActive)sub.textContent='verbruik gemeten · apparaatstatus niet actief';
      else if(stateActive)sub.textContent=`draait · laag elektrisch verbruik (≤ ${ACTIVE_THRESHOLD_W} W)`;
      else sub.textContent='niet actief';
    }
    node.removeAttribute('data-power-estimated');
    node.removeAttribute('title');
  }

  function apply(detail){
    const raw=detail?.raw||window.EnergyCoreV2?.state?.raw||null;
    const loads=raw?.loads;
    const root=document.getElementById('live-energy-flow');
    if(!loads||!root)return;
    patchNode('Wasmachine',loads.washer);
    patchNode('Droger',loads.dryer);
  }

  document.addEventListener('energycorev2state',e=>setTimeout(()=>apply(e.detail),0));
  document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>apply(),500));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(()=>apply(),250));
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)setTimeout(()=>apply(),100);});
  setInterval(()=>apply(),5000);
})();
