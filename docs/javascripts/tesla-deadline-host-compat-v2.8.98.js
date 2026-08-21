(function(){
  'use strict';

  const HOST_CLASS='tesla-regulation';

  function ensureHost(){
    const root=document.getElementById('live-energy-flow');
    if(!root||root.querySelector(`.${HOST_CLASS}`)) return;

    const manager=Array.from(root.querySelectorAll('.energy-manager-panel'))
      .find(panel=>!panel.classList.contains('heating-hybrid-panel'));
    if(!manager) return;

    const host=document.createElement('div');
    host.className=HOST_CLASS;
    host.dataset.teslaDeadlineHost='compat-v2.8.98';
    manager.insertAdjacentElement('afterend',host);
  }

  function start(){
    ensureHost();
    const root=document.getElementById('live-energy-flow');
    if(!root||root.dataset.teslaDeadlineHostObserver==='1') return;
    root.dataset.teslaDeadlineHostObserver='1';
    new MutationObserver(ensureHost).observe(root,{childList:true,subtree:true});
  }

  document.addEventListener('DOMContentLoaded',start);
  document.addEventListener('DOMContentSwitch',start);
})();
