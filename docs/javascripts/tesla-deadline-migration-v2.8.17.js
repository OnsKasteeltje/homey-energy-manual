(function(){
  function apply(){
    const panel=document.getElementById('tesla-deadline-control');
    if(!panel) return;
    const runtime=panel.querySelector('.tesla-deadline-runtime');
    if(!runtime || runtime.hidden) return;
    const socBox=[...runtime.querySelectorAll(':scope > div')].find(d=>d.querySelector('span')?.textContent.trim()==='SOC-doel');
    const socValue=socBox?.querySelector('strong')?.textContent.trim()||'';
    if(socValue!=='Opnieuw invoeren') return;

    runtime.classList.add('tesla-deadline-runtime--migration');
    runtime.innerHTML=`<div class="tesla-deadline-migration"><strong>Deadline-instelling verouderd</strong><span>Deze deadline gebruikt nog het oude kWh-model. Voer hierboven één keer de huidige SOC en doel-SOC in en sla de deadline opnieuw op.</span></div>`;

    const note=panel.querySelector('.tesla-deadline-note');
    if(note) note.textContent='Na opnieuw opslaan gebruikt de deadlinefunctie het SOC-model. Daarna verschijnen hier de operationele status, het SOC-doel en het berekende uiterste startmoment.';
  }

  function start(){
    apply();
    const root=document.getElementById('live-energy-flow')||document.body;
    new MutationObserver(apply).observe(root,{childList:true,subtree:true});
  }
  document.addEventListener('DOMContentLoaded',start);
  document.addEventListener('DOMContentSwitch',start);
})();
