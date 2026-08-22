(function(){
  'use strict';

  // v2.8.115: zelfde Live View-geometrie en vaste dunne flowlijnen als v2.8.114,
  // alleen de SVG-pijlpunten zijn vergroot voor betere zichtbaarheid.
  function tuneMarker(marker, direction){
    if(!marker) return;
    marker.setAttribute('markerUnits','strokeWidth');
    marker.setAttribute('markerWidth','5.0');
    marker.setAttribute('markerHeight','5.0');
    marker.setAttribute('viewBox','0 0 6 6');
    marker.setAttribute('refY','3');
    marker.setAttribute('orient','auto');
    marker.setAttribute('overflow','visible');

    const path=marker.querySelector('path');
    if(!path) return;
    if(direction==='start'){
      marker.setAttribute('refX','0.6');
      path.setAttribute('d','M5.4 0.6 L5.4 5.4 L0.6 3 Z');
    }else{
      marker.setAttribute('refX','5.4');
      path.setAttribute('d','M0.6 0.6 L0.6 5.4 L5.4 3 Z');
    }
  }

  function apply(){
    const root=document.getElementById('live-energy-flow');
    if(!root) return;
    tuneMarker(root.querySelector('#arrow-pv'),'end');
    tuneMarker(root.querySelector('#arrow-grid'),'end');
    tuneMarker(root.querySelector('#arrow-battery'),'end');
    tuneMarker(root.querySelector('#arrow-topology-start'),'start');
    tuneMarker(root.querySelector('#arrow-topology-end'),'end');
  }

  let queued=false;
  function scheduleApply(){
    if(queued) return;
    queued=true;
    requestAnimationFrame(()=>{
      queued=false;
      apply();
    });
  }

  document.addEventListener('liveenergyrendered',scheduleApply);
  document.addEventListener('DOMContentLoaded',()=>setTimeout(scheduleApply,250));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(scheduleApply,150));

  const observer=new MutationObserver(scheduleApply);
  function observeRoot(){
    const root=document.getElementById('live-energy-flow');
    if(root){
      observer.disconnect();
      observer.observe(root,{childList:true,subtree:true});
      scheduleApply();
    }
  }
  document.addEventListener('DOMContentLoaded',observeRoot);
  document.addEventListener('DOMContentSwitch',observeRoot);
  setTimeout(observeRoot,900);
})();
