(function(){
  'use strict';
  const BASE='/homey-energy-manual/';
  const PANEL_ID='tesla-deadline-control';
  const HOST_CLASS='tesla-regulation';
  window.HomeEnergyFrontend=window.HomeEnergyFrontend||{};
  window.HomeEnergyFrontend.teslaDeadlineUi='2.8.99';
  let lastSnapshot=null,controlConfig=null,lastCommand=null;

  async function getJson(path){try{const r=await fetch(`${BASE}${path}?ts=${Date.now()}`,{cache:'no-store'});if(!r.ok)return null;return r.json();}catch(e){return null;}}
  async function refreshData(){
    const [phase,config,command]=await Promise.all([
      getJson('data/pv-phase-24h.json'),
      getJson('data/tesla-control-config.json'),
      getJson('data/tesla-deadline-command.json')
    ]);
    lastSnapshot=(phase?.samples||[]).at(-1)||null;
    controlConfig=config;
    lastCommand=command;
  }
  function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
  function fmtLatest(v){if(!v)return '—';const d=new Date(v);return Number.isNaN(d.getTime())?'—':d.toLocaleString('nl-NL',{weekday:'short',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});}
  function statusLabel(s){const map={GEEN_DEADLINE:'Geen deadline',WACHT_OP_PV:'Wacht op PV',OPPORTUNISTISCH:'Opportunistisch laden',DEADLINE_WACHT:'Wacht op geschikt laadmoment',DEADLINE_OPPORTUNISTISCH:'Opportunistisch laden',DEADLINE_CATCH_UP:'Catch-up actief',DEADLINE_GEMIST_CATCH_UP:'Deadline gepasseerd · catch-up actief',DOEL_GEHAALD:'Laaddoel gehaald',NIET_AANGESLOTEN:'Tesla niet aangesloten',CONFIG_FOUT:'Deadline-instelling ongeldig'};return map[String(s||'').toUpperCase()]||String(s||'Status nog niet gepubliceerd');}

  function ensureHost(){
    const root=document.getElementById('live-energy-flow');
    if(!root)return null;
    let host=root.querySelector(`.${HOST_CLASS}`);
    if(host)return host;
    const manager=Array.from(root.querySelectorAll('.energy-manager-panel')).find(panel=>!panel.classList.contains('heating-hybrid-panel'));
    if(!manager)return null;
    host=document.createElement('div');
    host.className=HOST_CLASS;
    host.dataset.teslaDeadlineHost='self-v2.8.99';
    manager.insertAdjacentElement('afterend',host);
    return host;
  }

  async function sendCommand(panel){
    const worker=String(controlConfig?.worker_url||'').trim();
    const message=panel.querySelector('.tesla-deadline-message');
    if(!worker){message.textContent='Cloudflare Worker is nog niet gekoppeld.';message.dataset.state='error';return;}
    const active=panel.querySelector('input[name="tesla-deadline-mode"]:checked')?.value==='on';
    const deadline=panel.querySelector('#tesla-deadline-datetime')?.value||'';
    const currentSoc=Number(panel.querySelector('#tesla-current-soc')?.value);
    const targetSoc=Number(panel.querySelector('#tesla-target-soc')?.value);
    const maxA=Number(panel.querySelector('#tesla-deadline-amps')?.value||11);
    if(active&&(!deadline||!Number.isFinite(currentSoc)||currentSoc<0||currentSoc>100||!Number.isFinite(targetSoc)||targetSoc<1||targetSoc>100||targetSoc<=currentSoc||maxA<6||maxA>16)){
      message.textContent='Controleer datum/tijd, huidige SOC, doel-SOC en maximale laadstroom.';message.dataset.state='error';return;
    }
    const pin=window.prompt('Voer de Tesla-control PIN in om deze wijziging naar Homey te sturen:');
    if(pin===null)return;
    const button=panel.querySelector('.tesla-deadline-save');button.disabled=true;message.textContent='Opdracht wordt veilig aangeboden…';message.dataset.state='busy';
    try{
      const r=await fetch(worker,{method:'POST',headers:{'Content-Type':'application/json','X-Tesla-Control-Pin':pin},body:JSON.stringify({active,deadline:active?deadline:'',currentSoc:active?currentSoc:null,targetSoc:active?targetSoc:null,maxA})});
      const j=await r.json().catch(()=>({}));
      if(!r.ok||!j.ok)throw new Error(j.error||`HTTP ${r.status}`);
      lastCommand=j.command||lastCommand;
      message.textContent=active?`Deadline opgeslagen: ${currentSoc}% → ${targetSoc}%. Homey neemt de opdracht binnen circa 2 minuten over.`:'Deadline uitgeschakeld. Homey neemt de opdracht binnen circa 2 minuten over.';message.dataset.state='ok';
    }catch(e){message.textContent=`Opslaan mislukt: ${e.message||e}`;message.dataset.state='error';}
    finally{button.disabled=false;}
  }

  function renderPanel(){
    const host=ensureHost();
    if(!host||document.getElementById(PANEL_ID))return false;
    const ps=lastSnapshot||{};
    const snapHasActive=typeof ps.evDeadlineActive==='boolean'||typeof ps.EVDeadlineActive==='boolean';
    const snapActive=ps.evDeadlineActive===true||ps.EVDeadlineActive===true;
    const cmdActive=lastCommand?.active===true;
    const publishedActive=snapHasActive?snapActive:cmdActive;
    const deadline=(ps.evDeadlineTime||ps.EVDeadlineTime||lastCommand?.deadline||'');
    const maxA=Number(ps.evMaxA??ps.EVMaxA??lastCommand?.maxA??11);
    const currentSoc=Number(lastCommand?.currentSoc);
    const targetSoc=Number(lastCommand?.targetSoc);
    const hasSoc=Number.isFinite(currentSoc)&&Number.isFinite(targetSoc)&&targetSoc>currentSoc;
    const latest=ps.evLatestStart||ps.EVLatestStart||'';
    const status=ps.evDeadlineStatus||ps.EVDeadlineStatus||'';
    const linked=Boolean(String(controlConfig?.worker_url||'').trim());
    const source=snapHasActive?'Homey':'laatste website-opdracht';
    const panel=document.createElement('div');panel.id=PANEL_ID;panel.className='tesla-deadline-control';panel.innerHTML=`<div class="tesla-deadline-head"><div><small>LAADREGELING</small><strong>Tesla deadline</strong></div><div class="tesla-deadline-mode" role="radiogroup" aria-label="Tesla deadline modus"><label><input type="radio" name="tesla-deadline-mode" value="off" ${publishedActive?'':'checked'}> Geen deadline</label><label><input type="radio" name="tesla-deadline-mode" value="on" ${publishedActive?'checked':''}> Deadline actief</label></div></div><div class="tesla-deadline-fields" ${publishedActive?'':'hidden'}><label><span>Gereed uiterlijk</span><input id="tesla-deadline-datetime" type="datetime-local" value="${esc(deadline&&/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(deadline)?deadline.replace(' ','T').slice(0,16):'')}"></label><label><span>Huidige SOC</span><div class="tesla-input-unit"><input id="tesla-current-soc" type="number" min="0" max="99" step="1" value="${hasSoc?currentSoc:''}" placeholder="71"><b>%</b></div></label><label><span>Doel-SOC</span><div class="tesla-input-unit"><input id="tesla-target-soc" type="number" min="1" max="100" step="1" value="${hasSoc?targetSoc:''}" placeholder="90"><b>%</b></div></label><label><span>Max. laadstroom</span><div class="tesla-input-unit"><input id="tesla-deadline-amps" type="number" min="6" max="16" step="1" value="${Number.isFinite(maxA)&&maxA>0?maxA:11}"><b>A</b></div></label></div><div class="tesla-deadline-actions"><button type="button" class="tesla-deadline-save" ${linked?'':'disabled'}>${publishedActive?'Wijziging opslaan':'Instelling opslaan'}</button><span class="tesla-deadline-linkstate">${linked?'Veilige write-route gereed':'Worker nog niet gekoppeld'}</span></div><div class="tesla-deadline-runtime" ${publishedActive?'':'hidden'}><div><span>Status</span><strong>${esc(statusLabel(status))}</strong></div><div><span>SOC-doel</span><strong>${hasSoc?`${currentSoc}% → ${targetSoc}%`:'Opnieuw invoeren'}</strong></div><div><span>Uiterlijk starten</span><strong>${esc(fmtLatest(latest))}</strong></div></div><p class="tesla-deadline-message" aria-live="polite"></p><p class="tesla-deadline-note">${publishedActive?`Deadline actief volgens ${source}. ${hasSoc?`SOC ingevoerd ${fmtLatest(lastCommand?.socEnteredAt||lastCommand?.requestedAt)}.`:'Deze bestaande deadline gebruikt nog het oude kWh-formaat; voer bij een volgende wijziging huidige SOC en doel-SOC in.'}`:'Zonder deadline blijft Tesla opportunistisch laden en kan hij als exportbuffer worden gebruikt.'} Intern zet de beveiligde Worker het SOC-verschil om naar benodigde laadenergie met de huidige praktijkkalibratie; de gebruiker stuurt alleen op percentages.</p>`;
    host.prepend(panel);
    const radios=panel.querySelectorAll('input[name="tesla-deadline-mode"]'),fields=panel.querySelector('.tesla-deadline-fields'),runtime=panel.querySelector('.tesla-deadline-runtime');radios.forEach(r=>r.addEventListener('change',()=>{const on=panel.querySelector('input[name="tesla-deadline-mode"]:checked')?.value==='on';fields.hidden=!on;runtime.hidden=!on;}));panel.querySelector('.tesla-deadline-save')?.addEventListener('click',()=>sendCommand(panel));
    return true;
  }

  async function refresh(){await refreshData();document.getElementById(PANEL_ID)?.remove();renderPanel();}
  function start(){
    refresh();
    const root=document.getElementById('live-energy-flow');
    if(root&&!root.dataset.teslaDeadlineUiObserver){
      root.dataset.teslaDeadlineUiObserver='2.8.99';
      new MutationObserver(()=>{if(!document.getElementById(PANEL_ID))renderPanel();}).observe(root,{childList:true,subtree:true});
    }
    [150,500,1200,2500].forEach(ms=>setTimeout(()=>{if(!document.getElementById(PANEL_ID))renderPanel();},ms));
  }
  document.addEventListener('DOMContentLoaded',start);
  document.addEventListener('DOMContentSwitch',start);
  if(document.readyState!=='loading')start();
})();
