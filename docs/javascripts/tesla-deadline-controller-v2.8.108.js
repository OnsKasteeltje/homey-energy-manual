(function(){
  'use strict';
  const BASE='/homey-energy-manual/';
  window.HomeEnergyFrontend=window.HomeEnergyFrontend||{};
  window.HomeEnergyFrontend.teslaDeadlineController='2.8.108';

  let config=null,command=null,snapshot=null,loading=false,draft=null;
  let bootTimer=null,bootAttempts=0;

  const native=()=>document.querySelector('[data-tesla-deadline-native]');
  const today=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
  function normalizeDeadline(value){
    const current=today(),raw=String(value||'');
    if(/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(raw)){
      const n=raw.replace(' ','T').slice(0,16),time=n.slice(11,16)||'20:00';
      return n.slice(0,10)<current?`${current}T${time}`:n;
    }
    return `${current}T20:00`;
  }
  async function getJson(path){try{const r=await fetch(`${BASE}${path}?ts=${Date.now()}`,{cache:'no-store'});return r.ok?await r.json():null;}catch(_){return null;}}
  async function loadData(){
    const [phase,cfg,cmd]=await Promise.all([getJson('data/pv-phase-24h.json'),getJson('data/tesla-control-config.json'),getJson('data/tesla-deadline-command.json')]);
    snapshot=(phase?.samples||[]).at(-1)||null;config=cfg;command=cmd;
  }
  function activeState(){
    if(typeof command?.active==='boolean')return command.active;
    if(typeof snapshot?.evDeadlineActive==='boolean')return snapshot.evDeadlineActive;
    if(typeof snapshot?.EVDeadlineActive==='boolean')return snapshot.EVDeadlineActive;
    return false;
  }
  function remoteDeadline(){return normalizeDeadline(command?.deadline||snapshot?.evDeadlineTime||snapshot?.EVDeadlineTime||'');}
  function readDraft(wrap){return wrap?{
    active:wrap.querySelector('input[name="tesla-native-mode"]:checked')?.value==='on',
    deadline:wrap.querySelector('.tesla-inline-deadline')?.value||'',
    currentSoc:wrap.querySelector('.tesla-inline-current')?.value||'',
    targetSoc:wrap.querySelector('.tesla-inline-target')?.value||'',
    maxA:wrap.querySelector('.tesla-inline-amps')?.value||'11'
  }:null;}
  function rememberDraft(wrap){draft=readDraft(wrap)||draft;}
  function applyDraft(wrap){
    if(!wrap||!draft)return false;
    const off=wrap.querySelector('input[name="tesla-native-mode"][value="off"]'),on=wrap.querySelector('input[name="tesla-native-mode"][value="on"]');
    if(off)off.checked=!draft.active;if(on)on.checked=draft.active;
    const fields=wrap.querySelector('.tesla-inline-fields');if(fields)fields.hidden=!draft.active;
    const deadline=wrap.querySelector('.tesla-inline-deadline');if(deadline){deadline.min=`${today()}T00:00`;deadline.value=normalizeDeadline(draft.deadline);}
    const current=wrap.querySelector('.tesla-inline-current');if(current)current.value=draft.currentSoc;
    const target=wrap.querySelector('.tesla-inline-target');if(target)target.value=draft.targetSoc;
    const amps=wrap.querySelector('.tesla-inline-amps');if(amps)amps.value=draft.maxA||'11';
    return true;
  }
  function ensureDefaults(wrap){
    const deadline=wrap?.querySelector('.tesla-inline-deadline');if(deadline){deadline.min=`${today()}T00:00`;deadline.value=normalizeDeadline(deadline.value);}
    const amps=wrap?.querySelector('.tesla-inline-amps');if(amps&&!amps.value)amps.value='11';
  }
  function bind(wrap){
    if(!wrap||wrap.dataset.bound==='2.8.108')return;
    wrap.dataset.bound='2.8.108';
    const fields=wrap.querySelector('.tesla-inline-fields');
    wrap.querySelectorAll('input[name="tesla-native-mode"]').forEach(r=>r.addEventListener('change',()=>{
      const active=wrap.querySelector('input[name="tesla-native-mode"]:checked')?.value==='on';
      if(fields)fields.hidden=!active;if(active)ensureDefaults(wrap);rememberDraft(wrap);
    }));
    wrap.querySelectorAll('.tesla-inline-deadline,.tesla-inline-current,.tesla-inline-target,.tesla-inline-amps').forEach(el=>{
      el.addEventListener('input',()=>rememberDraft(wrap));el.addEventListener('change',()=>rememberDraft(wrap));
    });
    wrap.querySelector('.tesla-inline-save')?.addEventListener('click',()=>save(wrap));
  }
  function populate(){
    const wrap=native();if(!wrap)return false;bind(wrap);
    if(!applyDraft(wrap)){
      const active=activeState(),currentSoc=Number(command?.currentSoc),targetSoc=Number(command?.targetSoc);
      const hasSoc=Number.isFinite(currentSoc)&&Number.isFinite(targetSoc)&&targetSoc>currentSoc;
      const maxA=Number(command?.maxA??snapshot?.evMaxA??snapshot?.EVMaxA??11);
      const off=wrap.querySelector('input[name="tesla-native-mode"][value="off"]'),on=wrap.querySelector('input[name="tesla-native-mode"][value="on"]');
      if(off)off.checked=!active;if(on)on.checked=active;
      const fields=wrap.querySelector('.tesla-inline-fields');if(fields)fields.hidden=!active;
      const deadline=wrap.querySelector('.tesla-inline-deadline');if(deadline){deadline.min=`${today()}T00:00`;deadline.value=remoteDeadline();}
      const current=wrap.querySelector('.tesla-inline-current');if(current&&hasSoc)current.value=String(currentSoc);
      const target=wrap.querySelector('.tesla-inline-target');if(target&&hasSoc)target.value=String(targetSoc);
      const amps=wrap.querySelector('.tesla-inline-amps');if(amps)amps.value=String(Number.isFinite(maxA)&&maxA>=6&&maxA<=16?maxA:11);
    }
    const linked=Boolean(String(config?.worker_url||'').trim());
    const button=wrap.querySelector('.tesla-inline-save');if(button)button.disabled=!linked;
    const msg=wrap.querySelector('.tesla-inline-message');if(msg&&!draft)msg.textContent=linked?'':'Write-route niet gekoppeld';
    return true;
  }
  async function refresh(){
    if(loading)return;loading=true;
    try{await loadData();if(!populate())scheduleBootReady();}finally{loading=false;}
  }
  function scheduleBootReady(){
    if(native()){
      clearTimeout(bootTimer);bootTimer=null;bootAttempts=0;
      if(config||command||snapshot)populate();else refresh();
      return;
    }
    if(bootAttempts>=40)return;
    bootAttempts+=1;
    clearTimeout(bootTimer);bootTimer=setTimeout(scheduleBootReady,125);
  }
  async function save(wrap){
    rememberDraft(wrap);
    const worker=String(config?.worker_url||'').trim(),msg=wrap.querySelector('.tesla-inline-message'),button=wrap.querySelector('.tesla-inline-save');
    const d=draft||readDraft(wrap),currentSoc=Number(d.currentSoc),targetSoc=Number(d.targetSoc),maxA=Number(d.maxA||11);
    if(d.active&&(!d.deadline||!Number.isFinite(currentSoc)||currentSoc<0||currentSoc>99||!Number.isFinite(targetSoc)||targetSoc<1||targetSoc>100||targetSoc<=currentSoc||maxA<6||maxA>16)){if(msg)msg.textContent='Controleer deadline, SOC en laadstroom.';return;}
    const pin=window.prompt('Voer de Tesla-control PIN in:');if(pin===null)return;
    if(button)button.disabled=true;if(msg)msg.textContent='Opslaan…';
    try{
      const r=await fetch(worker,{method:'POST',headers:{'Content-Type':'application/json','X-Tesla-Control-Pin':pin},body:JSON.stringify({active:d.active,deadline:d.active?d.deadline:'',currentSoc:d.active?currentSoc:null,targetSoc:d.active?targetSoc:null,maxA})});
      const j=await r.json().catch(()=>({}));if(!r.ok||!j.ok)throw new Error(j.error||`HTTP ${r.status}`);
      command=j.command||command;draft=null;if(msg)msg.textContent=d.active?'Deadline opgeslagen':'Deadline uitgeschakeld';setTimeout(refresh,0);
    }catch(e){if(msg)msg.textContent=`Opslaan mislukt: ${e.message||e}`;}finally{if(button)button.disabled=false;}
  }

  function lifecycleRefresh(){bootAttempts=0;scheduleBootReady();setTimeout(refresh,0);}
  document.addEventListener('liveenergyrendered',lifecycleRefresh);
  document.addEventListener('energycorev2state',()=>setTimeout(scheduleBootReady,0));
  document.addEventListener('DOMContentSwitch',lifecycleRefresh);
  document.addEventListener('appdatarefresh',lifecycleRefresh);
  document.addEventListener('DOMContentLoaded',lifecycleRefresh);
  if(document.readyState!=='loading')lifecycleRefresh();
})();