(function(){
  'use strict';
  // v2.8.37: legacy Shadow tesla_kWh_est values are not measurement-grade.
  // Keep P1/boiler history intact, but never present legacy Tesla estimates as facts.
  // Important: do NOT observe mutations on the dashboard itself. The previous observer
  // called scrub() after every DOM write performed by scrub(), which could create a
  // self-triggering mutation loop and freeze history tabs / Material navigation.
  const ROOT='#energy-history-dashboard';
  function scrub(){
    const root=document.querySelector(ROOT); if(!root)return;
    root.querySelectorAll('.eh-card').forEach(card=>{
      const label=card.querySelector('.eh-card-label');
      if(!label||label.textContent.trim()!=='Tesla')return;
      const value=card.querySelector('.eh-card-value');
      if(value&&value.textContent!=='—')value.textContent='—';
      let sub=card.querySelector('.eh-card-sub');
      if(!sub){sub=document.createElement('div');sub.className='eh-card-sub';card.appendChild(sub);}
      if(sub.textContent!=='legacy schatting uitgesloten')sub.textContent='legacy schatting uitgesloten';
    });
    // The fourth aggregate chart series is the legacy Tesla estimate. Hide the line
    // and its integrated point markers; day view remains based on direct v2 samples.
    const title=[...root.querySelectorAll('.eh-panel-title h3')].find(x=>/Weekoverzicht|Maandoverzicht|Energie-overzicht · jaar/.test(x.textContent));
    if(title){
      const panel=title.closest('.eh-panel');
      if(panel){
        const lines=panel.querySelectorAll('path.eh-line');
        if(lines.length===4&&lines[3].style.display!=='none')lines[3].style.display='none';
        panel.querySelectorAll('circle.eh-data-point.eh-pv').forEach(p=>p.style.display='none');
        panel.querySelectorAll('.eh-key').forEach(k=>{
          if(k.textContent.trim()==='Tesla')k.textContent='Tesla · legacy uitgesloten';
        });
      }
    }
  }
  document.addEventListener('DOMContentLoaded',()=>setTimeout(scrub,100));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(scrub,100));
  document.addEventListener('click',e=>{
    if(e.target&&e.target.closest&&e.target.closest(`${ROOT} .eh-tab`))setTimeout(scrub,0);
  });
})();
