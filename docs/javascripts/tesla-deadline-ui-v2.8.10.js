(function(){
  const BASE='/homey-energy-manual/';
  const PANEL_ID='tesla-deadline-control';
  let lastSnapshot=null;

  async function getSnapshot(){
    try{
      const r=await fetch(`${BASE}data/pv-phase-24h.json?ts=${Date.now()}`,{cache:'no-store'});
      if(!r.ok)return null;
      const j=await r.json();
      return (j.samples||[]).at(-1)||null;
    }catch(e){return null;}
  }

  function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
  function fmtDateTime(v){
    if(!v)return '';
    const d=new Date(v);
    if(Number.isNaN(d.getTime()))return String(v);
    return d.toLocaleString('nl-NL',{weekday:'short',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
  }
  function fmtLatest(v){
    if(!v)return '—';
    const d=new Date(v);
    return Number.isNaN(d.getTime())?'—':d.toLocaleString('nl-NL',{weekday:'short',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
  }
  function statusLabel(s){
    const map={
      GEEN_DEADLINE:'Geen deadline',WACHT_OP_PV:'Wacht op PV',OPPORTUNISTISCH:'Opportunistisch laden',
      DEADLINE_WACHT:'Wacht op geschikt laadmoment',DEADLINE_OPPORTUNISTISCH:'Opportunistisch laden',
      DEADLINE_CATCH_UP:'Catch-up actief',DEADLINE_GEMIST_CATCH_UP:'Deadline gepasseerd · catch-up actief',
      DOEL_GEHAALD:'Laaddoel gehaald',NIET_AANGESLOTEN:'Tesla niet aangesloten',CONFIG_FOUT:'Deadline-instelling ongeldig'
    };
    return map[String(s||'').toUpperCase()]||String(s||'Status nog niet gepubliceerd');
  }

  function renderPanel(){
    const host=document.querySelector('.tesla-regulation');
    if(!host)return;
    if(document.getElementById(PANEL_ID))return;

    const ps=lastSnapshot||{};
    const publishedActive=ps.evDeadlineActive===true || ps.EVDeadlineActive===true;
    const deadline=ps.evDeadlineTime||ps.EVDeadlineTime||'';
    const goal=Number(ps.evGoalKWh??ps.EVGoalKWh??20);
    const maxA=Number(ps.evMaxA??ps.EVMaxA??11);
    const remaining=Number(ps.evRemainingKWh??ps.EVRemainingKWh);
    const latest=ps.evLatestStart||ps.EVLatestStart||'';
    const status=ps.evDeadlineStatus||ps.EVDeadlineStatus||'';

    const panel=document.createElement('div');
    panel.id=PANEL_ID;
    panel.className='tesla-deadline-control';
    panel.innerHTML=`
      <div class="tesla-deadline-head">
        <div>
          <small>LAADREGELING</small>
          <strong>Tesla deadline</strong>
        </div>
        <div class="tesla-deadline-mode" role="radiogroup" aria-label="Tesla deadline modus">
          <label><input type="radio" name="tesla-deadline-mode" value="off" ${publishedActive?'':'checked'}> Geen deadline</label>
          <label><input type="radio" name="tesla-deadline-mode" value="on" ${publishedActive?'checked':''}> Deadline actief</label>
        </div>
      </div>
      <div class="tesla-deadline-fields" ${publishedActive?'':'hidden'}>
        <label><span>Gereed uiterlijk</span><input id="tesla-deadline-datetime" type="datetime-local" value="${esc(deadline && /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(deadline)?deadline.replace(' ','T').slice(0,16):'')}"></label>
        <label><span>Minimaal laden</span><div class="tesla-input-unit"><input id="tesla-deadline-kwh" type="number" min="1" max="75" step="1" value="${Number.isFinite(goal)&&goal>0?goal:20}"><b>kWh</b></div></label>
        <label><span>Max. laadstroom</span><div class="tesla-input-unit"><input id="tesla-deadline-amps" type="number" min="6" max="16" step="1" value="${Number.isFinite(maxA)&&maxA>0?maxA:11}"><b>A</b></div></label>
        <button type="button" class="tesla-deadline-save" disabled title="Veilige schrijfroute naar Homey is nog niet beschikbaar">Deadline opslaan</button>
      </div>
      <div class="tesla-deadline-runtime" ${publishedActive?'':'hidden'}>
        <div><span>Status</span><strong>${esc(statusLabel(status))}</strong></div>
        <div><span>Nog te laden</span><strong>${Number.isFinite(remaining)?remaining.toFixed(1)+' kWh':'—'}</strong></div>
        <div><span>Uiterlijk starten</span><strong>${esc(fmtLatest(latest))}</strong></div>
      </div>
      <p class="tesla-deadline-note">${publishedActive?`Homey publiceert momenteel een actieve deadline${deadline?` voor ${esc(fmtDateTime(deadline))}`:''}.`:'Zonder deadline blijft Tesla opportunistisch laden en kan hij als exportbuffer worden gebruikt.'} <span>Instellen vanaf deze publieke website wordt pas geactiveerd zodra een veilige Homey write-route beschikbaar is.</span></p>`;

    host.prepend(panel);
    const radios=panel.querySelectorAll('input[name="tesla-deadline-mode"]');
    const fields=panel.querySelector('.tesla-deadline-fields');
    const runtime=panel.querySelector('.tesla-deadline-runtime');
    const note=panel.querySelector('.tesla-deadline-note');
    radios.forEach(r=>r.addEventListener('change',()=>{
      const on=panel.querySelector('input[name="tesla-deadline-mode"]:checked')?.value==='on';
      fields.hidden=!on;
      runtime.hidden=!on;
      note.firstChild.textContent=on?'Vul het gewenste laadvenster in. ':'Zonder deadline blijft Tesla opportunistisch laden en kan hij als exportbuffer worden gebruikt. ';
    }));
  }

  async function refresh(){
    lastSnapshot=await getSnapshot();
    const old=document.getElementById(PANEL_ID);
    if(old)old.remove();
    renderPanel();
  }

  function start(){
    refresh();
    const root=document.getElementById('live-energy-flow');
    if(root){new MutationObserver(()=>{if(!document.getElementById(PANEL_ID))renderPanel();}).observe(root,{childList:true,subtree:true});}
  }
  document.addEventListener('DOMContentLoaded',start);
  document.addEventListener('DOMContentSwitch',start);
})();
