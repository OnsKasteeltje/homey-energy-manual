(function(){
  'use strict';
  // v2.0.6: voorkom misleidende oude Tesla/Core-state direct na een nieuwe website-opdracht.
  // Leest uitsluitend de gepubliceerde GitHub command-state; geen extra Homey-devicecalls.
  window.HomeEnergyFrontend=window.HomeEnergyFrontend||{};
  window.HomeEnergyFrontend.homeArchitectureTeslaPending='2.0.6';

  const BASE='/homey-energy-manual/';
  const RECENT_MS=10*60*1000;
  let coreDetail=null,lastCommand=null,timer=null,loading=false;

  const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const fmtKWh=v=>Number(v).toLocaleString('nl-NL',{maximumFractionDigits:2});
  const fmtTime=value=>{const s=String(value||'').trim();if(!s)return '';const local=s.match(/T(\d{2}):(\d{2})(?::\d{2})?$/);if(local&&!/[zZ]|[+-]\d\d:?\d\d$/.test(s))return `${local[1]}:${local[2]}`;const d=new Date(s);return Number.isFinite(d.getTime())?new Intl.DateTimeFormat('nl-NL',{timeZone:'Europe/Amsterdam',hour:'2-digit',minute:'2-digit',hour12:false}).format(d):'';};
  const norm=s=>String(s||'').trim().replace(' ','T').slice(0,16);

  function teslaGoal(){
    const root=document.getElementById('home-architecture');
    if(!root)return null;
    return [...root.querySelectorAll('.ha-goal')].find(el=>el.querySelector('strong')?.textContent.trim()==='Tesla laden')||null;
  }

  function pendingState(cmd,detail){
    if(!cmd||!detail?.raw)return null;
    const t=detail.raw.tesla||{};
    const requestedAt=Date.parse(String(cmd.requestedAt||cmd.socEnteredAt||''));
    if(!Number.isFinite(requestedAt)||Date.now()-requestedAt>RECENT_MS||requestedAt-Date.now()>60000)return null;
    const commandActive=cmd.active===true,coreActive=t.deadline_active===true;
    const commandDeadline=norm(cmd.deadline),coreDeadline=norm(t.deadline_at);
    const mismatch=commandActive!==coreActive||(commandActive&&commandDeadline&&commandDeadline!==coreDeadline);
    if(!mismatch)return null;
    return {cmd,commandActive};
  }

  function apply(){
    const goal=teslaGoal(),pending=pendingState(lastCommand,coreDetail);
    if(!goal||!pending)return false;
    const state=goal.querySelector('.ha-goal-state'),small=goal.querySelector('small');
    if(state){state.classList.remove('ok','off');state.classList.add('warn');state.textContent=pending.commandActive?'Nieuwe deadline wordt verwerkt':'Deadline uitschakelen wordt verwerkt';}
    if(small){
      if(pending.commandActive){
        const c=pending.cmd,time=fmtTime(c.deadline),soc=(Number.isFinite(Number(c.currentSoc))&&Number.isFinite(Number(c.targetSoc)))?`${Number(c.currentSoc)}→${Number(c.targetSoc)}%`:'';
        const bits=[time?`Deadline ${time}`:'',soc,Number.isFinite(Number(c.goalKWh))?`${fmtKWh(c.goalKWh)} kWh`:'' ].filter(Boolean);
        small.textContent=bits.join(' · ');
      }else small.textContent='Nieuwe opdracht bevestigd; wachten op Homey/Core-publicatie';
    }
    goal.dataset.teslaCommandPending='true';
    return true;
  }

  async function loadCommand(){
    if(loading)return;loading=true;
    try{
      const r=await fetch(`${BASE}data/tesla-deadline-command.json?ts=${Date.now()}`,{cache:'no-store'});
      if(r.ok)lastCommand=await r.json();
      apply();
    }catch(_){/* Core-weergave blijft leidend wanneer command niet leesbaar is. */}
    finally{loading=false;}
  }

  function refresh(detail){if(detail)coreDetail=detail;setTimeout(()=>{apply();loadCommand();},0);}
  document.addEventListener('energycorev2state',e=>refresh(e.detail));
  document.addEventListener('appdatarefresh',()=>refresh(coreDetail));
  document.addEventListener('DOMContentSwitch',()=>refresh(coreDetail));
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')refresh(coreDetail);});
  document.addEventListener('DOMContentLoaded',()=>refresh(window.EnergyCoreV2?.state||coreDetail));
  if(document.readyState!=='loading')refresh(window.EnergyCoreV2?.state||coreDetail);
  timer=setInterval(()=>{if(document.visibilityState==='visible'&&document.getElementById('home-architecture'))loadCommand();},10000);
  window.addEventListener('beforeunload',()=>clearInterval(timer),{once:true});
})();
