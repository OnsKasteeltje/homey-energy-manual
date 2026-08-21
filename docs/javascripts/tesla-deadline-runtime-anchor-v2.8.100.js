(function(){
  'use strict';
  const ROOT_ID='live-energy-flow';
  const HOST_CLASS='tesla-regulation';
  const MARK='runtime-anchor-v2.8.100';
  let kicking=false;

  function ensureAnchor(){
    const root=document.getElementById(ROOT_ID);
    if(!root)return false;
    const manager=Array.from(root.querySelectorAll('.energy-manager-panel')).find(p=>!p.classList.contains('heating-hybrid-panel'));
    if(!manager)return false;
    let host=root.querySelector(`.${HOST_CLASS}`);
    if(!host){
      host=document.createElement('div');
      host.className=HOST_CLASS;
      host.dataset.teslaDeadlineHost=MARK;
      manager.insertAdjacentElement('afterend',host);
    }else if(host.previousElementSibling!==manager){
      manager.insertAdjacentElement('afterend',host);
    }
    return true;
  }

  function kick(){
    if(kicking)return;
    kicking=true;
    try{
      if(ensureAnchor()){
        document.dispatchEvent(new CustomEvent('DOMContentSwitch',{detail:{reason:MARK,at:new Date().toISOString()}}));
      }
    }finally{
      setTimeout(()=>{kicking=false;},50);
    }
  }

  function start(){
    kick();
    const root=document.getElementById(ROOT_ID);
    if(root&&!root.dataset.teslaDeadlineRuntimeAnchor){
      root.dataset.teslaDeadlineRuntimeAnchor=MARK;
      new MutationObserver(()=>{
        if(!root.querySelector(`.${HOST_CLASS}`)||!document.getElementById('tesla-deadline-control')) kick();
      }).observe(root,{childList:true,subtree:true});
    }
    [100,300,800,1600,3200].forEach(ms=>setTimeout(kick,ms));
  }

  document.addEventListener('DOMContentLoaded',start);
  document.addEventListener('DOMContentSwitch',()=>setTimeout(kick,0));
  if(document.readyState!=='loading')start();
})();
