(function(){
  'use strict';
  let latestRaw=null,observer=null,scheduled=false;

  function apply(){
    scheduled=false;
    const root=document.getElementById('live-energy-flow');
    const svg=root?.querySelector('svg.energy-dashboard.concept-layout');
    const r=latestRaw||window.EnergyCoreV2?.state?.raw;
    if(!root||!svg||!r)return;

    const b=r.battery||{};
    const integrated=b.integrated===true;
    const batteryNode=[...svg.querySelectorAll('.energy-node.battery')][0];
    if(batteryNode){
      const value=batteryNode.querySelector('.energy-value');
      const sub=batteryNode.querySelector('.energy-sub');
      if(!integrated){
        if(value)value.textContent='0 W';
        if(sub)sub.textContent='nog niet aangesloten';
        batteryNode.classList.add('battery-not-integrated');
      }else{
        batteryNode.classList.remove('battery-not-integrated');
      }
    }

    const paths=[...svg.querySelectorAll('path.energy-path')];
    const byD=d=>paths.filter(p=>(p.getAttribute('d')||'')===d);
    const batteryRelated=[
      ...byD('M450 118 H570'),
      ...byD('M750 180 V285'),
      ...byD('M750 285 V180')
    ];
    batteryRelated.forEach(p=>{
      if(!integrated){
        p.classList.remove('is-active');
        p.classList.add('is-idle','battery-disconnected-path');
        p.style.strokeWidth='2';
        p.removeAttribute('marker-end');
        p.style.opacity='0.22';
      }else{
        p.classList.remove('battery-disconnected-path');
        p.style.removeProperty('opacity');
      }
    });

    const topo=svg.querySelector('.energy-grid-battery-link');
    const topoLabel=svg.querySelector('.energy-topology-label');
    if(topo){
      topo.classList.toggle('battery-not-integrated-topology',!integrated);
      if(!integrated){
        topo.removeAttribute('marker-start');
        topo.removeAttribute('marker-end');
      }
    }
    if(topoLabel&&!integrated)topoLabel.textContent='AC-bus · toekomstig';
    root.dataset.batteryIntegrated=String(integrated);
  }

  function schedule(){if(scheduled)return;scheduled=true;requestAnimationFrame(apply);}
  function attach(){
    const root=document.getElementById('live-energy-flow');
    if(!root)return;
    if(observer)observer.disconnect();
    observer=new MutationObserver(schedule);
    observer.observe(root,{childList:true,subtree:true});
    schedule();
  }

  document.addEventListener('energycorev2state',e=>{latestRaw=e.detail?.raw||latestRaw;schedule();});
  document.addEventListener('DOMContentLoaded',()=>setTimeout(attach,250));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(attach,120));
  setTimeout(attach,900);
})();
