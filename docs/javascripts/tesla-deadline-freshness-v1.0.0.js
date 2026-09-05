(function(){
  'use strict';
  const BASE='/homey-energy-manual/';
  window.HomeEnergyFrontend=window.HomeEnergyFrontend||{};
  window.HomeEnergyFrontend.teslaDeadlineFreshness='1.0.0';

  let core=null,command=null,refreshing=false;
  const native=()=>document.querySelector('[data-tesla-deadline-native]');
  const asTime=value=>{const t=Date.parse(String(value||''));return Number.isFinite(t)?t:null;};
  const fmtKWh=value=>Number(value).toLocaleString('nl-NL',{maximumFractionDigits:2});
  const hhmm=value=>{const s=String(value||'');const m=s.match(/T(\d{2}:\d{2})/);return m?m[1]:'—';};
  async function getJson(path){try{const r=await fetch(`${BASE}${path}?ts=${Date.now()}`,{cache:'no-store'});return r.ok?await r.json():null;}catch(_){return null;}}

  function commandIsNewer(){
    if(!command||typeof command.active!=='boolean')return false;
    const cmdAt=asTime(command.requestedAt||command.socEnteredAt);
    const coreAt=asTime(core?.meta?.source_sample_at||core?.meta?.generated_at);
    if(cmdAt===null)return false;
    if(coreAt===null)return true;
    return cmdAt>coreAt;
  }

  function apply(){
    if(!commandIsNewer())return false;
    const wrap=native();if(!wrap)return false;
    const active=Boolean(command.active);
    const off=wrap.querySelector('input[name="tesla-native-mode"][value="off"]');
    const on=wrap.querySelector('input[name="tesla-native-mode"][value="on"]');
    if(off)off.checked=!active;
    if(on)on.checked=active;
    const fields=wrap.querySelector('.tesla-inline-fields');if(fields)fields.hidden=!active;
    if(active){
      const deadline=wrap.querySelector('.tesla-inline-deadline');if(deadline)deadline.value=String(command.deadline||'').replace(' ','T').slice(0,16);
      const current=wrap.querySelector('.tesla-inline-current');if(current&&Number.isFinite(Number(command.currentSoc)))current.value=String(command.currentSoc);
      const target=wrap.querySelector('.tesla-inline-target');if(target&&Number.isFinite(Number(command.targetSoc)))target.value=String(command.targetSoc);
      const amps=wrap.querySelector('.tesla-inline-amps');if(amps&&Number.isFinite(Number(command.maxA)))amps.value=String(command.maxA);
    }
    const msg=wrap.querySelector('.tesla-inline-message');
    if(msg){
      if(active){
        const parts=[`Deadline actief · ${hhmm(command.deadline)}`];
        if(Number.isFinite(Number(command.maxA)))parts.push(`${Math.round(Number(command.maxA))} A`);
        if(Number.isFinite(Number(command.goalKWh)))parts.push(`${fmtKWh(command.goalKWh)} kWh doel`);
        parts.push('wacht op actuele Core-snapshot');
        msg.textContent=parts.join(' · ');
        msg.dataset.state='info';
      }else{
        msg.textContent='Geen deadline · wacht op actuele Core-snapshot';
        msg.dataset.state='info';
      }
    }
    wrap.dataset.deadlineFreshnessSource='command-newer-than-core';
    return true;
  }

  async function refresh(){
    if(refreshing)return;refreshing=true;
    try{
      const [c,cmd]=await Promise.all([getJson('data/energy-state-v2.json'),getJson('data/tesla-deadline-command.json')]);
      if(c)core=c;if(cmd)command=cmd;
      apply();
      setTimeout(apply,250);
      setTimeout(apply,1000);
    }finally{refreshing=false;}
  }

  const kick=()=>setTimeout(refresh,0);
  document.addEventListener('liveenergyrendered',kick);
  document.addEventListener('energycorev2state',kick);
  document.addEventListener('DOMContentSwitch',kick);
  document.addEventListener('appdatarefresh',kick);
  document.addEventListener('DOMContentLoaded',kick);
  if(document.readyState!=='loading')kick();
})();
