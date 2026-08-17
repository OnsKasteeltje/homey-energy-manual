(function(){
  'use strict';
  function fmtAge(ms){
    if(ms==null||!Number.isFinite(ms)) return 'onbekend';
    const m=Math.max(0,Math.round(ms/60000));
    return m<1?'<1 min':`${m} min`;
  }
  function render(detail){
    const old=document.getElementById('em-v2-health');
    if(!detail){
      if(old) old.innerHTML='<strong>EM v2: GEEN DATA</strong> · wacht op Energy Core v2-state';
      return;
    }
    const raw=detail.raw||{};
    const meta=raw.meta||{};
    const status=!detail.heartbeatFresh?'OFFLINE':(!detail.stateFresh?'STALE':'LIVE');
    const text=`<strong>EM v2: ${status}</strong> · state ${fmtAge(detail.stateAgeMs)} oud · heartbeat ${fmtAge(detail.heartbeatAgeMs)} oud · revision ${meta.state_revision??'?'} · ${detail.controlMode||'UNKNOWN'}`;
    if(old){old.innerHTML=text;return;}
    const host=document.querySelector('.md-content__inner')||document.querySelector('main');
    if(!host)return;
    const box=document.createElement('div');
    box.id='em-v2-health';
    box.className='admonition info';
    box.style.marginBottom='1rem';
    box.innerHTML=text;
    host.insertBefore(box,host.firstChild);
  }
  document.addEventListener('energycorev2state',e=>render(e.detail));
  document.addEventListener('DOMContentLoaded',()=>{
    setTimeout(()=>render(window.EnergyCoreV2?.state||null),1000);
  });
  document.addEventListener('DOMContentSwitch',()=>{
    setTimeout(()=>render(window.EnergyCoreV2?.state||null),100);
  });
})();
