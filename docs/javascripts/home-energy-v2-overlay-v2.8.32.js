(function(){
  'use strict';
  const fmtW=w=>{w=Number(w||0);return Math.abs(w)>=1000?`${(w/1000).toLocaleString('nl-NL',{maximumFractionDigits:2})} kW`:`${Math.round(w)} W`};
  function findRow(label){return [...document.querySelectorAll('#home-architecture .ha-row')].find(r=>r.querySelector('span')?.textContent.trim()===label);}
  function setRow(label,value){const r=findRow(label);if(!r)return;const s=r.querySelectorAll(':scope > span');if(s[1])s[1].textContent=value;}
  function setKpi(label,value){const k=[...document.querySelectorAll('#home-architecture .ha-kpi')].find(x=>x.querySelector('span')?.textContent.trim()===label);const s=k?.querySelector('strong');if(s)s.textContent=value;}
  function apply(detail){
    const r=detail?.raw;if(!r)return;
    const p=r.pv||{},g=r.grid||{},hw=r.hot_water||{},t=r.tesla||{};
    const pv=Number(p.total_w)||0,p1=Number(g.power_w)||0,home=Math.max(0,pv+p1);
    setRow('P1 / Net',fmtW(p1));
    setRow('PV · SolarEdge',fmtW(p.solaredge_w));
    setRow('PV · GoodWe 4,2kW',fmtW(p.goodwe_4200_w));
    setRow('PV · GoodWe 2kW',fmtW(p.goodwe_2000_w));
    setRow('Boiler',hw.boiler_power_w>100?`verwarmen · ${fmtW(hw.boiler_power_w)}`:(hw.boiler_on?'aan · 0 W':'uit'));
    setRow('Auto beschikbaar',t.connected?'ja / aangesloten':'nee');
    setKpi('PV-productie nu',fmtW(pv));
    setKpi('Verbruik woning nu',fmtW(home));
    setKpi('Netto net nu',fmtW(p1));
    setKpi('Boilerstatus',hw.boiler_power_w>100?'Verwarmen':(hw.boiler_on?'Aan / thermostaat af':'Uit'));
    const health=document.querySelector('#home-architecture .ha-health span');
    if(health&&r.meta?.source_sample_at) health.textContent=`Energy Core v2 · revision ${r.meta.state_revision??'?'} · ${new Date(r.meta.source_sample_at).toLocaleString('nl-NL')}`;
  }
  function current(){if(window.EnergyCoreV2?.state)apply(window.EnergyCoreV2.state);}
  document.addEventListener('energycorev2state',e=>setTimeout(()=>apply(e.detail),120));
  document.addEventListener('DOMContentLoaded',()=>setTimeout(current,500));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(current,400));
  const rootObserver=new MutationObserver(()=>setTimeout(current,50));
  document.addEventListener('DOMContentLoaded',()=>{const r=document.getElementById('home-architecture');if(r)rootObserver.observe(r,{childList:true,subtree:true});});
})();
