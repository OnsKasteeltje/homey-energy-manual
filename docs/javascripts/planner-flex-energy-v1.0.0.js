(() => {
  const root=document.getElementById('planner-shadow'); if(!root||root.querySelector('#ps-flex-energy'))return;
  const src=root.dataset.source||'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-planner-shadow.json?source=planner-flex-energy';
  const unwrap=x=>x?.plan?.inputs?x.plan:x;
  const fmt=(v,d=1)=>Number.isFinite(Number(v))?Number(v).toFixed(d):'—';
  const card=(title,value,note)=>`<div class="ps-card"><div class="ps-card-title">${title}</div><div class="ps-card-value">${value}</div>${note?`<div class="ps-card-note">${note}</div>`:''}</div>`;
  const render=data=>{
    const plan=unwrap(data); const ww=plan?.inputs?.warmWater||{}; const tesla=plan?.inputs?.tesla||{};
    const wwPowerW=Number(ww.modeledPowerW);
    const wwRemainingMin=Math.max(0,Number(ww.remainingFallbackMin)||0);
    const wwMaxKWh=Number.isFinite(wwPowerW)?wwPowerW/1000*4:null;
    const wwRemainingKWh=ww.goalReachedToday?0:(Number.isFinite(wwPowerW)?wwPowerW/1000*wwRemainingMin/60:null);
    const teslaKnown=tesla.deadlineActive===true&&Number.isFinite(Number(tesla.remainingKWh))&&Number(tesla.remainingKWh)>=0;
    const teslaEnergy=teslaKnown?`${fmt(tesla.remainingKWh,2)} kWh`:'onbekend';
    const section=document.createElement('section'); section.id='ps-flex-energy'; section.className='ps-section'; section.dataset.plannerTab='flex';
    section.innerHTML=`
      <h2>Planbare energie</h2>
      <div class="ps-chart-note">Resterende elektrische energie die de Planner nog flexibel over toekomstige tijdslots kan verdelen. Energie wordt in kWh getoond; vermogen apart in kW.</div>
      <div class="ps-grid">
        ${card('Boiler · planbare energie',Number.isFinite(wwRemainingKWh)?`${fmt(wwRemainingKWh,2)} / ${fmt(wwMaxKWh,1)} kWh`:'—',ww.goalReachedToday?'dagdoel gehaald':`${Math.round(wwRemainingMin)} min resterend bij ${fmt(wwPowerW/1000,1)} kW`)}
        ${card('Boiler · max. planbaar vermogen',Number.isFinite(wwPowerW)?`${fmt(wwPowerW/1000,1)} kW`:'—','modelvermogen warm water')}
        ${card('Tesla · planbare energie',teslaEnergy,teslaKnown?'actieve deadline-opdracht':'geen betrouwbare actuele SOC/energievraag beschikbaar')}
        ${card('Tesla · max. planbaar vermogen','nog vast te leggen','wordt afgeleid uit het EV Power Adapter-contract; geen fysieke accucapaciteit als planbudget')}
      </div>`;
    const hero=root.querySelector('.ps-hero'); const nav=root.querySelector('.ps-device-tabs');
    if(nav)nav.after(section); else if(hero)hero.after(section); else root.append(section);
  };
  fetch(src,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();}).then(render).catch(e=>console.warn('Planbare energie view kon niet laden',e));
})();