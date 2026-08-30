(function(){
  'use strict';
  const BASE='/homey-energy-manual/';
  window.HomeEnergyFrontend=window.HomeEnergyFrontend||{};
  window.HomeEnergyFrontend.emsSettingsController='1.1.2';

  let command=null,config=null,core=null,loading=false,saving=false,commandReady=false;

  async function getJson(path){
    try{
      const r=await fetch(`${BASE}${path}?ts=${Date.now()}`,{cache:'no-store'});
      return r.ok?await r.json():null;
    }catch(_){return null;}
  }

  function commandTime(cmd){
    const t=Date.parse(String(cmd?.requestedAt||''));
    return Number.isFinite(t)?t:0;
  }

  function acceptCommand(cmd){
    if(!validCommand(cmd))return false;
    if(!command||!validCommand(command))return true;
    const incoming=commandTime(cmd),current=commandTime(command);
    if(incoming&&current&&incoming<current)return false;
    return true;
  }

  function actualHotWaterSource(){
    const mode=core?.hot_water?.mode;
    if(mode===true)return 'BOILER';
    if(mode===false)return 'CV';
    return null;
  }

  function validCommand(cmd){
    const contractType=String(cmd?.contractType||'').toUpperCase();
    const hotWaterSource=String(cmd?.hotWaterSource||'').toUpperCase();
    return cmd?.schema===1&&cmd?.kind==='ems_settings'&&['FIXED','DYNAMIC'].includes(contractType)&&['BOILER','CV'].includes(hotWaterSource);
  }

  function routeReady(){
    return Boolean(String(config?.worker_url||'').trim()) && config?.ems_settings_supported===true;
  }

  function template(){
    return `<div class="energy-manager-panel ems-settings-panel" data-ems-settings>
      <div class="energy-manager-title"><strong>EMS instellingen</strong><span>canonieke gebruikerskeuzes</span></div>
      <div class="ems-settings-grid">
        <label><small>ENERGIECONTRACT</small><select data-ems-contract><option value="FIXED">Vast</option><option value="DYNAMIC">Dynamisch</option></select><span>Wijziging wordt direct als EMS-opdracht aangeboden na PIN-controle.</span></label>
        <label><small>WARMWATERBRON</small><select data-ems-hot-water><option value="BOILER">Boiler</option><option value="CV">CV</option></select><span>Operationele bronkeuze; boilercontrol is alleen toegestaan bij Boiler.</span></label>
        <div class="ems-settings-actions"><span data-ems-message aria-live="polite">Instellingen laden…</span></div>
      </div>
    </div>`;
  }

  function bind(panel){
    if(!panel||panel.dataset.bound==='1.1.2')return;
    panel.dataset.bound='1.1.2';
    panel.querySelector('[data-ems-contract]')?.addEventListener('change',()=>save(panel));
    panel.querySelector('[data-ems-hot-water]')?.addEventListener('change',()=>save(panel));
  }

  function ensurePanel(){
    const root=document.getElementById('live-energy-flow');
    if(!root)return null;
    let panel=root.querySelector('[data-ems-settings]');
    if(!panel){root.insertAdjacentHTML('beforeend',template());panel=root.querySelector('[data-ems-settings]');}
    bind(panel);
    return panel;
  }

  function setEnabled(panel,enabled){
    panel.querySelectorAll('[data-ems-contract],[data-ems-hot-water]').forEach(el=>el.disabled=!enabled);
  }

  function populate(){
    const panel=ensurePanel();if(!panel)return;
    const contract=panel.querySelector('[data-ems-contract]');
    const hot=panel.querySelector('[data-ems-hot-water]');
    const msg=panel.querySelector('[data-ems-message]');

    if(!commandReady||!validCommand(command)){
      setEnabled(panel,false);
      if(msg&&!saving){msg.textContent='Canonieke EMS-instellingen niet geladen · wijzigen geblokkeerd';msg.dataset.state='error';}
      return;
    }

    const contractType=String(command.contractType).toUpperCase();
    const requestedHot=String(command.hotWaterSource).toUpperCase();
    if(!saving){
      if(contract)contract.value=contractType;
      if(hot)hot.value=requestedHot;
    }
    const linked=routeReady();setEnabled(panel,linked&&!saving);
    if(msg&&!saving){
      const actual=actualHotWaterSource();
      if(!linked){msg.textContent='Selector gereed · write-route nog niet vrijgegeven';msg.dataset.state='pending';}
      else if(actual&&actual!==requestedHot){msg.textContent=`Opdracht ${requestedHot} opgeslagen · Homey meldt nog ${actual}`;msg.dataset.state='pending';}
      else{msg.textContent=`Actief: ${contractType} · warm water ${actual||requestedHot}`;msg.dataset.state='ok';}
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
      // GitHub Pages can briefly serve an older command after a successful Worker write.
      // Never let an older requestedAt roll an already accepted newer command back in the UI.
      if(acceptCommand(cmd)){command=cmd;commandReady=true;}
      config=cfg||config;core=state||core;populate();
    }finally{loading=false;}
  }

  async function save(panel){
    if(saving)return;
    const msg=panel.querySelector('[data-ems-message]');
    if(!commandReady||!validCommand(command)){
      if(msg){msg.textContent='Opslaan geblokkeerd: canonieke EMS-instellingen zijn niet geladen';msg.dataset.state='error';}
      setEnabled(panel,false);
      return;
    }
    const worker=String(config?.worker_url||'').trim();
    const contractType=String(panel.querySelector('[data-ems-contract]')?.value||'').toUpperCase();
    const hotWaterSource=String(panel.querySelector('[data-ems-hot-water]')?.value||'').toUpperCase();
    if(!['FIXED','DYNAMIC'].includes(contractType)||!['BOILER','CV'].includes(hotWaterSource)){
      if(msg){msg.textContent='Opslaan geblokkeerd: ongeldige selectorstatus';msg.dataset.state='error';}
      populate();return;
    }
    if(!routeReady()){if(msg)msg.textContent='Write-route nog niet vrijgegeven';populate();return;}
    const pin=window.prompt('Voer de Tesla-control PIN in:');
    if(pin===null){populate();return;}
    saving=true;setEnabled(panel,false);if(msg){msg.textContent='Opslaan…';msg.dataset.state='pending';}
    try{
      const r=await fetch(worker,{method:'POST',headers:{'Content-Type':'application/json','X-Tesla-Control-Pin':pin},body:JSON.stringify({kind:'ems_settings',contractType,hotWaterSource})});
      const j=await r.json().catch(()=>({}));
      if(!r.ok||!j.ok)throw new Error(j.error||`HTTP ${r.status}`);
      if(acceptCommand(j.command)){command=j.command;commandReady=true;}
      if(msg){msg.textContent='Opgeslagen · wacht op Homey bevestiging';msg.dataset.state='pending';}
      setTimeout(load,1000);
    }catch(e){
      if(msg){msg.textContent=`Opslaan mislukt: ${e.message||e}`;msg.dataset.state='error';}
      setTimeout(populate,1200);
    }finally{saving=false;setEnabled(panel,routeReady()&&commandReady);}
  }

  function refresh(){setTimeout(load,0);}
  document.addEventListener('liveenergyrendered',refresh);
  document.addEventListener('energycorev2state',e=>{core=e.detail?.raw||core;populate();});
  document.addEventListener('DOMContentSwitch',refresh);
  document.addEventListener('appdatarefresh',refresh);
  document.addEventListener('DOMContentLoaded',refresh);
  if(document.readyState!=='loading')refresh();
})();
