(function(){
  'use strict';
  const BASE='/homey-energy-manual/';
  window.HomeEnergyFrontend=window.HomeEnergyFrontend||{};
  window.HomeEnergyFrontend.teslaDeadlineController='2.8.104';
  let config=null,command=null,snapshot=null,loading=false;

  function today(){
    const now=new Date();
    const y=now.getFullYear();
    const m=String(now.getMonth()+1).padStart(2,'0');
    const d=String(now.getDate()).padStart(2,'0');
    return `${y}-${m}-${d}`;
  }

  function normalizeDeadline(value){
    const current=today();
    const raw=String(value||'');
    if(/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(raw)){
      const normalized=raw.replace(' ','T').slice(0,16);
      const time=normalized.slice(11,16)||'20:00';
      return normalized.slice(0,10)<current?`${current}T${time}`:normalized;
    }
    return `${current}T20:00`;
  }

  function native(){return document.querySelector('[data-tesla-deadline-native]');}
  function ensureLocalDefaults(wrap){
    if(!wrap)return;
    const deadline=wrap.querySelector('.tesla-inline-deadline');
    if(deadline){
      deadline.min=`${today()}T00:00`;
      deadline.value=normalizeDeadline(deadline.value);
    }
    const amps=wrap.querySelector('.tesla-inline-amps');
    if(amps&&!amps.value)amps.value='11';
  }

  async function getJson(path){
    try{
      const r=await fetch(`${BASE}${path}?ts=${Date.now()}`,{cache:'no-store'});
      return r.ok?await r.json():null;
    }catch(_){return null;}
  }

  async function loadData(){
    const [phase,cfg,cmd]=await Promise.all([
      getJson('data/pv-phase-24h.json'),
      getJson('data/tesla-control-config.json'),
      getJson('data/tesla-deadline-command.json')
    ]);
    snapshot=(phase?.samples||[]).at(-1)||null;
    config=cfg;
    command=cmd;
  }

  function activeState(){
    if(typeof snapshot?.evDeadlineActive==='boolean')return snapshot.evDeadlineActive;
    if(typeof snapshot?.EVDeadlineActive==='boolean')return snapshot.EVDeadlineActive;
    return command?.active===true;
  }

  function remoteDeadline(){return normalizeDeadline(snapshot?.evDeadlineTime||snapshot?.EVDeadlineTime||command?.deadline||'');}

  function bind(wrap){
    if(!wrap||wrap.dataset.bound==='2.8.104')return;
    wrap.dataset.bound='2.8.104';
    const fields=wrap.querySelector('.tesla-inline-fields');
    wrap.querySelectorAll('input[name="tesla-native-mode"]').forEach(r=>r.addEventListener('change',()=>{
      const active=wrap.querySelector('input[name="tesla-native-mode"]:checked')?.value==='on';
      if(fields)fields.hidden=!active;
      if(active)ensureLocalDefaults(wrap);
    }));
    wrap.querySelector('.tesla-inline-save')?.addEventListener('click',()=>save(wrap));
  }

  function prime(){
    const wrap=native();
    if(!wrap)return false;
    bind(wrap);
    ensureLocalDefaults(wrap);
    const msg=wrap.querySelector('.tesla-inline-message');
    if(msg&&msg.textContent==='Instellingen laden…')msg.textContent='';
    return true;
  }

  function populate(){
    const wrap=native();
    if(!wrap)return false;
    bind(wrap);
    const active=activeState();
    const currentSoc=Number(command?.currentSoc);
    const targetSoc=Number(command?.targetSoc);
    const hasSoc=Number.isFinite(currentSoc)&&Number.isFinite(targetSoc)&&targetSoc>currentSoc;
    const maxA=Number(snapshot?.evMaxA??snapshot?.EVMaxA??command?.maxA??11);
    const linked=Boolean(String(config?.worker_url||'').trim());
    const off=wrap.querySelector('input[name="tesla-native-mode"][value="off"]');
    const on=wrap.querySelector('input[name="tesla-native-mode"][value="on"]');
    if(off)off.checked=!active;if(on)on.checked=active;
    const fields=wrap.querySelector('.tesla-inline-fields');if(fields)fields.hidden=!active;
    const deadline=wrap.querySelector('.tesla-inline-deadline');
    if(deadline){deadline.min=`${today()}T00:00`;deadline.value=remoteDeadline();}
    const current=wrap.querySelector('.tesla-inline-current');if(current&&hasSoc)current.value=String(currentSoc);
    const target=wrap.querySelector('.tesla-inline-target');if(target&&hasSoc)target.value=String(targetSoc);
    const amps=wrap.querySelector('.tesla-inline-amps');if(amps)amps.value=String(Number.isFinite(maxA)&&maxA>=6&&maxA<=16?maxA:11);
    const button=wrap.querySelector('.tesla-inline-save');if(button)button.disabled=!linked;
    const msg=wrap.querySelector('.tesla-inline-message');if(msg)msg.textContent=linked?'':'Write-route niet gekoppeld';
    return true;
  }

  async function save(wrap){
    const worker=String(config?.worker_url||'').trim();
    const msg=wrap.querySelector('.tesla-inline-message');
    const button=wrap.querySelector('.tesla-inline-save');
    const active=wrap.querySelector('input[name="tesla-native-mode"]:checked')?.value==='on';
    const deadline=wrap.querySelector('.tesla-inline-deadline')?.value||'';
    const currentSoc=Number(wrap.querySelector('.tesla-inline-current')?.value);
    const targetSoc=Number(wrap.querySelector('.tesla-inline-target')?.value);
    const maxA=Number(wrap.querySelector('.tesla-inline-amps')?.value||11);
    if(active&&(!deadline||!Number.isFinite(currentSoc)||currentSoc<0||currentSoc>99||!Number.isFinite(targetSoc)||targetSoc<1||targetSoc>100||targetSoc<=currentSoc||maxA<6||maxA>16)){
      if(msg)msg.textContent='Controleer deadline, SOC en laadstroom.';return;
    }
    const pin=window.prompt('Voer de Tesla-control PIN in:');
    if(pin===null)return;
    if(button)button.disabled=true;if(msg)msg.textContent='Opslaan…';
    try{
      const r=await fetch(worker,{method:'POST',headers:{'Content-Type':'application/json','X-Tesla-Control-Pin':pin},body:JSON.stringify({active,deadline:active?deadline:'',currentSoc:active?currentSoc:null,targetSoc:active?targetSoc:null,maxA})});
      const j=await r.json().catch(()=>({}));
      if(!r.ok||!j.ok)throw new Error(j.error||`HTTP ${r.status}`);
      command=j.command||command;
      if(msg)msg.textContent=active?'Deadline opgeslagen':'Deadline uitgeschakeld';
    }catch(e){if(msg)msg.textContent=`Opslaan mislukt: ${e.message||e}`;}
    finally{if(button)button.disabled=false;}
  }

  async function refresh(){
    prime();
    if(loading)return;loading=true;
    try{await loadData();populate();}finally{loading=false;}
  }

  function afterRender(){setTimeout(()=>{prime();if(config||command||snapshot)populate();else refresh();},0);}
  document.addEventListener('energycorev2state',afterRender);
  document.addEventListener('DOMContentSwitch',()=>setTimeout(refresh,100));
  document.addEventListener('DOMContentLoaded',()=>setTimeout(refresh,120));
  if(document.readyState!=='loading')setTimeout(refresh,120);
})();
