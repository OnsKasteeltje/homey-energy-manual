(() => {
  const root=document.getElementById('planner-shadow'); if(!root)return;
  const RAW='https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-planner-shadow.json';
  const el=(t,c,x)=>{const n=document.createElement(t);if(c)n.className=c;if(x!==undefined)n.textContent=x;return n;};
  const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
  const fmt=(v,d=0)=>finite(v)?Number(v).toLocaleString('nl-NL',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
  const signedW=v=>finite(v)?`${Number(v)>=0?'+':''}${fmt(v)} W`:'—';
  const time=iso=>{const d=new Date(iso);return Number.isNaN(d.getTime())?'—':d.toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'});};
  const local=iso=>{const d=new Date(iso);return Number.isNaN(d.getTime())?'—':d.toLocaleString('nl-NL',{dateStyle:'short',timeStyle:'short'});};
  const card=(title,value,sub='')=>{const c=el('div','ps-card');c.append(el('div','ps-card-title',title),el('div','ps-card-value',value));if(sub)c.append(el('div','ps-card-sub',sub));return c;};
  const section=title=>{const s=el('section','ps-section');s.append(el('h2','',title));return s;};
  const activeActions=a=>{const x=[];if(a?.battery&&a.battery!=='HOLD')x.push(`Accu ${a.battery}`);if(a?.tesla&&a.tesla!=='HOLD')x.push(`Tesla ${a.tesla}`);if(a?.warmWater&&a.warmWater!=='HOLD')x.push(`WW ${a.warmWater}`);return x;};
  const actionText=a=>activeActions(a).length?activeActions(a).join(' · '):'Geen actie';
  const cls=a=>String(a?.priceClass||a?.class||'normal').toLowerCase();
  const price=a=>finite(a?.price_eur_kwh)?Number(a.price_eur_kwh):finite(a?.price)?Number(a.price):null;
  const unwrap=payload=>payload?.plan?.plan?.actions?payload.plan:(payload?.plan||payload||{});
  const contributorLabel=t=>{const v=String(t?.likelyContributor||'');if(v.startsWith('WASHER_ACTIVE_'))return `Wasmachine actief in ${t.washerActiveSamples||0}/${t.sampleCount||0} samples`;if(v.startsWith('DRYER_ACTIVE_'))return `Droger actief in ${t.dryerActiveSamples||0}/${t.sampleCount||0} samples`;if(v==='HIGH_LOAD_UNIDENTIFIED')return 'Hoge historische load, apparaat niet herkend';return 'Structurele of niet-geclassificeerde baseload';};
  const traceText=a=>{const t=a?.baseForecastTrace;if(!t)return '';const vals=Array.isArray(t.sampleValuesW)&&t.sampleValuesW.length?t.sampleValuesW.map(v=>`${fmt(v)} W`).join(' · '):'geen kwartiersamples';return `\nForecastbasis: ${t.basis||'—'}\nHistorische samples: ${t.sampleCount||0}\nWaarden: ${vals}\nHerleiding: ${contributorLabel(t)}`;};
  async function load(){for(const u of [root.dataset.source,`${RAW}?ts=${Date.now()}`]){try{const r=await fetch(u,{cache:'no-store'});if(r.ok)return await r.json();}catch(_){}}throw new Error('Plannerdata niet bereikbaar');}

  function balanceChart(actions){
    const s=section('24-uurs energiebalans');
    const intro=el('div','ps-chart-note','Verwachting vóór flexibele lasten. Positief net = import; negatief net = PV-overschot. Hover op base load voor de historische herleiding.');s.append(intro);
    const known=actions.filter(a=>finite(a.baseLoadForecastW)||finite(a.pvForecastW)||finite(a.netBeforeFlexW));
    if(!known.length){s.append(el('div','ps-empty','Energy-balance forecast is nog niet beschikbaar.'));return s;}
    const values=[];actions.forEach(a=>{if(finite(a.baseLoadForecastW))values.push(Math.abs(Number(a.baseLoadForecastW)));if(finite(a.pvForecastW))values.push(Math.abs(Number(a.pvForecastW)));if(finite(a.netBeforeFlexW))values.push(Math.abs(Number(a.netBeforeFlexW)));});
    const max=Math.max(1000,...values);
    const legend=el('div','ps-balance-legend');[['Base load','base'],['PV','pv'],['Net vóór flex','net']].forEach(([label,c])=>{const x=el('span','');x.append(el('i',`ps-key ${c}`),document.createTextNode(label));legend.append(x);});s.append(legend);
    const chart=el('div','ps-balance-chart');
    actions.forEach((a,idx)=>{const col=el('div','ps-balance-col');const plot=el('div','ps-balance-plot');const zero=el('div','ps-zero');plot.append(zero);
      const bar=(kind,v)=>{if(!finite(v))return;const n=Number(v),h=Math.max(2,Math.min(48,Math.abs(n)/max*48));const b=el('div',`ps-bar ${kind}`);b.style.height=`${h}%`;if(kind==='net'){b.classList.add(n<0?'export':'import');b.style.bottom=n<0?`${50-h}%`:'50%';}else{b.style.bottom='50%';}b.title=`${time(a.start)} · ${kind==='base'?'Base load':kind==='pv'?'PV':'Net vóór flex'} ${fmt(n)} W${kind==='base'?traceText(a):''}`;plot.append(b);};
      bar('base',a.baseLoadForecastW);bar('pv',a.pvForecastW);bar('net',a.netBeforeFlexW);col.append(plot);if(idx%4===0)col.append(el('span','ps-balance-time',time(a.start)));chart.append(col);
    });s.append(chart);return s;
  }

  function render(payload){
    root.querySelector('#ps-status')?.remove();
    const p=unwrap(payload),i=p.inputs||{},plan=p.plan||{},actions=Array.isArray(plan.actions)?plan.actions:[],now=Date.now();
    const current=actions.find(a=>{const t=new Date(a.start).getTime();return Number.isFinite(t)&&t<=now&&t+15*60000>now;})||actions.find(a=>new Date(a.start).getTime()>=now)||actions[0];
    const modern=/V0\.(3|4)/.test(String(p.schema||''));
    const currentPrice=current?price(current):null;
    const summary=el('div','ps-summary');summary.append(el('strong','',current?actionText(current):'Geen actueel slot'),el('span','',`${finite(currentPrice)?`€ ${fmt(currentPrice,3)}/kWh · ${String(current?.priceClass||current?.class||'—')}`:'prijs —'} · ${i.contract||'—'} · ${String(p.schema||'').replace('EM2_ENERGY_PLAN_24H_','Planner ')}`));

    const kpis=el('div','ps-grid ps-kpi-grid');
    const eb=plan.energyBalance||{},fq=i.forecastQuality||{},teslaPolicy=i.tesla?.opportunityPolicy||'';
    kpis.append(
      card('Base load',finite(current?.baseLoadForecastW)?`${fmt(current.baseLoadForecastW)} W`:finite(eb.baseLoadGlobalMedianW)?`${fmt(eb.baseLoadGlobalMedianW)} W`:'—',current?.baseForecastTrace?`${current.baseForecastTrace.basis} · ${current.baseForecastTrace.sampleCount} samples`:fq.baseLoad||'—'),
      card('PV forecast',finite(current?.pvForecastW)?`${fmt(current.pvForecastW)} W`:'—',fq.pv||i.pvForecast?.quality||'—'),
      card('Net vóór flex',signedW(current?.netBeforeFlexW),finite(current?.pvSurplusBeforeFlexW)&&Number(current.pvSurplusBeforeFlexW)>0?`${fmt(current.pvSurplusBeforeFlexW)} W PV-overschot`:finite(current?.importBeforeFlexW)?`${fmt(current.importBeforeFlexW)} W import`:'onbekend'),
      card('Forecastdekking',modern?`${fmt(eb.slotsWithNetForecast||0)}/96`:`${actions.length}/96`,`PV-slots ${fmt(eb.slotsWithPvForecast||0)} · ${plan.horizonQuality||'—'}`)
    );

    const horizon=section('Planneracties — komende 24 uur'),legend=el('div','ps-legend');['CHEAP','NORMAL','EXPENSIVE','FIXED'].forEach(x=>legend.append(el('span',`ps-pill ${x.toLowerCase()}`,x)));horizon.append(legend);const strip=el('div','ps-slot-strip');actions.forEach(a=>{const active=activeActions(a).length>0,s=el('div',`ps-slot ${cls(a)} ${active?'active':''}`),pr=price(a);s.title=`${time(a.start)} · ${actionText(a)} · ${finite(pr)?`€ ${fmt(pr,3)}`:'prijs —'} · base ${fmt(a.baseLoadForecastW)} W · PV ${fmt(a.pvForecastW)} W · net ${signedW(a.netBeforeFlexW)}${traceText(a)}`;s.append(el('span','ps-slot-time',time(a.start)),el('strong','',actionText(a)));strip.append(s);});horizon.append(strip);

    const why=section('Waarom dit besluit?'),notes=[];
    if(modern){if(String(fq.pv||'').startsWith('WEATHER_'))notes.push('PV-forecast gebruikt de 15-minuten weerforecast voor Hauwert en wordt gekalibreerd tegen gemeten PV.');if(fq.gridHeadroom==='NOT_MODELED_PHASE_AWARE')notes.push('Fasebewuste net-headroom is nog niet gemodelleerd; runtime safety blijft leidend.');if(plan.battery?.mode==='THEORETICAL_ONLY_NO_SOC')notes.push('Batterijplanning blijft theoretisch zolang werkelijk SOC en commissioningconstraints ontbreken.');}
    if(i.tesla?.deadlineActive)notes.push('Tesla deadline/MUST: PV-overschot krijgt voorrang; alleen resterende noodzakelijke netenergie wordt bij DYNAMIC naar goedkope slots verschoven.');
    else if(teslaPolicy==='PV_SURPLUS_ONLY')notes.push(`Tesla opportunity is PV-only: zonder minimaal ${fmt(i.tesla?.opportunityMinW||800)} W verwacht PV-overschot wordt geen laadslot gepland, ook niet bij goedkope of negatieve prijzen.`);
    else notes.push('Geen Tesla deadline-MUST: opportunity hoort uitsluitend uit PV/exportoverschot te komen.');
    if(i.warmWater?.goalReachedToday)notes.push('Warmwaterdagdoel is gehaald: geen verplichte extra opwarming.');if(actions.length&&actions.every(a=>activeActions(a).length===0))notes.push('Er is nu geen laad-, ontlaad- of flexloadactie gepland; alle slots handhaven de huidige toestand.');const ul=el('ul','ps-reasons');(notes.length?notes:['Geen bijzondere blokkades gerapporteerd.']).forEach(n=>ul.append(el('li','',n)));why.append(ul);

    const must=section('Verplichtingen & datakwaliteit'),mg=el('div','ps-grid');
    const priceInfo=i.price||{};mg.append(card('Tesla',i.tesla?.deadlineActive?'MUST actief':'PV opportunity',i.tesla?.deadlineActive?`${fmt(i.tesla.remainingKWh,1)} kWh · deadline ${local(i.tesla.deadlineAt)}`:`PV-only · ≥ ${fmt(i.tesla?.opportunityMinW||800)} W`),card('Warm water',i.warmWater?.catchupRequired?'MUST_CATCHUP':i.warmWater?.goalReachedToday?'Dagdoel gehaald':'Nog open',`deadline ${i.warmWater?.deadlineLocal||'19:00'}`),card('Prijscontext',(priceInfo.usable??i.priceUsable)?'Bruikbaar':'Niet bruikbaar',i.tesla?.deadlineActive?`${priceInfo.quality||i.priceQuality||'—'} · deadline-optimalisatie`:`${priceInfo.quality||i.priceQuality||'—'} · geen Tesla opportunity-trigger`),card('PV-forecast',fq.pv||i.pvForecast?.quality||'—',fq.pvNote||i.pvForecast?.note||''));must.append(mg);
    root.append(summary,kpis,balanceChart(actions),horizon,why,must);
  }
  load().then(render).catch(e=>{const s=root.querySelector('#ps-status');if(s){s.className='ps-error';s.textContent=`Plannerdata laden mislukt: ${e.message}`;}});
})();
