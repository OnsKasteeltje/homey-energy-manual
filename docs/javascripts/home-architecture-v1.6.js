(function(){
  // Homepage architecture v1.6: resilient Tesla deadline status overlay with SOC-based user goal.
  const DATA_BASE='/homey-energy-manual/data/';
  const script=document.createElement('script');
  script.src='/homey-energy-manual/javascripts/home-architecture-v1.js';
  let commandCache=null,statusCache=null,phaseCache=null,enhanceTimer=null;

  async function getJson(name){
    const r=await fetch(`${DATA_BASE}${name}?ts=${Date.now()}`,{cache:'no-store'});
    if(!r.ok) throw new Error(`${name}: ${r.status}`);
    return r.json();
  }
  function fmtDeadline(v){
    if(!v) return '—';
    const d=new Date(String(v).replace(' ','T'));
    return Number.isNaN(d.getTime())?String(v):d.toLocaleString('nl-NL',{weekday:'short',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
  }
  function runtimeLabel(s){
    const map={GEEN_DEADLINE:'Opportunistisch',WACHT_OP_PV:'Wacht op PV',OPPORTUNISTISCH:'Opportunistisch laden',DEADLINE_WACHT:'Wacht op geschikt laadmoment',DEADLINE_OPPORTUNISTISCH:'Opportunistisch laden',DEADLINE_CATCH_UP:'Catch-up actief',DEADLINE_GEMIST_CATCH_UP:'Deadline gepasseerd · catch-up',DOEL_GEHAALD:'Laaddoel gehaald',NIET_AANGESLOTEN:'Tesla niet aangesloten',CONFIG_FOUT:'Deadlineconfiguratie fout'};
    return map[String(s||'').toUpperCase()]||'';
  }
  async function refreshData(){
    const [status,command,phase]=await Promise.all([
      getJson('homey-status.json').catch(()=>statusCache),
      getJson('tesla-deadline-command.json').catch(()=>commandCache),
      getJson('pv-phase-24h.json').catch(()=>phaseCache)
    ]);
    if(status) statusCache=status;
    if(command) commandCache=command;
    if(phase) phaseCache=phase;
  }
  function applyOverlay(){
    const status=statusCache||{},command=commandCache||{},phase=phaseCache||{};
    document.querySelectorAll('.ha-goal').forEach(goal=>{
      const title=goal.querySelector('strong'),state=goal.querySelector('.ha-goal-state'),sub=goal.querySelector('small');
      if(title?.textContent.trim()==='Warm water' && state?.textContent.trim()==='Doel vandaag gehaald'){
        state.textContent='Boiler op temperatuur';
        if(sub) sub.textContent='Warmwaterdoel voor vandaag bereikt';
      }
    });

    const ww=(status.flows||[]).find(f=>f.name==='Warm water optimalisatie - PV boiler + CV advies v1.3')||{};
    const tes=(status.flows||[]).find(f=>f.name==='Tesla laden v2.1')||{};
    document.querySelectorAll('.ha-stage.control .ha-row').forEach(row=>{
      const spans=row.querySelectorAll(':scope > span'); if(spans.length<2)return;
      const key=spans[0].textContent.trim();
      if(key==='Boiler') spans[1].innerHTML=ww.enabled?'via warmwater · actief <span class="dot ok"></span>':'regeling uit <span class="dot off"></span>';
      if(key==='Tesla / Easee') spans[1].innerHTML=tes.enabled?'deadline-regeling v2.1 · actief <span class="dot ok"></span>':'regeling uit <span class="dot off"></span>';
    });

    const samples=phase.samples||[],latest=samples.length?samples[samples.length-1]:{};
    const runtime=latest.evDeadlineStatus||latest.EVDeadlineStatus||'';
    const latestStart=latest.evLatestStart||latest.EVLatestStart||'';
    const active=command.active===true;
    const currentSoc=Number(command.currentSoc),targetSoc=Number(command.targetSoc);
    const hasSoc=Number.isFinite(currentSoc)&&Number.isFinite(targetSoc)&&targetSoc>currentSoc;
    const goals=[...document.querySelectorAll('.ha-stage.decision .ha-goal')];
    const chargeGoal=goals.find(g=>g.querySelector('strong')?.textContent.trim()==='Tesla laden');
    const deadlineGoal=goals.find(g=>g.querySelector('strong')?.textContent.trim()==='Tesla gereed vóór');

    if(active){
      if(deadlineGoal){
        const state=deadlineGoal.querySelector('.ha-goal-state'),sub=deadlineGoal.querySelector('small');
        if(state){state.className='ha-goal-state warn';state.textContent=`Deadline actief · ${fmtDeadline(command.deadline)}`;}
        if(sub){
          const bits=[hasSoc?`${currentSoc}% → ${targetSoc}%`:'SOC opnieuw invoeren',`${Number(command.maxA||11)} A max`];
          if(latestStart) bits.push(`uiterlijk starten ${fmtDeadline(latestStart)}`);
          sub.textContent=bits.join(' · ');
        }
      }
      if(chargeGoal){
        const state=chargeGoal.querySelector('.ha-goal-state'),sub=chargeGoal.querySelector('small'),rl=runtimeLabel(runtime);
        if(state && rl){state.textContent=rl;state.className=`ha-goal-state ${/catch-up|gehaald/i.test(rl)?'ok':'warn'}`;}
        if(sub) sub.textContent=rl?'Operationele status van de actieve deadline-regeling':'Deadline is ingesteld; Homey-status wordt verwerkt';
      }
    } else if(deadlineGoal){
      const state=deadlineGoal.querySelector('.ha-goal-state'),sub=deadlineGoal.querySelector('small');
      if(state){state.className='ha-goal-state off';state.textContent='Geen deadline';}
      if(sub) sub.textContent='Opportunistisch laden / exportbuffer';
    }

    const foot=document.querySelector('.ha-foot');
    if(foot) foot.textContent=active
      ? (hasSoc
          ? `Tesla-SOC wordt handmatig als startwaarde ingevoerd. Deadline: van ${currentSoc}% naar ${targetSoc}% vóór ${fmtDeadline(command.deadline)}; intern rekent de regeling dit om naar benodigde laadenergie en bepaalt Homey wanneer catch-up nodig is.`
          : `Deze actieve deadline is nog met het oude kWh-formaat ingesteld. Bij de volgende wijziging voer je huidige SOC en doel-SOC in.`)
      : 'Zonder deadline wordt de Tesla opportunistisch geladen en kan hij als flexibele exportbuffer worden ingezet.';
  }
  async function enhance(){await refreshData();applyOverlay();}
  function scheduleEnhance(){clearTimeout(enhanceTimer);enhanceTimer=setTimeout(()=>{enhance().catch(()=>{});},80);}

  script.onload=()=>{
    document.dispatchEvent(new Event('DOMContentSwitch'));
    scheduleEnhance();
    const root=document.getElementById('home-architecture');
    if(root)new MutationObserver(()=>scheduleEnhance()).observe(root,{childList:true,subtree:true});
    setInterval(()=>enhance().catch(()=>{}),30000);
  };
  script.onerror=()=>{
    const root=document.getElementById('home-architecture');
    if(root) root.innerHTML='<div class="ha-shell"><div class="ha-health"><strong>Architectuuroverzicht kon niet worden geladen</strong><span>Basisrenderer ontbreekt.</span></div></div>';
  };
  document.head.appendChild(script);
})();
