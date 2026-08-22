(function(){
  'use strict';

  // v2.8.116: pijlgeometrie wordt direct in dezelfde render-cyclus toegepast.
  // Geen requestAnimationFrame, timeouts of MutationObserver meer: voorkomt zichtbare post-render repaint.
  function tuneMarker(marker,direction){
    if(!marker)return;
    marker.setAttribute('markerUnits','strokeWidth');
    marker.setAttribute('markerWidth','5.0');
    marker.setAttribute('markerHeight','5.0');
    marker.setAttribute('viewBox','0 0 6 6');
    marker.setAttribute('refY','3');
    marker.setAttribute('orient','auto');
    marker.setAttribute('overflow','visible');
    const path=marker.querySelector('path');
    if(!path)return;
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
    if(!root)return;
    tuneMarker(root.querySelector('#arrow-pv'),'end');
    tuneMarker(root.querySelector('#arrow-grid'),'end');
    tuneMarker(root.querySelector('#arrow-battery'),'end');
    tuneMarker(root.querySelector('#arrow-topology-start'),'start');
    tuneMarker(root.querySelector('#arrow-topology-end'),'end');
    root.dataset.arrowGeometryVersion='2.8.116';
  }

  // De renderer vuurt dit event direct na het plaatsen van de SVG af. Pas geometrie synchroon toe,
  // zodat de browser maar één visuele frame hoeft te schilderen.
  document.addEventListener('liveenergyrendered',apply);
  document.addEventListener('DOMContentSwitch',apply);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',apply,{once:true});
  else apply();
})();
