(function(){
  // Homepage architecture v1.1: load v1 renderer and override warm-water wording after render.
  const script=document.createElement('script');
  script.src='/homey-energy-manual/javascripts/home-architecture-v1.js';
  script.onload=()=>{
    const improve=()=>{
      document.querySelectorAll('.ha-goal').forEach(goal=>{
        const title=goal.querySelector('strong');
        const state=goal.querySelector('.ha-goal-state');
        const sub=goal.querySelector('small');
        if(title?.textContent.trim()==='Warm water' && state?.textContent.trim()==='Doel vandaag gehaald'){
          state.textContent='Boiler op temperatuur';
          if(sub) sub.textContent='Warmwaterdoel voor vandaag bereikt';
        }
      });
    };
    improve();
    setTimeout(improve,500);
  };
  document.head.appendChild(script);
})();