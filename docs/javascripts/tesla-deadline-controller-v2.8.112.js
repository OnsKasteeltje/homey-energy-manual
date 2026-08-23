(function(){
  'use strict';
  const BASE='/homey-energy-manual/';
  const PENDING_ACK_MS=120000;
  window.HomeEnergyFrontend=window.HomeEnergyFrontend||{};
  window.HomeEnergyFrontend.teslaDeadlineController='2.8.113';

  let config=null,command=null,coreTesla=null,loading=false,draft=null,pendingCommand=null,pendingFailure='';
  let bootTimer=null,bootAttempts=0;

  const native=()=>document.querySelector('[data-tesla-deadline-native]');
  const today=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
  const nowLocalMinute=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}T${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;};
  function normalizeDeadline(value){
    const current=today(),raw=String(value||'');
    if(/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(raw)){
      const n=raw.replace(' ','T').slice(0,16),time=n.slice(11,16)||'20:00';
      return n.slice(0,10)<current?`${current}T${time}`:n;
    }
    return `${current}T20:00`;
  }
  const deadlinePast=value=>{const s=String(value||'').trim();if(!s)return false;const d=new Date(s.replace(' ','T'));return Number.isFinite(d.getTime())&&Date.now()>=d.getTime();};
  const pendingAge=value=>{const t=Date.parse(String(value?.requestedAt||value?.socEnteredAt||''));return Number.isFinite(t)?Date.now()-t:0;};
  const fmtKWh=value=>Number(value).toLocaleString('nl-NL',{maximumFractionDigits:2});
  async function getJson(path){try{const r=await fetch(`${BASE}${path}?ts=${Date.now()}`,{cache:'no-store'});return r.ok?await r.json():null;}catch(_){return null;}}

  function coreAcknowledgesPending(){
    if(!pendingCommand||typeof coreTesla?.deadline_active!=='boolean')return false;
    if(Boolean(coreTesla.deadline_active)!==Boolean(pendingCommand.active))return false;
    if(!pendingCommand.active)return true;
    return normalizeDeadline(coreTesla?.deadline_at||'')===normalizeDeadline(pendingCommand.deadline||'');
  }
  function reconcilePending(){
    if(coreAcknowledgesPending()){pendingCommand=null;pendingFailure='';return;}
    if(pendingCommand&&pendingAge(pendingCommand)>PENDING_ACK_MS){
      pendingFailure=pendingCommand.active?'Deadline niet door Core bevestigd · controleer write-route':'Uitschakelen niet door Core bevestigd · controleer write-route';
      pendingCommand=null;
    }
  }

  async function loadData(){
    const [core,cfg,cmd]=await Promise.all([getJson('data/energy-state-v2.json'),getJson('data/tesla-control-config.json'),getJson('data/tesla-deadline-command.json')]);
    coreTesla=core?.tesla||coreTesla;config=cfg;command=cmd;reconcilePending();
  }
  function effectiveCommand(){return pendingCommand||command;}
  function activeState(){
    if(pendingCommand&&typeof pendingCommand.active==='boolean')return pendingCommand.active;
    if(typeof coreTesla?.deadline_active==='boolean')return coreTesla.deadline_active;
    if(typeof command?.active==='boolean')return command.active;
    return false;
  }
  function lifecycle(){
    const status=String(coreTesla?.deadline_status||coreTesla?.lifecycle_status||'').toUpperCase();
    const remaining=Math.max(0,Number(coreTesla?.remaining_kwh)||0);
    const amps=Math.max(0,Number(coreTesla?.requested_a)||Number(effectiveCommand()?.maxA)||0);
    if(activeState())return {kind:'active',status,remaining,amps};
    if(status==='DEADLINE_REACHED')return {kind:'reached',status,remaining,amps};
    if(status==='DOEL_GEHAALD_NA_DEADLINE')return {kind:'missed_done',status,remaining,amps};
    if(status.includes('DEADLINE_MISSED'))return {kind:remaining>0.01?'missed_open':'missed_done',status,remaining,amps};
    if(deadlinePast(coreTesla?.deadline_at||effectiveCommand()?.deadline)&&remaining>0.01)return {kind:'missed_open',status,remaining,amps};
    return {kind:'none',status,remaining,amps};
  }
  function remoteDeadline(){return normalizeDeadline(pendingCommand?.deadline||coreTesla?.deadline_at||command?.deadline||'');}
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
    const deadline=wrap.querySelector('.tesla-inline-deadline');if(deadline){deadline.min=nowLocalMinute();deadline.value=normalizeDeadline(draft.deadline);}
    const current=wrap.querySelector('.tesla-inline-current');if(current)current.value=draft.currentSoc;
    const target=wrap.querySelector('.tesla-inline-target');if(target)target.value=draft.targetSoc;
    const amps=wrap.querySelector('.tesla-inline-amps');if(amps)amps.value=draft.maxA||'11';
    return true;
  }
  function ensureDefaults(wrap){
    const deadline=wrap?.querySelector('.tesla-inline-deadline');if(deadline){deadline.min=nowLocalMinute();deadline.value=normalizeDeadline(deadline.value);}
    const amps=wrap?.querySelector('.tesla-inline-amps');if(amps&&!amps.value)amps.value='11';
  }
  function bind(wrap){
    if(!wrap||wrap.dataset.bound==='2.8.113')return;
    wrap.dataset.bound='2.8.113';
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
  function statusText(lc){
    if(pendingCommand)return pendingCommand.active?'Deadline opgeslagen · verwerking loopt':'Deadline uitgeschakeld · verwerking loopt';
    if(pendingFailure)return pendingFailure;
    if(lc.kind==='reached')return 'Tesla gereed · doel vóór deadline gehaald';
    if(lc.kind==='missed_open')return `Deadline gemist · doel wordt nog afgemaakt${lc.amps?` · ${Math.round(lc.amps)} A`:''}${lc.remaining?` · ${fmtKWh(lc.remaining)} kWh resterend`:''}`;
    if(lc.kind==='missed_done')return 'Tesla gereed · deadline gemist';
    return '';
  }
  function populate(){
    const wrap=native();if(!wrap)return false;bind(wrap);reconcilePending();
    if(!applyDraft(wrap)){
      const source=effectiveCommand();
      const active=activeState(),currentSoc=Number(source?.currentSoc),targetSoc=Number(source?.targetSoc);
      const hasSoc=Number.isFinite(currentSoc)&&Number.isFinite(targetSoc)&&targetSoc>currentSoc;
      const maxA=Number(source?.maxA??coreTesla?.requested_a??11);
      const off=wrap.querySelector('input[name="tesla-native-mode"][value="off"]'),on=wrap.querySelector('input[name="tesla-native-mode"][value="on"]');
      if(off)off.checked=!active;if(on)on.checked=active;
      const fields=wrap.querySelector('.tesla-inline-fields');if(fields)fields.hidden=!active;
      const deadline=wrap.querySelector('.tesla-inline-deadline');if(deadline){deadline.min=nowLocalMinute();deadline.value=remoteDeadline();}
      const current=wrap.querySelector('.tesla-inline-current');if(current&&hasSoc)current.value=String(currentSoc);
      const target=wrap.querySelector('.tesla-inline-target');if(target&&hasSoc)target.value=String(targetSoc);
      const amps=wrap.querySelector('.tesla-inline-amps');if(amps)amps.value=String(Number.isFinite(maxA)&&maxA>=6&&maxA<=16?maxA:11);
    }
    const linked=Boolean(String(config?.worker_url||'').trim());
    const button=wrap.querySelector('.tesla-inline-save');if(button)button.disabled=!linked;
    const msg=wrap.querySelector('.tesla-inline-message');
    if(msg&&!draft){const text=statusText(lifecycle());msg.textContent=text||(linked?'':'Write-route niet gekoppeld');msg.dataset.state=pendingFailure?'error':(text?'info':'');}
    return true;
  }
  async function refresh(){
    if(loading)return;loading=true;
    try{await loadData();if(!populate())scheduleBootReady();}finally{loading=false;}
  }
  function scheduleBootReady(){
    if(native()){
      clearTimeout(bootTimer);bootTimer=null;bootAttempts=0;
      if(config||command||coreTesla||pendingCommand)populate();else refresh();
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
    if(d.active&&deadlinePast(d.deadline)){if(msg){msg.textContent='Deadline moet in de toekomst liggen.';msg.dataset.state='error';}return;}
    const pin=window.prompt('Voer de Tesla-control PIN in:');if(pin===null)return;
    if(button)button.disabled=true;if(msg)msg.textContent='Opslaan…';
    try{
      const r=await fetch(worker,{method:'POST',headers:{'Content-Type':'application/json','X-Tesla-Control-Pin':pin},body:JSON.stringify({active:d.active,deadline:d.active?d.deadline:'',currentSoc:d.active?currentSoc:null,targetSoc:d.active?targetSoc:null,maxA})});
      const j=await r.json().catch(()=>({}));if(!r.ok||!j.ok){const label=j.error==='deadline_not_in_future'?'Deadline moet in de toekomst liggen.':(j.error||`HTTP ${r.status}`);throw new Error(label);}
      command=j.command||command;
      pendingCommand=j.command||{active:d.active,deadline:d.active?d.deadline:'',currentSoc:d.active?currentSoc:null,targetSoc:d.active?targetSoc:null,maxA,requestedAt:new Date().toISOString()};
      pendingFailure='';draft=null;populate();setTimeout(refresh,0);
    }catch(e){if(msg){msg.textContent=`Opslaan mislukt: ${e.message||e}`;msg.dataset.state='error';}}finally{if(button)button.disabled=false;}
  }

  function lifecycleRefresh(){bootAttempts=0;scheduleBootReady();setTimeout(refresh,0);}
  document.addEventListener('liveenergyrendered',lifecycleRefresh);
  document.addEventListener('energycorev2state',e=>{coreTesla=e.detail?.raw?.tesla||coreTesla;reconcilePending();setTimeout(()=>{populate();},0);});
  document.addEventListener('DOMContentSwitch',lifecycleRefresh);
  document.addEventListener('appdatarefresh',lifecycleRefresh);
  document.addEventListener('DOMContentLoaded',lifecycleRefresh);
  if(document.readyState!=='loading')lifecycleRefresh();
})();