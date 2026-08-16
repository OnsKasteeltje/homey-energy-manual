(function(){
  const LABELS={
    DEADLINE_PRIJS_NEGATIEF:'Laden · negatieve stroomprijs',
    DEADLINE_PV_OVERSCHOT:'Laden op PV-overschot',
    DEADLINE_WACHT_PV_FORECAST:'Wacht op voorspelde PV',
    DEADLINE_PRIJS_GOEDKOOP:'Laden · gunstige stroomprijs',
    DEADLINE_WACHT_GOEDKOPER:'Wacht op goedkoper laadmoment'
  };
  function apply(){
    const panel=document.getElementById('tesla-deadline-control');
    if(!panel)return;
    const box=[...panel.querySelectorAll('.tesla-deadline-runtime > div')].find(d=>d.querySelector('span')?.textContent.trim()==='Status');
    const strong=box?.querySelector('strong');
    if(!strong)return;
    const raw=strong.textContent.trim();
    if(LABELS[raw])strong.textContent=LABELS[raw];
  }
  function start(){
    apply();
    const root=document.getElementById('live-energy-flow')||document.body;
    new MutationObserver(apply).observe(root,{childList:true,subtree:true,characterData:true});
  }
  document.addEventListener('DOMContentLoaded',start);
  document.addEventListener('DOMContentSwitch',start);
})();
