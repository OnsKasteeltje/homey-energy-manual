(() => {
  const root=document.getElementById('planner-shadow'); if(!root||root.querySelector('#ps-flex-energy'))return;
  const src=root.dataset.source||'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-planner-shadow.json?source=planner-flex-energy';
  const unwrap=x=>x?.plan?.inputs?x.plan:x;
  const fmt=(v,d=1)=>Number.isFinite(Number(v))?Number(v).toLocaleString('nl-NL',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
  const card=(title,value,note)=>`<div class="ps-card"><div class="ps-card-title">${title}</div><div class="ps-card-value">${value}</div>${note?`<div class="ps-card-sub">${note}</div>`:''}</div>`;
  const fixBoilerRow=ww=>{
    const moved=root.querySelector('#ps-forecast-load-windows');
    const price=[...root.querySelectorAll('.ps-section')].find(s=>s.querySelector('h2')?.textContent?.trim()==='Prijs & planneracties');
    const hosts=[moved,price].filter(Boolean);
    const isBoiler=r=>['Boiler','Boiler plan'].includes(r.querySelector('.ps-action-name')?.textContent?.trim());
    let row=null;
    for(const host of hosts){row=[...host.querySelectorAll(':scope > .ps-action-row')].find(isBoiler);if(row)break;}
    const host=moved||price;if(!host)return;
    if(!row){row=document.createElement('div');row.className='ps-action-row ps-forecast-row';const name=document.createElement('div');name.className='ps-action-name';name.textContent='Boiler plan';const track=document.createElement('div');track.className='ps-action-track';row.append(name,track);host.append(row);}
    const track=row.querySelector('.ps-action-track');
    if(track&&!track.querySelector('.ps-action-segment:not(.ps-action-empty)')){
      let empty=track.querySelector('.ps-action-empty');if(!empty){empty=document.createElement('div');empty.className='ps-action-segment ps-action-empty';empty.style.gridColumn='1 / 97';track.append(empty);}
      empty.textContent=ww.goalReachedToday?'geen planning · dagdoel gehaald':ww.catchupRequired?'catch-up vereist · nog geen slot gepubliceerd':'geen warmwaterplanning in deze horizon';
    }
  };
  const render=data=>{
    const plan=unwrap(data); const ww=plan?.inputs?.warmWater||{}; const tesla=plan?.inputs?.tesla||{};
    fixBoilerRow(ww);
    const wwPowerW=Number(ww.modeledPowerW),wwRemainingMin=Math.max(0,Number(ww.remainingFallbackMin)||0);
    const wwMaxKWh=Number.isFinite(wwPowerW)?wwPowerW/1000*4:null;
    const wwRemainingKWh=ww.goalReachedToday?0:(Number.isFinite(wwPowerW)?wwPowerW/1000*wwRemainingMin/60:null);
    const teslaKnown=tesla.deadlineActive===true&&Number.isFinite(Number(tesla.remainingKWh))&&Number(tesla.remainingKWh)>=0;
    const section=document.createElement('section'); section.id='ps-flex-energy'; section.className='ps-section'; section.dataset.plannerTab='flex';
    section.innerHTML=`<h2>Planbare energie</h2><div class="ps-chart-note">Resterende elektrische energie die nog over toekomstige tijdslots kan worden verdeeld. Energie in kWh; vermogen apart in kW.</div><div class="ps-grid">${card('Boiler · planbare energie',Number.isFinite(wwRemainingKWh)?`${fmt(wwRemainingKWh,2)} / ${fmt(wwMaxKWh,1)} kWh`:'—',ww.goalReachedToday?'dagdoel gehaald':`${Math.round(wwRemainingMin)} min resterend bij ${fmt(wwPowerW/1000,1)} kW`)}${card('Boiler · max. planbaar vermogen',Number.isFinite(wwPowerW)?`${fmt(wwPowerW/1000,1)} kW`:'—','modelvermogen warm water')}${card('Tesla · planbare energie',teslaKnown?`${fmt(tesla.remainingKWh,2)} kWh`:'onbekend',teslaKnown?'actieve deadline-opdracht':'geen betrouwbare actuele SOC/energievraag beschikbaar')}${card('Tesla · max. planbaar vermogen','nog vast te leggen','volgt uit EV Power Adapter-contract; accucapaciteit is geen planbudget')}</div>`;
    const nav=root.querySelector('.ps-device-tabs'),hero=root.querySelector('.ps-hero');if(nav)nav.after(section);else if(hero)hero.after(section);else root.append(section);
  };
  fetch(src,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();}).then(render).catch(e=>console.warn('Planbare energie view kon niet laden',e));
})();