(function(){
  // Homepage architecture v1.2: load base renderer, then correct warm-water wording and active-flow status.
  const BASE='/homey-energy-manual/data/';
  const script=document.createElement('script');
  script.src='/homey-energy-manual/javascripts/home-architecture-v1.js';

  async function enhance(){
    // 1) Make OP_TEMPERATUUR wording explicit.
    document.querySelectorAll('.ha-goal').forEach(goal=>{
      const title=goal.querySelector('strong');
      const state=goal.querySelector('.ha-goal-state');
      const sub=goal.querySelector('small');
      if(title?.textContent.trim()==='Warm water' && state?.textContent.trim()==='Doel vandaag gehaald'){
        state.textContent='Boiler op temperatuur';
        if(sub) sub.textContent='Warmwaterdoel voor vandaag bereikt';
      }
    });

    // 2) Use the current warm-water flow status for Aansturing, not the retired night-test flow.
    try{
      const r=await fetch(`${BASE}homey-status.json?ts=${Date.now()}`,{cache:'no-store'});
      if(!r.ok) return;
      const status=await r.json();
      const ww=(status.flows||[]).find(f=>f.name==='Warm water optimalisatie - PV boiler + CV advies v1.3')||{};
      document.querySelectorAll('.ha-stage.control .ha-row').forEach(row=>{
        const label=row.querySelector('span:first-child');
        if(label?.textContent.trim()!=='Boiler') return;
        const value=row.querySelector('span:last-child');
        if(!value) return;
        value.innerHTML=ww.enabled
          ? 'via warmwater · actief <span class="dot ok"></span>'
          : 'regeling uit <span class="dot off"></span>';
      });
    }catch(_e){}
  }

  script.onload=()=>{
    enhance();
    setTimeout(enhance,500);
    setTimeout(enhance,1500);
  };
  document.head.appendChild(script);
})();