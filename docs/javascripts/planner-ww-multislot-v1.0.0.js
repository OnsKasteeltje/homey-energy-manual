(() => {
  const root=document.getElementById('planner-shadow');
  if(!root)return;
  const RAW='https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-planner-shadow.json';
  const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
  const fmt=(v,d=1)=>finite(v)?Number(v).toLocaleString('nl-NL',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
  const time=iso=>{const d=new Date(iso);return Number.isNaN(d.getTime())?'—':d.toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'});};
  const el=(t,c,x)=>{const n=document.createElement(t);if(c)n.className=c;if(x!==undefined)n.textContent=x;return n;};
  const reasonLabel=r=>({PV_FULL:'volledig PV-overschot',PV_PARTIAL:'gedeeltelijk PV-overschot',DEADLINE_REQUIRED_CHEAPEST:'deadline · goedkoopste resterende slot',DEADLINE_REQUIRED:'deadline · resterend noodzakelijk'}[String(r||'').toUpperCase()]||String(r||'').replaceAll('_',' ').toLowerCase()||'plannerkeuze');
  const actionLabel=a=>{const w=String(a?.warmWater||'').toUpperCase();if(w==='MUST_CATCHUP')return 'MUST catch-up';if(w==='PV_PREFERRED')return 'PV preferred';if(w==='DEADLINE_REQUIRED')return 'deadline required';return w.replaceAll('_',' ').toLowerCase()||'gepland';};
  const unwrap=payload=>payload?.plan?.plan?.actions?payload.plan:(payload?.plan||payload||{});
  async function load(){for(const u of [root.dataset.source,`${RAW}?ts=${Date.now()}`]){try{const r=await fetch(u,{cache:'no-store'});if(r.ok)return await r.json();}catch(_){}}return null;}
  function render(payload){
    if(root.querySelector('#ps-ww-multislot'))return;
    const p=unwrap(payload),i=p.inputs||{},plan=p.plan||{},ww=i.warmWater||{},wwPlan=plan.warmWater||{},slots=Array.isArray(wwPlan.allocatedSlots)?wwPlan.allocatedSlots:[],actions=Array.isArray(plan.actions)?plan.actions:[];
    const sec=el('section','ps-section ps-ww-multislot');sec.id='ps-ww-multislot';
    sec.append(el('h2','','Warm water · multi-slot planning'));
    sec.append(el('div','ps-chart-note','De boiler wordt als splittable thermische buffer gepland: meerdere kwartierslots mogen samen het resterende dagdoel invullen. Dit blijft SHADOW; de fysieke WW-writer verandert hierdoor niet.'));
    const cards=el('div','ps-grid ps-ww-kpis');
    const required=finite(ww.derivedEnergyKWh)?Number(ww.derivedEnergyKWh):null;
    const allocated=slots.reduce((s,x)=>s+(finite(x.allocatedKWh)?Number(x.allocatedKWh):0),0);
    const unallocated=finite(wwPlan.unallocatedKWh)?Number(wwPlan.unallocatedKWh):Math.max(0,(required||0)-allocated);
    cards.append(
      card('Resterend doel',ww.goalReachedToday?'0,0 kWh':finite(required)?`${fmt(required)} kWh`:'—',ww.goalReachedToday?'Dagdoel OP_TEMPERATUUR bereikt':`${fmt(ww.remainingFallbackMin,0)} min confirmed-heating equivalent`),
      card('Geplande blokken',String(slots.length),slots.length?'verdeeld over geselecteerde kwartierslots':'geen WW-blokken gepland'),
      card('Gepland totaal',`${fmt(allocated)} kWh`,unallocated>0?`${fmt(unallocated)} kWh nog niet toegewezen`:'volledig binnen horizon toegewezen'),
      card('Deadline',ww.deadlineLocal||'19:00',ww.catchupRequired?'MUST_CATCHUP actief':'opportunity zolang catch-up niet nodig is')
    );
    sec.append(cards);
    if(ww.goalReachedToday){sec.append(el('div','ps-ww-state done','Dagdoel is al gehaald. Eventuele resterende forecastblokken horen te vervallen bij de volgende planner-run; post-goal mag nooit MUST worden.'));}
    else if(!slots.length){sec.append(el('div','ps-ww-state','Er zijn momenteel geen WW-slots toegewezen. De planner houdt het resterende doel open en moet vóór de deadline naar catch-up escaleren als uitstel niet meer veilig is.'));}
    else {
      const list=el('div','ps-ww-slot-list');let remaining=finite(required)?Number(required):allocated;
      slots.forEach((s,idx)=>{
        const row=el('div','ps-ww-slot');
        const start=time(s.start),end=time(s.end||new Date(new Date(s.start).getTime()+15*60000).toISOString()),e=finite(s.allocatedKWh)?Number(s.allocatedKWh):0;
        remaining=Math.max(0,remaining-e);
        const action=actions.find(a=>a.start===s.start)||s;
        row.append(
          el('div','ps-ww-slot-time',`${start}–${end}`),
          el('div','ps-ww-slot-energy',`${fmt(e,3)} kWh`),
          el('div','ps-ww-slot-reason',`${actionLabel(action)} · ${reasonLabel(s.allocationReason||action.warmWaterReason)}`),
          el('div','ps-ww-slot-split',`PV ${fmt(s.pvCoverageW??action.warmWaterPvCoverageW,0)} W · net ${fmt(s.gridRequiredW??action.warmWaterGridRequiredW,0)} W`),
          el('div','ps-ww-slot-remaining',`na blok: ${fmt(remaining,3)} kWh resterend`)
        );
        list.append(row);
      });
      sec.append(list);
    }
    const policy=wwPlan.allocationPolicy||'—';
    sec.append(el('div','ps-ww-foot',`Plannerpolicy: ${policy.replaceAll('_',' ').toLowerCase()} · iedere nieuwe planner-run herberekent vanaf de actuele confirmed-heating state.`));
    const must=root.querySelector('.ps-section:last-of-type');
    if(must&&must.parentNode===root)root.insertBefore(sec,must);else root.append(sec);
  }
  const card=(title,value,sub='')=>{const c=el('div','ps-card');c.append(el('div','ps-card-title',title),el('div','ps-card-value',value));if(sub)c.append(el('div','ps-card-sub',sub));return c;};
  load().then(p=>{if(p)render(p);});
})();