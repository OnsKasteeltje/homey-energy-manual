(function(){
  'use strict';
  function removeKpis(){
    const root=document.getElementById('home-architecture');
    if(!root)return;
    root.querySelectorAll('.ha-kpis').forEach(el=>el.remove());
  }
  document.addEventListener('energycorev2state',()=>setTimeout(removeKpis,0));
  document.addEventListener('DOMContentLoaded',()=>setTimeout(removeKpis,350));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(removeKpis,150));
  setTimeout(removeKpis,1000);
})();
