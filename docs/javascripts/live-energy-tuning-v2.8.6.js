(function(){
  function tuneEnergyFlow(){
    const svg=document.querySelector('#live-energy-flow svg.energy-dashboard');
    if(!svg)return;

    // Houd vermogensafhankelijke lijndikte zichtbaar, maar demp de visuele verschillen.
    svg.querySelectorAll('path.energy-path.is-active').forEach(p=>{
      const raw=parseFloat(p.style.strokeWidth||'3');
      if(Number.isFinite(raw)) p.style.strokeWidth=String(Math.min(5.2,2.4+(Math.max(0,raw-2.4)*0.45)));
    });

    // De vijf laatste grid-paden zijn de individuele verbruikersconnectoren.
    // Wanneer wasmachine/droger alleen via Homey-status ACTIEF bekend zijn,
    // krijgen zij dezelfde visuele dikte als Overig verbruik; er wordt geen wattage geschat.
    const gridPaths=[...svg.querySelectorAll('path.energy-path.energy-grid')];
    const loads=gridPaths.slice(-5);
    if(loads.length===5){
      const other=loads[4];
      const reference=parseFloat(other.style.strokeWidth||'3.2');
      [loads[2],loads[3]].forEach(p=>{
        if(p.classList.contains('is-active')) p.style.strokeWidth=String(reference);
      });
    }

    // Iets compactere pijlpunten voor een rustiger mobiel beeld.
    ['arrow-pv','arrow-grid','arrow-battery'].forEach(id=>{
      const m=svg.querySelector(`#${id}`);
      if(m){m.setAttribute('markerWidth','7');m.setAttribute('markerHeight','7');}
    });
  }

  const root=document.getElementById('live-energy-flow');
  if(!root)return;
  const observer=new MutationObserver(()=>requestAnimationFrame(tuneEnergyFlow));
  observer.observe(root,{childList:true,subtree:true});
  document.addEventListener('DOMContentLoaded',()=>requestAnimationFrame(tuneEnergyFlow));
  document.addEventListener('DOMContentSwitch',()=>requestAnimationFrame(tuneEnergyFlow));
})();
