(function(){
  'use strict';
  const fmtW=w=>{w=Number(w||0);return Math.abs(w)>=1000?`${(w/1000).toLocaleString('nl-NL',{maximumFractionDigits:2})} kW`:`${Math.round(w)} W`;};
  function apply(detail){
    const root=document.getElementById('home-architecture');
    const r=detail?.raw||window.EnergyCoreV2?.state?.raw;
    if(!root||!r)return;
    const q=r.quatt||r.heating||r.space_heating;
    if(!q)return;
    const power=Number(q.power_w??q.quatt_power_w??0)||0;
    const thermal=Number(q.thermal_power_w||0)||0;
    const demand=q.thermostat_heating_on===true;
    const cvReq=q.cv_requested===true||q.cv_onoff_command===true;
    const cvFlame=q.cv_flame===true;
    const active=thermal>100||power>100||demand;
    const state=cvFlame&&active?'Hybride verwarming':active?'Quatt actief':cvFlame?'CV verwarmt':cvReq?'CV ondersteuning gevraagd':demand?'Warmtevraag':'Geen warmtevraag';
    const measureList=root.querySelector('.ha-stage.measure .ha-list');
    if(measureList&&!measureList.querySelector('[data-quatt-row]')){
      const row=document.createElement('div');row.className='ha-row';row.dataset.quattRow='1';row.innerHTML=`<span>Ruimteverwarming · Quatt</span><span>${fmtW(power)}</span>`;measureList.appendChild(row);
    }
    const goals=root.querySelector('.ha-stage.decision .ha-goals');
    if(goals&&!goals.querySelector('[data-heating-goal]')){
      const el=document.createElement('div');el.className='ha-goal';el.dataset.heatingGoal='1';el.innerHTML=`<div class="ha-goal-icon">♨</div><div><strong>Ruimteverwarming</strong><span class="ha-goal-state ${active||cvFlame||cvReq?'warn':'off'}">${state}</span><small>${fmtW(power)} elektrisch${thermal>0?` · ${fmtW(thermal)} thermisch`:''} · Quatt observe-only</small></div>`;goals.appendChild(el);
    }
  }
  document.addEventListener('energycorev2state',e=>setTimeout(()=>apply(e.detail),30));
  document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>apply(),350));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(()=>apply(),180));
})();
