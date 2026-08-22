(function(){
  'use strict';

  function tuneMarker(marker, direction){
    if(!marker) return;
    marker.setAttribute('markerUnits','userSpaceOnUse');
    marker.setAttribute('markerWidth','10');
    marker.setAttribute('markerHeight','10');
    marker.setAttribute('viewBox','0 0 10 10');
    marker.setAttribute('refY','5');
    const path=marker.querySelector('path');
    if(!path) return;
    if(direction==='start'){
      marker.setAttribute('refX','1');
      path.setAttribute('d','M9 1 L9 9 L1 5 Z');
    }else{
      marker.setAttribute('refX','9');
      path.setAttribute('d','M1 1 L1 9 L9 5 Z');
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

  document.addEventListener('liveenergyrendered',apply);
  document.addEventListener('DOMContentLoaded',()=>setTimeout(apply,250));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(apply,150));
  setTimeout(apply,1000);
})();
