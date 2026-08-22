(function(){
  'use strict';

  // Initial-page render transaction for Live View.
  // Keep the container hidden while the existing presentation-only layers finish
  // their first pass, then reveal the complete card tree in one paint.
  // This component never reads or writes control state.
  const SETTLE_MS=1250;
  const FAILSAFE_MS=3000;
  let revealed=false,settleTimer=null,failsafeTimer=null;

  function root(){return document.getElementById('live-energy-flow');}

  function reveal(reason){
    if(revealed)return;
    const el=root();
    if(!el)return;
    revealed=true;
    if(settleTimer)clearTimeout(settleTimer);
    if(failsafeTimer)clearTimeout(failsafeTimer);
    el.dataset.atomicReady='true';
    el.dataset.atomicRenderVersion='2.8.123';
    el.dataset.atomicRevealReason=reason;
  }

  function arm(){
    const el=root();
    if(!el||revealed)return;
    el.dataset.atomicReady='false';
    if(settleTimer)clearTimeout(settleTimer);
    settleTimer=setTimeout(()=>reveal('initial-presentation-settled'),SETTLE_MS);
    if(!failsafeTimer)failsafeTimer=setTimeout(()=>reveal('failsafe'),FAILSAFE_MS);
  }

  document.addEventListener('liveenergyrendered',arm);
  document.addEventListener('DOMContentSwitch',()=>{
    revealed=false;
    settleTimer=null;
    failsafeTimer=null;
    arm();
  });

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',()=>{
      const el=root();
      if(el)el.dataset.atomicReady='false';
      failsafeTimer=setTimeout(()=>reveal('failsafe-no-render-event'),FAILSAFE_MS);
    },{once:true});
  }else{
    const el=root();
    if(el)el.dataset.atomicReady='false';
    failsafeTimer=setTimeout(()=>reveal('failsafe-no-render-event'),FAILSAFE_MS);
  }
})();
