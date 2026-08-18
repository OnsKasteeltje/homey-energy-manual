(function(){
  'use strict';
  // Cache-busting loader for the Quatt-aware live renderer.
  const base=(document.currentScript?.src||'').replace(/[^/]+$/,'');
  const s=document.createElement('script');
  s.src=base+'live-energy-v2.8.39.js?v=2.8.40';
  s.defer=true;
  document.head.appendChild(s);
})();
