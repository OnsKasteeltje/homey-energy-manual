(function(){
  // Homepage architecture v1.3: reliably start the base renderer after dynamic loading,
  // then apply current warm-water wording/status corrections.
  const DATA_BASE='/homey-energy-manual/data/';
  const script=document.createElement('script');
  script.src='/homey-energy-manual/javascripts/home-architecture-v1.js';

  async function enhance(){
    // Make OP_TEMPERATUUR wording explicit.
    document.querySelectorAll('.ha-goal').forEach(goal=>{
      const title=goal.querySelector('strong');
      const state=goal.querySelector('.ha-goal-state');
      const sub=goal.querySelector('small');
      if(title?.textContent.trim()==='Warm water' && state?.textContent.trim()==='Doel vandaag gehaald'){
        state.textContent='Boiler op temperatuur';
        if(sub) sub.textContent='Warmwaterdoel voor vandaag bereikt';
      }
    });

    // Use the current warm-water v1.3 flow for the Aansturing status.
    try{
      const r=await fetch(`${DATA_BASE}homey-status.json?ts=${Date.now()}`,{cache:'no-store'});
      if(!r.ok) return;
      const status=await r.json();
      const ww=(status.flows||[]).find(f=>f.name==='Warm water optimalisatie - PV boiler + CV advies v1.3')||{};
      document.querySelectorAll('.ha-stage.control .ha-row').forEach(row=>{
        const spans=row.querySelectorAll(':scope > span');
        if(spans.length<2 || spans[0].textContent.trim()!=='Boiler') return;
        spans[1].innerHTML=ww.enabled
          ? 'via warmwater · actief <span class="dot ok"></span>'
          : 'regeling uit <span class="dot off"></span>';
      });
    }catch(_e){}
  }

  script.onload=()=>{
    // The base script was loaded after DOMContentLoaded; trigger its supported rerender event explicitly.
    document.dispatchEvent(new Event('DOMContentSwitch'));
    setTimeout(enhance,100);
    setTimeout(enhance,700);
  };
  script.onerror=()=>{
    const root=document.getElementById('home-architecture');
    if(root) root.innerHTML='<div class="ha-shell"><div class="ha-health"><strong>Architectuuroverzicht kon niet worden geladen</strong><span>Basisrenderer ontbreekt.</span></div></div>';
  };
  document.head.appendChild(script);
})();
