(function(){
  'use strict';
  const BASE='/homey-energy-manual/';
  window.HomeEnergyFrontend=window.HomeEnergyFrontend||{};
  window.HomeEnergyFrontend.emsSettingsController='1.0.0';

  let command=null,config=null,core=null,loading=false;

  async function getJson(path){
    try{
      const r=await fetch(`${BASE}${path}?ts=${Date.now()}`,{cache:'no-store'});
      return r.ok?await r.json():null;
    }catch(_){return null;}
  }

  function actualHotWaterSource(){
    const mode=core?.hot_water?.mode;
    if(mode===true)return 'BOILER';
    if(mode===false)return 'CV';
    return null;
  }

  function template(){
    return `<div class="energy-manager-panel ems-settings-panel" data-ems-settings>
      <div class="energy-manager-title"><strong>EMS instellingen</strong><span>canonieke gebruikerskeuzes</span></div>
      <div class="ems-settings-grid">
        <label><small>ENERGIECONTRACT</small><select data-ems-contract><option value="FIXED">Vast</option><option value="DYNAMIC">Dynamisch</option></select><span>Stuurt welke prijscontext voor economische optimalisatie geldig is.</span></label>
        <label><small>WARMWATERBRON</small><select data-ems-hot-water><option value="BOILER">Boiler</option><option value="CV">CV</option></select><span>Operationele bronkeuze; boilercontrol is alleen toegestaan bij Boiler.</span></label>
        <div class="ems-settings-actions"><button type="button" data-ems-save disabled>Instellingen opslaan</button><span data-ems-message aria-live="polite">Instellingen laden…</span></div>
      </div>
    </div>`;
  }

  function ensurePanel(){
    const root=document.getElementById('live-energy-flow');
    if(!root)return null;
    let panel=root.querySelector('[data-ems-settings]');
    if(panel)return panel;
    root.insertAdjacentHTML('beforeend',template());
    panel=root.querySelector('[data-ems-settings]');
    panel?.querySelector('[data-ems-save]')?.addEventListener('click',()=>save(panel));
    return panel;
  }

  function populate(){
    const panel=ensurePanel();if(!panel)return;
    const contract=panel.querySelector('[data-ems-contract]');
    const hot=panel.querySelector('[data-ems-hot-water]');
    const button=panel.querySelector('[data-ems-save]');
    const msg=panel.querySelector('[data-ems-message]');
    const contractType=String(command?.contractType||'FIXED').toUpperCase();
    const requestedHot=String(command?.hotWaterSource||actualHotWaterSource()||'BOILER').toUpperCase();
    if(contract)contract.value=['FIXED','DYNAMIC'].includes(contractType)?contractType:'FIXED';
    if(hot)hot.value=['BOILER','CV'].includes(requestedHot)?requestedHot:'BOILER';
    const linked=Boolean(String(config?.worker_url||'').trim());
    if(button)button.disabled=!linked;
    if(msg){
      const actual=actualHotWaterSource();
      if(actual&&actual!==requestedHot){
        msg.textContent=`Opdracht ${requestedHot} opgeslagen · Homey meldt nog ${actual}`;
        msg.dataset.state='pending';
      }else{
        msg.textContent=linked?`Actief: ${contractType} · warm water ${actual||requestedHot}`:'Write-route niet gekoppeld';
        msg.dataset.state=linked?'ok':'error';
      }
    }
  }

  async function load(){
    if(loading)return;loading=true;
    try{
      const [cmd,cfg,state]=await Promise.all([
        getJson('data/ems-settings-command.json'),
        getJson('data/tesla-control-config.json'),
        getJson('data/energy-state-v2.json')
      ]);
      command=cmd||command;config=cfg||config;core=state||core;populate();
    }finally{loading=false;}
  }

  async function save(panel){
    const worker=String(config?.worker_url||'').trim();
    const contractType=panel.querySelector('[data-ems-contract]')?.value||'FIXED';
    const hotWaterSource=panel.querySelector('[data-ems-hot-water]')?.value||'BOILER';
    const button=panel.querySelector('[data-ems-save]');
    const msg=panel.querySelector('[data-ems-message]');
    if(!worker){if(msg)msg.textContent='Write-route niet gekoppeld';return;}
    const pin=window.prompt('Voer de control PIN in:');if(pin===null)return;
    if(button)button.disabled=true;if(msg)msg.textContent='Opslaan…';
    try{
      const r=await fetch(worker,{method:'POST',headers:{'Content-Type':'application/json','X-Tesla-Control-Pin':pin},body:JSON.stringify({kind:'ems_settings',contractType,hotWaterSource})});
      const j=await r.json().catch(()=>({}));
      if(!r.ok||!j.ok)throw new Error(j.error||`HTTP ${r.status}`);
      command=j.command||command;
      if(msg){msg.textContent='Opgeslagen · wacht op Homey bevestiging';msg.dataset.state='pending';}
      setTimeout(load,1000);
    }catch(e){
      if(msg){msg.textContent=`Opslaan mislukt: ${e.message||e}`;msg.dataset.state='error';}
    }finally{if(button)button.disabled=false;}
  }

  function refresh(){setTimeout(load,0);}
  document.addEventListener('liveenergyrendered',refresh);
  document.addEventListener('energycorev2state',e=>{core=e.detail?.raw||core;populate();});
  document.addEventListener('DOMContentSwitch',refresh);
  document.addEventListener('appdatarefresh',refresh);
  document.addEventListener('DOMContentLoaded',refresh);
  if(document.readyState!=='loading')refresh();
})();
