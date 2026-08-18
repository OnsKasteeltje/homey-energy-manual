(function(){
  'use strict';
  // v2.8.36: legacy Shadow tesla_kWh_est values are not measurement-grade.
  // Keep P1/boiler history intact, but never present legacy Tesla estimates as facts.
  const ROOT='#energy-history-dashboard';
  function scrub(){
    const root=document.querySelector(ROOT); if(!root)return;
    root.querySelectorAll('.eh-card').forEach(card=>{
      const label=card.querySelector('.eh-card-label');
      if(!label||label.textContent.trim()!=='Tesla')return;
      const value=card.querySelector('.eh-card-value');
      if(value)value.textContent='—';
      let sub=card.querySelector('.eh-card-sub');
      if(!sub){sub=document.createElement('div');sub.className='eh-card-sub';card.appendChild(sub);}
      sub.textContent='legacy schatting uitgesloten';
    });
    // The fourth aggregate chart series is the legacy Tesla estimate. Hide only that
    // series; day view has five series and is based on v2 samples, so leave it intact.
    const title=[...root.querySelectorAll('.eh-panel-title h3')].find(x=>/Weekoverzicht|Maandoverzicht|Energie-overzicht · jaar/.test(x.textContent));
    if(title){const panel=title.closest('.eh-panel');if(panel){const lines=panel.querySelectorAll('path.eh-line');if(lines.length===4)lines[3].style.display='none';const keys=panel.querySelectorAll('.eh-key');keys.forEach(k=>{if(k.textContent.trim()==='Tesla')k.textContent='Tesla · legacy uitgesloten';});}}
  }
  document.addEventListener('DOMContentLoaded',()=>{setTimeout(scrub,100);});
  document.addEventListener('click',()=>setTimeout(scrub,0));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(scrub,100));
  const root=document.querySelector(ROOT);if(root)new MutationObserver(scrub).observe(root,{childList:true,subtree:true});
})();
