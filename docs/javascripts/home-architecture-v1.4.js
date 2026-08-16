(function(){
  // Homepage architecture v1.4: base renderer + warmwater corrections + Tesla deadline-aware status.
  const DATA_BASE='/homey-energy-manual/data/';
  const script=document.createElement('script');
  script.src='/homey-energy-manual/javascripts/home-architecture-v1.js';

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

  async function enhance(){
    // Warmwater wording/status.
    document.querySelectorAll('.ha-goal').forEach(goal=>{
      const title=goal.querySelector('strong');
      const state=goal.querySelector('.ha-goal-state');
      const sub=goal.querySelector('small');
      if(title?.textContent.trim()==='Warm water' && state?.textContent.trim()==='Doel vandaag gehaald'){
        state.textContent='Boiler op temperatuur';
        if(sub) sub.textContent='Warmwaterdoel voor vandaag bereikt';
      }
    });

    try{
      const [status,command,phase]=await Promise.all([
        getJson('homey-status.json'),
        getJson('tesla-deadline-command.json').catch(()=>null),
        getJson('pv-phase-24h.json').catch(()=>null)
      ]);

      // Current warm-water flow for control stage.
      const ww=(status.flows||[]).find(f=>f.name==='Warm water optimalisatie - PV boiler + CV advies v1.3')||{};
      const tes=(status.flows||[]).find(f=>f.name==='Tesla laden v2.1')||{};
      document.querySelectorAll('.ha-stage.control .ha-row').forEach(row=>{
        const spans=row.querySelectorAll(':scope > span');
        if(spans.length<2) return;
        const key=spans[0].textContent.trim();
        if(key==='Boiler'){
          spans[1].innerHTML=ww.enabled?'via warmwater · actief <span class="dot ok"></span>':'regeling uit <span class="dot off"></span>';
        }
        if(key==='Tesla / Easee'){
          spans[1].innerHTML=tes.enabled?'deadline-regeling v2.1 · actief <span class="dot ok"></span>':'regeling uit <span class="dot off"></span>';
        }
      });

      // Tesla deadline-aware decision cards.
      const samples=phase?.samples||[];
      const latest=samples.length?samples[samples.length-1]:{};
      const runtime=latest.evDeadlineStatus||latest.EVDeadlineStatus||'';
      const remaining=Number(latest.evRemainingKWh??latest.EVRemainingKWh);
      const latestStart=latest.evLatestStart||latest.EVLatestStart||'';
      const active=command?.active===true;
      const goals=[...document.querySelectorAll('.ha-stage.decision .ha-goal')];
      const chargeGoal=goals.find(g=>g.querySelector('strong')?.textContent.trim()==='Tesla laden');
      const deadlineGoal=goals.find(g=>g.querySelector('strong')?.textContent.trim()==='Tesla gereed vóór');

      if(active){
        if(deadlineGoal){
          const state=deadlineGoal.querySelector('.ha-goal-state');
          const sub=deadlineGoal.querySelector('small');
          if(state){state.className='ha-goal-state warn';state.textContent=`Deadline actief · ${fmtDeadline(command.deadline)}`;}
          if(sub){
            const bits=[`${Number(command.goalKWh||0).toLocaleString('nl-NL')} kWh doel`,`${Number(command.maxA||11)} A max`];
            if(Number.isFinite(remaining)) bits.push(`${remaining.toFixed(1)} kWh resterend`);
            if(latestStart) bits.push(`uiterlijk starten ${fmtDeadline(latestStart)}`);
            sub.textContent=bits.join(' · ');
          }
        }
        if(chargeGoal){
          const state=chargeGoal.querySelector('.ha-goal-state');
          const sub=chargeGoal.querySelector('small');
          const rl=runtimeLabel(runtime);
          if(state && rl){state.textContent=rl;state.className=`ha-goal-state ${/catch-up|gehaald/i.test(rl)?'ok':'warn'}`;}
          if(sub) sub.textContent=rl?`Operationele status van de actieve deadline-regeling`:`Deadline is ingesteld; Homey-status wordt verwerkt`;
        }
      } else {
        if(deadlineGoal){
          const state=deadlineGoal.querySelector('.ha-goal-state');
          const sub=deadlineGoal.querySelector('small');
          if(state){state.className='ha-goal-state off';state.textContent='Geen deadline';}
          if(sub) sub.textContent='Opportunistisch laden / exportbuffer';
        }
      }

      const foot=document.querySelector('.ha-foot');
      if(foot) foot.textContent=active
        ? `Tesla-SOC is niet beschikbaar. De actieve deadline wordt daarom gestuurd op minimaal ${Number(command.goalKWh||0).toLocaleString('nl-NL')} kWh laden vóór ${fmtDeadline(command.deadline)}; Homey bepaalt wanneer catch-up nodig is.`
        : 'Tesla-SOC is niet beschikbaar. Zonder deadline wordt de Tesla opportunistisch geladen en kan hij als flexibele exportbuffer worden ingezet.';
    }catch(_e){}
  }

  script.onload=()=>{
    document.dispatchEvent(new Event('DOMContentSwitch'));
    setTimeout(enhance,120);
    setTimeout(enhance,900);
  };
  script.onerror=()=>{
    const root=document.getElementById('home-architecture');
    if(root) root.innerHTML='<div class="ha-shell"><div class="ha-health"><strong>Architectuuroverzicht kon niet worden geladen</strong><span>Basisrenderer ontbreekt.</span></div></div>';
  };
  document.head.appendChild(script);
})();
