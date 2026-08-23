(() => {
  const root = document.getElementById('planner-shadow');
  if (!root) return;

  const RAW_BASE = 'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/';
  const BUSINESS_CASE = {
    import2027: 0.25500,
    netExport2027: 0.00250,
    roundTripEfficiency: 0.85,
    nominalCapacityKWh: 14.4,
    usableWindowKWh: 10.08,
    acLimitW: 3300,
    feederLimitA: 16,
    nominalVoltageV: 230,
    batteryContinuousW: 3600,
    investmentEuro: 4880,
    annualCentralEuro: 687,
    annualLowEuro: 556,
    annualHighEuro: 808,
    annualUsefulOutputKWh: 2720
  };
  BUSINESS_CASE.hardwareMaxW = Math.min(
    BUSINESS_CASE.acLimitW,
    BUSINESS_CASE.feederLimitA * BUSINESS_CASE.nominalVoltageV,
    BUSINESS_CASE.batteryContinuousW
  );

  const el = (tag, cls, text) => { const n=document.createElement(tag); if(cls)n.className=cls; if(text!==undefined)n.textContent=text; return n; };
  const fmt = (v,d=1) => Number.isFinite(Number(v)) ? Number(v).toLocaleString('nl-NL',{minimumFractionDigits:d,maximumFractionDigits:d}) : '—';
  const fmtKWh = v => `${fmt(v,2)} kWh`;
  const fmtW = v => Number.isFinite(Number(v)) ? `${Math.round(Number(v))} W` : '—';
  const euro = v => Number.isFinite(Number(v)) ? `€ ${fmt(v,2)}` : '—';
  const local = iso => { if(!iso)return '—'; const d=new Date(iso); return Number.isNaN(d.getTime())?'—':d.toLocaleString('nl-NL',{dateStyle:'short',timeStyle:'short'}); };
  const badge = (text,kind='') => el('span',`ps-badge ${kind}`,text);

  async function fetchJson(primary, rawFile, required=true){
    const candidates=[primary, `${RAW_BASE}${rawFile}?ts=${Date.now()}`].filter(Boolean);
    let last='geen bron geprobeerd';
    for(const url of candidates){
      try{
        const r=await fetch(url,{cache:'no-store'});
        if(!r.ok){last=`HTTP ${r.status} op ${url}`;continue;}
        return await r.json();
      }catch(e){last=`${e.message} op ${url}`;}
    }
    if(required) throw new Error(last);
    return {days:[]};
  }

  function card(title,value,sub=''){
    const c=el('div','ps-card'); c.append(el('div','ps-card-title',title),el('div','ps-card-value',value)); if(sub)c.append(el('div','ps-card-sub',sub)); return c;
  }

  function renderScore(payload){
    const p=payload.plan||{}, s=p.scenario||{}, i=p.inputs||{}, st=payload.status||{};
    const wrap=el('section','ps-section'); wrap.append(el('h2','', 'Actuele plannerstatus'));
    const grid=el('div','ps-grid');
    grid.append(
      card('Status',p.plannerStatus||st.status||'—',`gegenereerd ${local(p.generatedAt)}`),
      card('Scenario',`${fmt(BUSINESS_CASE.nominalCapacityKWh,1)} kWh`,`3 × Pylontech US5000 · ${fmtW(BUSINESS_CASE.hardwareMaxW)} hardwarelimiet`),
      card('Bruikbaar venster',fmtKWh(Number(s.usableWindowKWh)||BUSINESS_CASE.usableWindowKWh),`SOC ${fmt(s.minSocPct,0)}–${fmt(s.maxSocPct,0)}% · ηRT ${fmt(BUSINESS_CASE.roundTripEfficiency*100,0)}%`),
      card('Hardwaregrens',fmtW(BUSINESS_CASE.hardwareMaxW),`${BUSINESS_CASE.feederLimitA} A × ${BUSINESS_CASE.nominalVoltageV} V = ${fmtW(BUSINESS_CASE.feederLimitA*BUSINESS_CASE.nominalVoltageV)}; ESS bewust lager begrensd`),
      card('Contractscenario','Zonder saldering',`€ ${fmt(BUSINESS_CASE.import2027,4)}/kWh afname · € ${fmt(BUSINESS_CASE.netExport2027,4)}/kWh terugleverwaarde`),
      card('Tesla',i.tesla?.deadlineActive?`${fmtKWh(i.tesla.remainingKWh)} resterend`:'Geen deadline-MUST',i.tesla?.deadlineActive?`deadline ${local(i.tesla.deadlineAt)}`:(i.tesla?.deadlineAt?`laatste deadline ${local(i.tesla.deadlineAt)}`:'')),
      card('Warm water',i.warmWater?.goalReachedToday?'Dagdoel gehaald':`${fmt(i.warmWater?.remainingFallbackMin,0)} min resterend`,i.warmWater?.catchupRequired?'MUST_CATCHUP':'deadline 19:00')
    );
    wrap.append(grid);
    const q=el('div','ps-quality'); q.append(badge('SHADOW','good'),badge('CONTROL IMPACT: NONE','good'),badge(`PV forecast: ${i.pvForecast?.quality||'—'}`,i.pvForecast?.quality==='SUMMARY_ONLY'?'warn':''));
    if((p.plan?.slotsAvailable||0)===0) q.append(badge('Geen kwartierslots bij huidig FIXED-plan','warn'));
    wrap.append(q); return wrap;
  }

  function renderTimeline(payload){
    const p=payload.plan||{}, actions=p.plan?.actions||[];
    const sec=el('section','ps-section'); sec.append(el('h2','', '24-uurs plan'));
    if(!actions.length){sec.append(el('div','ps-empty','De huidige v0.2-planner publiceert bij FIXED geen kunstmatige kwartierprijzen. Daarom zijn er nu geen dispatch-slots om te tekenen. De historische replay hieronder is wél bruikbaar voor het batterijscenario.')); return sec;}
    const scroller=el('div','ps-timeline-scroll'), table=el('table','ps-timeline');
    const trh=el('tr'); ['Tijd','Prijs','Batterij','Tesla','Warm water'].forEach(x=>trh.append(el('th','',x))); const thead=el('thead');thead.append(trh);table.append(thead);
    const tb=el('tbody'); actions.forEach(a=>{const tr=el('tr'); const cells=[new Date(a.start).toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'}),Number.isFinite(Number(a.price))?`€ ${Number(a.price).toFixed(3)}`:'—',a.battery||'HOLD',a.tesla||'HOLD',a.warmWater||'HOLD']; cells.forEach((x,j)=>{const td=el('td',j>1&&x!=='HOLD'?'ps-active':'',x);tr.append(td)});tb.append(tr)}); table.append(tb);scroller.append(table);sec.append(scroller);return sec;
  }

  function simulateDay(day, cfg){
    const samples=(day.samples||[]).filter(s=>Number.isFinite(Number(s.p1W))).sort((a,b)=>new Date(a.ts)-new Date(b.ts));
    if(samples.length<2)return null;
    let stored=0, chargedGrid=0, dischargedGrid=0, losses=0, exportRaw=0, importRaw=0, clippedExport=0;
    let chargePowerLimited=0, dischargePowerLimited=0, capacityLimited=0, phaseSamples=0, maxAbsL1W=0, maxBatteryW=0;
    for(let idx=0;idx<samples.length;idx++){
      const s=samples[idx], next=samples[idx+1]; let dtH=5/60;
      if(next){const d=(new Date(next.ts)-new Date(s.ts))/3600000;if(d>0&&d<0.5)dtH=d;}
      const p=Number(s.p1W);
      if(Number.isFinite(Number(s.l1W))&&Number.isFinite(Number(s.l2W))&&Number.isFinite(Number(s.l3W))){phaseSamples++;maxAbsL1W=Math.max(maxAbsL1W,Math.abs(Number(s.l1W)));}
      if(p<0){
        const exportKWh=(-p)*dtH/1000; exportRaw+=exportKWh;
        const powerCap=cfg.maxW*dtH/1000;
        const capacityCap=Math.max(0,(cfg.usableKWh-stored)/cfg.etaC);
        const acIn=Math.max(0,Math.min(exportKWh,powerCap,capacityCap));
        chargePowerLimited+=Math.max(0,Math.min(exportKWh,capacityCap)-acIn);
        capacityLimited+=Math.max(0,Math.min(exportKWh,powerCap)-acIn);
        if(acIn>0){const add=acIn*cfg.etaC;stored+=add;chargedGrid+=acIn;losses+=acIn-add;maxBatteryW=Math.max(maxBatteryW,acIn/dtH*1000);}
        clippedExport+=Math.max(0,exportKWh-acIn);
      } else if(p>0){
        const importKWh=p*dtH/1000; importRaw+=importKWh;
        const powerCap=cfg.maxW*dtH/1000;
        const energyCap=Math.max(0,stored*cfg.etaD);
        const acOut=Math.max(0,Math.min(importKWh,powerCap,energyCap));
        dischargePowerLimited+=Math.max(0,Math.min(importKWh,energyCap)-acOut);
        if(acOut>0){const take=acOut/cfg.etaD;stored-=take;dischargedGrid+=acOut;losses+=take-acOut;maxBatteryW=Math.max(maxBatteryW,acOut/dtH*1000);}
      }
    }
    const throughput=chargedGrid+dischargedGrid;
    const avoidedImportValue=dischargedGrid*BUSINESS_CASE.import2027;
    const lostExportCredit=chargedGrid*BUSINESS_CASE.netExport2027;
    return {date:day.date_local,samples:samples.length,phaseSamples,exportRaw,importRaw,chargedGrid,dischargedGrid,losses,cycles:throughput/(2*cfg.usableKWh),endStored:stored,clippedExport,avoidedImportValue,lostExportCredit,netEuro:avoidedImportValue-lostExportCredit,chargePowerLimited,dischargePowerLimited,capacityLimited,maxAbsL1W,maxBatteryW};
  }

  function replayRows(history,cfg){ return (history.days||[]).map(d=>simulateDay(d,cfg)).filter(Boolean).slice(-7); }
  function aggregate(rows){
    return rows.reduce((a,r)=>{
      ['chargedGrid','dischargedGrid','losses','cycles','exportRaw','importRaw','clippedExport','avoidedImportValue','lostExportCredit','netEuro','chargePowerLimited','dischargePowerLimited','capacityLimited','phaseSamples','samples'].forEach(k=>a[k]+=r[k]||0);
      a.maxAbsL1W=Math.max(a.maxAbsL1W,r.maxAbsL1W||0); a.maxBatteryW=Math.max(a.maxBatteryW,r.maxBatteryW||0); a.endStored=r.endStored||0; return a;
    },{chargedGrid:0,dischargedGrid:0,losses:0,cycles:0,exportRaw:0,importRaw:0,clippedExport:0,avoidedImportValue:0,lostExportCredit:0,netEuro:0,chargePowerLimited:0,dischargePowerLimited:0,capacityLimited:0,phaseSamples:0,samples:0,maxAbsL1W:0,maxBatteryW:0,endStored:0});
  }

  function renderDecision(history,payload){
    const sec=el('section','ps-section ps-decision'); sec.append(el('h2','', 'Potentiële besparing'));
    const etaLeg=Math.sqrt(BUSINESS_CASE.roundTripEfficiency);
    const mainCfg={usableKWh:BUSINESS_CASE.usableWindowKWh,maxW:BUSINESS_CASE.hardwareMaxW,etaC:etaLeg,etaD:etaLeg};
    const smallCfg={usableKWh:6.72,maxW:2500,etaC:etaLeg,etaD:etaLeg};
    const mainRows=replayRows(history,mainCfg), smallRows=replayRows(history,smallCfg), main=aggregate(mainRows), small=aggregate(smallRows);
    if(!mainRows.length){sec.append(el('div','ps-empty','Nog onvoldoende afgeronde daghistorie voor financiële vergelijking.'));return sec;}
    const deltaEuro=main.netEuro-small.netEuro, deltaImport=main.dischargedGrid-small.dischargedGrid;
    const simplePayback=BUSINESS_CASE.investmentEuro/BUSINESS_CASE.annualCentralEuro;
    const phaseCoverage=main.samples?100*main.phaseSamples/main.samples:0;

    sec.append(el('h3','', 'Jaarprognose zonder saldering'));
    sec.append(el('p','ps-footnote','Rekenaanname voor een gemiddeld jaar; niet geëxtrapoleerd uit de onderstaande meetdagen.'));
    const forecast=el('div','ps-grid'); forecast.append(
      card('Jaarpotentieel batterij',`€ ${fmt(BUSINESS_CASE.annualCentralEuro,0)} / jaar`,`bandbreedte € ${fmt(BUSINESS_CASE.annualLowEuro,0)}–€ ${fmt(BUSINESS_CASE.annualHighEuro,0)} per jaar`),
      card('Bruikbare accu-output',`${fmt(BUSINESS_CASE.annualUsefulOutputKWh,0)} kWh / jaar`,'centrale businesscase-aanname'),
      card('Investering AC-coupled',`€ ${fmt(BUSINESS_CASE.investmentEuro,0)}`,'3 × US5000 · zonder SmartSolar MPPT/DC-ombouw'),
      card('Eenvoudige TVT',`${fmt(simplePayback,1)} jaar`,'€ 4.880 ÷ € 687/jaar')
    ); sec.append(forecast);

    sec.append(el('h3','', `Hardware-feasible validatie · ${mainRows.length} gemeten dagen · zonder saldering`));
    sec.append(el('p','ps-footnote',`Replay respecteert maximaal ${fmtW(BUSINESS_CASE.hardwareMaxW)}, ${fmtKWh(BUSINESS_CASE.usableWindowKWh)} bruikbaar accuvenster en 85% round-trip rendement. Fasegegevens aanwezig voor ${fmt(phaseCoverage,0)}% van de samples; deze valideren de netbalans, maar zijn geen directe meting van de schuurkabelstroom.`));
    const measured=el('div','ps-grid'); measured.append(
      card('Hardware-feasible besparing',euro(main.netEuro),`${fmtKWh(main.dischargedGrid)} werkelijk simuleerbaar als vermeden netimport`),
      card('Vermeden netinkoop',euro(main.avoidedImportValue),`${fmtKWh(main.dischargedGrid)} × € ${fmt(BUSINESS_CASE.import2027,4)}/kWh`),
      card('Gemiste terugleverwaarde',euro(main.lostExportCredit),`${fmtKWh(main.chargedGrid)} × € ${fmt(BUSINESS_CASE.netExport2027,4)}/kWh`),
      card('Conversieverlies',fmtKWh(main.losses),`AC→accu→AC · ηRT ${fmt(BUSINESS_CASE.roundTripEfficiency*100,0)}%`),
      card('Piek batterijvermogen',fmtW(main.maxBatteryW),`hard begrensd op ${fmtW(BUSINESS_CASE.hardwareMaxW)}`),
      card('Door vermogenslimiet gemist',fmtKWh(main.chargePowerLimited+main.dischargePowerLimited),'extra laad-/ontlaadpotentieel dat 3,3 kW niet kon volgen'),
      card('Door capaciteit gemist',fmtKWh(main.capacityLimited),'PV-overschot dat niet meer in het bruikbare accuvenster paste'),
      card('Eindenergie in accu',fmtKWh(main.endStored),'op einde laatste gereplayde dag; niet als verlies geboekt'),
      card('Extra 14,4 vs 9,6 kWh',euro(deltaEuro),`${fmtKWh(deltaImport)} extra vermeden import in deze meetperiode`),
      card('Resterende export',fmtKWh(main.clippedExport),'niet opgeslagen door timing, vermogen of capaciteit')
    ); sec.append(measured);

    sec.append(el('div','ps-empty',`Hardware-check: gekozen ESS-limiet ${fmtW(BUSINESS_CASE.hardwareMaxW)} ligt onder de theoretische ${BUSINESS_CASE.feederLimitA} A × ${BUSINESS_CASE.nominalVoltageV} V = ${fmtW(BUSINESS_CASE.feederLimitA*BUSINESS_CASE.nominalVoltageV)} en onder de conservatieve 3×US5000-vermogensruimte van circa ${fmtW(BUSINESS_CASE.batteryContinuousW)}. De VM-3P75CT meet L1/L2/L3 op het netpunt; daardoor kunnen we Total-of-all-phases energetisch valideren, maar niet rechtstreeks de lokale stroom in de 20 m schuurkabel reconstrueren.`));
    sec.append(el('p','ps-footnote','Direct PV-verbruik door Tesla, boiler of andere verbruikers wordt niet dubbel als batterijbesparing geteld: de replay start bij gemeten netto P1-export en -import.'));
    return sec;
  }

  function renderReplay(history,payload){
    const sec=el('section','ps-section'); sec.append(el('h2','', 'Historische batterijreplay'));
    const etaLeg=Math.sqrt(BUSINESS_CASE.roundTripEfficiency);
    const cfg={usableKWh:BUSINESS_CASE.usableWindowKWh,maxW:BUSINESS_CASE.hardwareMaxW,etaC:etaLeg,etaD:etaLeg};
    const rows=replayRows(history,cfg).reverse();
    if(!rows.length){sec.append(el('div','ps-empty','Nog onvoldoende daghistorie voor replay.'));return sec;}
    const sum=aggregate(rows);
    const grid=el('div','ps-grid ps-replay-summary'); grid.append(
      card('Hardware-feasible effect',euro(sum.netEuro),`${euro(sum.avoidedImportValue)} vermeden inkoop − ${euro(sum.lostExportCredit)} gemiste teruglevering`),
      card('Opgeslagen netto export',fmtKWh(sum.chargedGrid),'AC energie richting gesimuleerde accu'),
      card('Vermeden netimport',fmtKWh(sum.dischargedGrid),'geleverd binnen 3,3 kW- en capaciteitslimieten'),
      card('Conversieverlies',fmtKWh(sum.losses),`ηRT ${fmt(BUSINESS_CASE.roundTripEfficiency*100,0)}%`),
      card('Equivalent cycli',fmt(sum.cycles,2),'over getoonde afgeronde dagen')
    ); sec.append(grid);
    const table=el('table','ps-replay-table'); const th=el('tr');['Dag','Export gemeten','Naar accu','Import gemeten','Vermeden import','€ effect','Piek accu','Eind-SOC energie','Cycli'].forEach(x=>th.append(el('th','',x)));const head=el('thead');head.append(th);table.append(head);const tb=el('tbody');rows.forEach(r=>{const tr=el('tr');[r.date,fmtKWh(r.exportRaw),fmtKWh(r.chargedGrid),fmtKWh(r.importRaw),fmtKWh(r.dischargedGrid),euro(r.netEuro),fmtW(r.maxBatteryW),fmtKWh(r.endStored),fmt(r.cycles,2)].forEach(x=>tr.append(el('td','',x)));tb.append(tr)});table.append(tb);const sc=el('div','ps-timeline-scroll');sc.append(table);sec.append(sc);
    sec.append(el('p','ps-footnote','Replay gebruikt gemeten netto P1-data en respecteert de bekende hardwaregrenzen van het gekozen AC-coupled ontwerp. Fasegegevens worden gebruikt als netpunt-validatie; lokale feederstroom blijft pas hard verifieerbaar met meting in de schuur-/Victron-tak.'));
    return sec;
  }

  async function load(){
    const status=document.getElementById('ps-status');
    try{
      const [payload,history]=await Promise.all([fetchJson(root.dataset.source,'energy-planner-shadow.json',true),fetchJson(root.dataset.history,'energy-day-series-7d.json',false)]);
      if(payload.observabilityOnly!==true||payload.controlImpact!=='NONE')throw new Error('observability safety marker ontbreekt');
      status.replaceChildren(renderDecision(history,payload),renderScore(payload),renderTimeline(payload),renderReplay(history,payload));
    }catch(e){status.replaceChildren(el('div','ps-error',`Planner Shadow kon niet worden geladen: ${e.message}`));}
  }
  load();
})();