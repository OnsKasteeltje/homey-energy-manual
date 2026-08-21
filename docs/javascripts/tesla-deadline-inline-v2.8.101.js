(function(){
  'use strict';
  const BASE='/homey-energy-manual/';
  const MARK='tesla-deadline-inline-v2.8.101';
  window.HomeEnergyFrontend=window.HomeEnergyFrontend||{};
  window.HomeEnergyFrontend.teslaDeadlineInline='2.8.101';

  let config=null,command=null,snapshot=null,refreshing=false;

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

  function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
  function card(){
    const manager=document.querySelector('#live-energy-flow .energy-manager-panel:not(.heating-hybrid-panel)');
    if(!manager)return null;
    return Array.from(manager.querySelectorAll('.energy-manager-grid > div')).find(el=>el.querySelector('small')?.textContent.trim()==='TESLA')||null;
  }
  function activeState(){
    const ps=snapshot||{};
    if(typeof ps.evDeadlineActive==='boolean')return ps.evDeadlineActive;
    if(typeof ps.EVDeadlineActive==='boolean')return ps.EVDeadlineActive;
    return command?.active===true;
  }
  function deadlineValue(){
    const raw=snapshot?.evDeadlineTime||snapshot?.EVDeadlineTime||command?.deadline||'';
    return /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(raw)?raw.replace(' ','T').slice(0,16):'';
  }

  function render(){
    const host=card();
    if(!host)return false;
    host.querySelector(`.${MARK}`)?.remove();
    const active=activeState();
    const currentSoc=Number(command?.currentSoc);
    const targetSoc=Number(command?.targetSoc);
    const hasSoc=Number.isFinite(currentSoc)&&Number.isFinite(targetSoc)&&targetSoc>currentSoc;
    const maxA=Number(snapshot?.evMaxA??snapshot?.EVMaxA??command?.maxA??11);
    const linked=Boolean(String(config?.worker_url||'').trim());
    const wrap=document.createElement('div');
    wrap.className=MARK;
    wrap.innerHTML=`<div class="tesla-inline-divider"></div><div class="tesla-inline-mode"><label><input type="radio" name="tesla-inline-mode" value="off" ${active?'':'checked'}> Geen deadline</label><label><input type="radio" name="tesla-inline-mode" value="on" ${active?'checked':''}> Deadline actief</label></div><div class="tesla-inline-fields" ${active?'':'hidden'}><label><span>Gereed uiterlijk</span><input class="tesla-inline-deadline" type="datetime-local" value="${esc(deadlineValue())}"></label><label><span>Huidige SOC</span><input class="tesla-inline-current" type="number" min="0" max="99" step="1" value="${hasSoc?currentSoc:''}" placeholder="71"></label><label><span>Doel-SOC</span><input class="tesla-inline-target" type="number" min="1" max="100" step="1" value="${hasSoc?targetSoc:''}" placeholder="90"></label><label><span>Max. laadstroom</span><input class="tesla-inline-amps" type="number" min="6" max="16" step="1" value="${Number.isFinite(maxA)?maxA:11}"></label></div><button type="button" class="tesla-inline-save" ${linked?'':'disabled'}>Deadline opslaan</button><span class="tesla-inline-message" aria-live="polite">${linked?'':'Write-route niet gekoppeld'}</span>`;
    host.appendChild(wrap);
    const fields=wrap.querySelector('.tesla-inline-fields');
    wrap.querySelectorAll('input[name="tesla-inline-mode"]').forEach(r=>r.addEventListener('change',()=>{fields.hidden=wrap.querySelector('input[name="tesla-inline-mode"]:checked')?.value!=='on';}));
    wrap.querySelector('.tesla-inline-save')?.addEventListener('click',()=>save(wrap));
    return true;
  }

  async function save(wrap){
    const worker=String(config?.worker_url||'').trim();
    const msg=wrap.querySelector('.tesla-inline-message');
    const button=wrap.querySelector('.tesla-inline-save');
    const active=wrap.querySelector('input[name="tesla-inline-mode"]:checked')?.value==='on';
    const deadline=wrap.querySelector('.tesla-inline-deadline')?.value||'';
    const currentSoc=Number(wrap.querySelector('.tesla-inline-current')?.value);
    const targetSoc=Number(wrap.querySelector('.tesla-inline-target')?.value);
    const maxA=Number(wrap.querySelector('.tesla-inline-amps')?.value||11);
    if(active&&(!deadline||!Number.isFinite(currentSoc)||currentSoc<0||currentSoc>99||!Number.isFinite(targetSoc)||targetSoc<1||targetSoc>100||targetSoc<=currentSoc||maxA<6||maxA>16)){
      msg.textContent='Controleer deadline, SOC en laadstroom.';return;
    }
    const pin=window.prompt('Voer de Tesla-control PIN in:');
    if(pin===null)return;
    button.disabled=true;msg.textContent='Opslaan…';
    try{
      const r=await fetch(worker,{method:'POST',headers:{'Content-Type':'application/json','X-Tesla-Control-Pin':pin},body:JSON.stringify({active,deadline:active?deadline:'',currentSoc:active?currentSoc:null,targetSoc:active?targetSoc:null,maxA})});
      const j=await r.json().catch(()=>({}));
      if(!r.ok||!j.ok)throw new Error(j.error||`HTTP ${r.status}`);
      command=j.command||command;
      msg.textContent=active?'Deadline opgeslagen':'Deadline uitgeschakeld';
    }catch(e){msg.textContent=`Opslaan mislukt: ${e.message||e}`;}
    finally{button.disabled=false;}
  }

  async function refresh(){
    if(refreshing)return;
    refreshing=true;
    try{await loadData();render();}finally{refreshing=false;}
  }
  function start(){
    refresh();
    const root=document.getElementById('live-energy-flow');
    if(root&&!root.dataset.teslaDeadlineInlineObserver){
      root.dataset.teslaDeadlineInlineObserver='2.8.101';
      new MutationObserver(()=>{if(!card()?.querySelector(`.${MARK}`))render();}).observe(root,{childList:true,subtree:true});
    }
  }
  document.addEventListener('DOMContentLoaded',start);
  document.addEventListener('DOMContentSwitch',start);
  document.addEventListener('energycorev2state',()=>setTimeout(render,0));
  if(document.readyState!=='loading')start();
})();
