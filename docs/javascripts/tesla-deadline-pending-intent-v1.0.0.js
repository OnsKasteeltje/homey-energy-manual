(function(){
  'use strict';
  const BASE='/homey-energy-manual/';
  const TZ='Europe/Amsterdam';
  const ACK_WARN_MS=120000;

  const getJson=async path=>{try{const r=await fetch(`${BASE}${path}?ts=${Date.now()}`,{cache:'no-store'});return r.ok?await r.json():null;}catch(_){return null;}};
  const stamp=v=>{const n=Date.parse(String(v||''));return Number.isFinite(n)?n:0;};
  const localMinute=value=>{
    const d=new Date(String(value||''));
    if(!Number.isFinite(d.getTime()))return String(value||'').replace(' ','T').slice(0,16);
    const parts=new Intl.DateTimeFormat('sv-SE',{timeZone:TZ,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).formatToParts(d);
    const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));
    return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
  };
  const commandMinute=value=>String(value||'').replace(' ','T').slice(0,16);

  async function apply(){
    const wrap=document.querySelector('[data-tesla-deadline-native]');
    if(!wrap)return;
    const [cmd,core]=await Promise.all([getJson('data/tesla-deadline-command.json'),getJson('data/energy-state-v2.json')]);
    if(!cmd||typeof cmd.active!=='boolean')return;

    const commandAt=stamp(cmd.requestedAt||cmd.socEnteredAt);
    const coreAt=stamp(core?.meta?.generated_at);
    const cmdDeadline=commandMinute(cmd.deadline);
    const coreDeadline=localMinute(core?.tesla?.deadline_at);
    const acknowledged=Boolean(core?.tesla?.deadline_active)===Boolean(cmd.active)&&(!cmd.active||cmdDeadline===coreDeadline);

    // Runtime state now lives on the Pi. The GitHub snapshot can therefore lag.
    // Keep a newer website command as the visible UI intent until a published
    // runtime snapshot explicitly acknowledges the same deadline.
    if(acknowledged||!commandAt||commandAt<=coreAt)return;

    const off=wrap.querySelector('input[name="tesla-native-mode"][value="off"]');
    const on=wrap.querySelector('input[name="tesla-native-mode"][value="on"]');
    if(off)off.checked=!cmd.active;
    if(on)on.checked=cmd.active;
    const fields=wrap.querySelector('.tesla-inline-fields');
    if(fields)fields.hidden=!cmd.active;

    if(cmd.active){
      const deadline=wrap.querySelector('.tesla-inline-deadline');
      const current=wrap.querySelector('.tesla-inline-current');
      const target=wrap.querySelector('.tesla-inline-target');
      const amps=wrap.querySelector('.tesla-inline-amps');
      if(deadline&&cmdDeadline)deadline.value=cmdDeadline;
      if(current&&Number.isFinite(Number(cmd.currentSoc)))current.value=String(cmd.currentSoc);
      if(target&&Number.isFinite(Number(cmd.targetSoc)))target.value=String(cmd.targetSoc);
      if(amps&&Number.isFinite(Number(cmd.maxA)))amps.value=String(cmd.maxA);
    }

    const msg=wrap.querySelector('.tesla-inline-message');
    if(msg){
      const age=Date.now()-commandAt;
      msg.textContent=age>ACK_WARN_MS
        ?'Deadline opgeslagen · runtime draait op Pi; bevestiging is nog niet zichtbaar in de website-snapshot'
        :'Deadline opgeslagen · verwerking loopt';
      msg.dataset.state='info';
    }
    wrap.dataset.pendingIntent='true';
  }

  let timer=null;
  function schedule(){
    clearTimeout(timer);
    setTimeout(apply,0);
    timer=setTimeout(apply,750);
  }
  ['liveenergyrendered','energycorev2state','DOMContentSwitch','appdatarefresh','DOMContentLoaded'].forEach(name=>document.addEventListener(name,schedule));
  if(document.readyState!=='loading')schedule();
})();
