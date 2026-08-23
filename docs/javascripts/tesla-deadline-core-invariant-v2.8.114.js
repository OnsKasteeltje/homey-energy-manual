(function(){
  'use strict';
  // Hard invariant: once Energy Core says the deadline is inactive, stale command/pending
  // data may never keep the deadline form visually active.
  window.HomeEnergyFrontend=window.HomeEnergyFrontend||{};
  window.HomeEnergyFrontend.teslaDeadlineCoreInvariant='2.8.114';

  let latestTesla=null;
  let timer=null;

  const native=()=>document.querySelector('[data-tesla-deadline-native]');
  const terminal=t=>{
    if(!t||typeof t.deadline_active!=='boolean')return false;
    if(t.deadline_active===true)return false;
    const remaining=Math.max(0,Number(t.remaining_kwh)||0);
    const status=String(t.deadline_status||t.lifecycle_status||'').toUpperCase();
    return remaining<=0.01 || status==='DEADLINE_REACHED' || status==='DOEL_GEHAALD_NA_DEADLINE' || status.startsWith('OPPORTUNITY_');
  };

  function enforce(){
    if(!terminal(latestTesla))return false;
    const wrap=native();if(!wrap)return false;
    const off=wrap.querySelector('input[name="tesla-native-mode"][value="off"]');
    const on=wrap.querySelector('input[name="tesla-native-mode"][value="on"]');
    const fields=wrap.querySelector('.tesla-inline-fields');
    if(off)off.checked=true;
    if(on)on.checked=false;
    if(fields)fields.hidden=true;
    wrap.dataset.coreDeadlineTerminal='true';
    return true;
  }

  function refreshFrom(detail){
    const t=detail?.raw?.tesla||detail?.tesla||null;
    if(t)latestTesla=t;
    setTimeout(enforce,0);
    setTimeout(enforce,100);
    setTimeout(enforce,500);
  }

  document.addEventListener('energycorev2state',e=>refreshFrom(e.detail));
  document.addEventListener('liveenergyrendered',()=>enforce());
  document.addEventListener('appdatarefresh',()=>enforce());
  document.addEventListener('DOMContentSwitch',()=>enforce());
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')enforce();});
  document.addEventListener('DOMContentLoaded',()=>refreshFrom(window.EnergyCoreV2?.state||null));
  if(document.readyState!=='loading')refreshFrom(window.EnergyCoreV2?.state||null);
  timer=setInterval(()=>{if(document.visibilityState==='visible')enforce();},1000);
  window.addEventListener('beforeunload',()=>clearInterval(timer),{once:true});
})();
