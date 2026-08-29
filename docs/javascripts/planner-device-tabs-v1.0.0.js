(() => {
  const root=document.getElementById('planner-shadow'); if(!root)return;
  const tabs=[['overview','Overzicht'],['flex','Flexbudget'],['tesla','Tesla'],['warmwater','Warm water'],['battery','Batterij'],['quatt','Quatt'],['devices','Apparaten'],['diagnostics','Diagnose'],['raw','Raw']];
  const nav=document.createElement('nav');nav.className='ps-device-tabs';nav.setAttribute('aria-label','Planner onderdelen');
  tabs.forEach(([id,label])=>{const b=document.createElement('button');b.type='button';b.dataset.tab=id;b.textContent=label;b.addEventListener('click',()=>select(id));nav.append(b);});
  const hero=root.querySelector('.ps-hero'); if(hero)hero.after(nav); else root.prepend(nav);
  const classify=()=>{
    [...root.children].forEach(n=>{if(n===nav||n.classList?.contains('ps-hero')||n.id==='ps-status')return;if(n.id==='ps-ww-multislot')n.dataset.plannerTab='warmwater';else if(n.classList?.contains('ps-section'))n.dataset.plannerTab='overview';else if(n.classList?.contains('ps-summary')||n.classList?.contains('ps-grid'))n.dataset.plannerTab='overview';});
  };
  const placeholder=(id)=>{let p=root.querySelector(`[data-planner-placeholder="${id}"]`);if(p)return p;p=document.createElement('section');p.className='ps-section ps-tab-placeholder';p.dataset.plannerPlaceholder=id;p.dataset.plannerTab=id;const label=tabs.find(x=>x[0]===id)?.[1]||id;p.innerHTML=`<h2>${label}</h2><div class="ps-chart-note">Deze subtab gebruikt dezelfde read-only Planner Shadow snapshot. Een specifieke ${label}-detailweergave wordt hier toegevoegd zodra de Planner daarvoor voldoende modeldata publiceert.</div>`;root.append(p);return p;};
  const select=id=>{classify();tabs.forEach(([tid])=>{nav.querySelector(`[data-tab="${tid}"]`)?.classList.toggle('active',tid===id);});if(id!=='overview'&&id!=='warmwater')placeholder(id);[...root.querySelectorAll('[data-planner-tab]')].forEach(n=>n.hidden=n.dataset.plannerTab!==id);location.hash=`planner-${id}`;};
  const observer=new MutationObserver(()=>{classify();const active=nav.querySelector('.active')?.dataset.tab||'overview';[...root.querySelectorAll('[data-planner-tab]')].forEach(n=>n.hidden=n.dataset.plannerTab!==active);});observer.observe(root,{childList:true});
  const initial=location.hash.startsWith('#planner-')?location.hash.slice(9):'overview';select(tabs.some(x=>x[0]===initial)?initial:'overview');
})();