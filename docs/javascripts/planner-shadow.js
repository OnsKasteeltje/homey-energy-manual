(() => {
  const root = document.getElementById('planner-shadow');
  if (!root) return;

  const RAW_BASE = 'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/';
  const TARIFF = {
    importNormal: 0.23790,
    importOffPeak: 0.23548,
    importReplay: (0.23790 + 0.23548) / 2,
    exportCredit: 0.15000
  };
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
      card('Scenario',`${fmt(s.nominalCapacityKWh,1)} kWh`,`${s.battery||'—'} · ${fmtW(s.acChargeLimitW)} max AC`),
      card('Bruikbaar venster',fmtKWh(s.usableWindowKWh),`SOC ${fmt(s.minSocPct,0)}–${fmt(s.maxSocPct,0)}% · ηRT ${fmt((s.roundTripEfficiency||0)*100,1)}%`),
      card('Contract',i.contract||'—',`prijscontext ${i.priceQuality||'—'} · horizon ${fmt(i.priceHorizonHours,0)} h`),
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
    if(!actions.length){
      sec.append(el('div','ps-empty','De huidige v0.2-planner publiceert bij FIXED geen kunstmatige kwartierprijzen. Daarom zijn er nu geen dispatch-slots om te tekenen. De historische replay hieronder is wél bruikbaar voor het batterijscenario.')); return sec;
    }
    const scroller=el('div','ps-timeline-scroll'), table=el('table','ps-timeline');
    const trh=el('tr'); ['Tijd','Prijs','Batterij','Tesla','Warm water'].forEach(x=>trh.append(el('th','',x))); const thead=el('thead');thead.append(trh);table.append(thead);
    const tb=el('tbody'); actions.forEach(a=>{const tr=el('tr'); const cells=[new Date(a.start).toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'}),Number.isFinite(Number(a.price))?`€ ${Number(a.price).toFixed(3)}`:'—',a.battery||'HOLD',a.tesla||'HOLD',a.warmWater||'HOLD']; cells.forEach((x,j)=>{const td=el('td',j>1&&x!=='HOLD'?'ps-active':'',x);tr.append(td)});tb.append(tr)}); table.append(tb);scroller.append(table);sec.append(scroller);return sec;
  }

  function simulateDay(day, cfg){
    const samples=(day.samples||[]).filter(s=>Number.isFinite(Number(s.p1W))).sort((a,b)=>new Date(a.ts)-new Date(b.ts));
    if(samples.length<2)return null;
    let stored=0, chargedGrid=0, dischargedGrid=0, losses=0, exportRaw=0, importRaw=0, clippedExport=0;
    for(let idx=0;idx<samples.length;idx++){
      const s=samples[idx], next=samples[idx+1]; let dtH=5/60;
      if(next){const d=(new Date(next.ts)-new Date(s.ts))/3600000;if(d>0&&d<0.5)dtH=d;}
      const p=Number(s.p1W);
      if(p<0){
        const exportKWh=(-p)*dtH/1000; exportRaw+=exportKWh;
        const acIn=Math.max(0,Math.min(exportKWh,cfg.maxW*dtH/1000,(cfg.usableKWh-stored)/cfg.etaC));
        if(acIn>0){const add=acIn*cfg.etaC;stored+=add;chargedGrid+=acIn;losses+=acIn-add;}
        clippedExport+=Math.max(0,exportKWh-acIn);
      } else if(p>0){
        const importKWh=p*dtH/1000; importRaw+=importKWh;
        const acOut=Math.max(0,Math.min(importKWh,cfg.maxW*dtH/1000,stored*cfg.etaD));
        if(acOut>0){const take=acOut/cfg.etaD;stored-=take;dischargedGrid+=acOut;losses+=take-acOut;}
      }
    }
    const throughput=chargedGrid+dischargedGrid;
    const avoidedImportValue=dischargedGrid*TARIFF.importReplay;
    const lostExportCredit=chargedGrid*TARIFF.exportCredit;
    return {date:day.date_local,samples:samples.length,exportRaw,importRaw,chargedGrid,dischargedGrid,losses,cycles:throughput/(2*cfg.usableKWh),endStored:stored,clippedExport,avoidedImportValue,lostExportCredit,netEuro:avoidedImportValue-lostExportCredit};
  }

  function replayRows(history,cfg){ return (history.days||[]).map(d=>simulateDay(d,cfg)).filter(Boolean).slice(-7); }
  function aggregate(rows){
    return rows.reduce((a,r)=>{['chargedGrid','dischargedGrid','losses','cycles','exportRaw','importRaw','clippedExport','avoidedImportValue','lostExportCredit','netEuro'].forEach(k=>a[k]+=r[k]||0);return a;},{chargedGrid:0,dischargedGrid:0,losses:0,cycles:0,exportRaw:0,importRaw:0,clippedExport:0,avoidedImportValue:0,lostExportCredit:0,netEuro:0});
  }

  function renderDecision(history,payload){
    const sec=el('section','ps-section ps-decision'); sec.append(el('h2','', 'Wat betekent dit voor de batterijkeuze?'));
    const s=payload.plan?.scenario||{};
    const mainCfg={usableKWh:Number(s.usableWindowKWh)||10.08,maxW:Number(s.acChargeLimitW)||3300,etaC:Number(s.chargeEfficiency)||0.95,etaD:Number(s.dischargeEfficiency)||0.95};
    const smallCfg={usableKWh:6.72,maxW:2500,etaC:mainCfg.etaC,etaD:mainCfg.etaD};
    const mainRows=replayRows(history,mainCfg), smallRows=replayRows(history,smallCfg), main=aggregate(mainRows), small=aggregate(smallRows);
    if(!mainRows.length){sec.append(el('div','ps-empty','Nog onvoldoende afgeronde daghistorie voor financiële vergelijking.'));return sec;}
    const deltaEuro=main.netEuro-small.netEuro, deltaImport=main.dischargedGrid-small.dischargedGrid;
    let judgement='Nog onvoldoende historie voor maatadvies';
    if(mainRows.length>=2){
      if(deltaEuro<0.10&&deltaImport<0.5) judgement='9,6 kWh presteert in deze meetperiode vrijwel gelijk';
      else if(deltaEuro<0.50) judgement='14,4 kWh heeft beperkt maar zichtbaar voordeel';
      else judgement='14,4 kWh wordt in deze meetperiode aantoonbaar beter benut';
    }
    const lead=el('div','ps-decision-lead'); lead.append(el('strong','',judgement),el('span','',` · gebaseerd op ${mainRows.length} afgeronde dagen`)); sec.append(lead);
    const grid=el('div','ps-grid'); grid.append(
      card('Financieel effect 14,4 kWh',euro(main.netEuro),`${fmtKWh(main.dischargedGrid)} netimport vermeden`),
      card('Waarde vermeden inkoop',euro(main.avoidedImportValue),`tegen € ${fmt(TARIFF.importReplay,5)}/kWh`),
      card('Gemiste terugleververgoeding',euro(main.lostExportCredit),`${fmtKWh(main.chargedGrid)} opgeslagen export × € ${fmt(TARIFF.exportCredit,5)}`),
      card('Extra voordeel vs 9,6 kWh',euro(deltaEuro),`${fmtKWh(deltaImport)} extra vermeden import`),
      card('Export niet opgeslagen',fmtKWh(main.clippedExport),'door vermogen/capaciteit/timing in replay')
    ); sec.append(grid);
    sec.append(el('div','ps-empty',`Netto €-effect = vermeden inkoop minus gemiste terugleververgoeding. Replaytarief: gemiddeld € ${fmt(TARIFF.importReplay,5)}/kWh import; € ${fmt(TARIFF.exportCredit,5)}/kWh teruglevering. Dit is een replay van gemeten P1-data, geen jaarprognose en exclusief batterijafschrijving/degradatie.`));
    return sec;
  }

  function renderReplay(history,payload){
    const sec=el('section','ps-section'); sec.append(el('h2','', 'Historische batterijreplay'));
    const s=payload.plan?.scenario||{}; const cfg={usableKWh:Number(s.usableWindowKWh)||10.08,maxW:Number(s.acChargeLimitW)||3300,etaC:Number(s.chargeEfficiency)||0.95,etaD:Number(s.dischargeEfficiency)||0.95};
    const rows=replayRows(history,cfg).reverse();
    if(!rows.length){sec.append(el('div','ps-empty','Nog onvoldoende daghistorie voor replay.'));return sec;}
    const sum=aggregate(rows);
    const grid=el('div','ps-grid ps-replay-summary'); grid.append(
      card('Financieel effect',euro(sum.netEuro),`${euro(sum.avoidedImportValue)} vermeden inkoop − ${euro(sum.lostExportCredit)} gemiste teruglevering`),
      card('Opgeslagen PV/netexport',fmtKWh(sum.chargedGrid),'AC energie richting gesimuleerde accu'),
      card('Vermeden netimport',fmtKWh(sum.dischargedGrid),'theoretisch geleverd uit accu'),
      card('Conversieverlies',fmtKWh(sum.losses),'η laden/ontladen volgens shadow-scenario'),
      card('Equivalent cycli',fmt(sum.cycles,2),'over getoonde afgeronde dagen')
    ); sec.append(grid);
    const table=el('table','ps-replay-table'); const th=el('tr');['Dag','Export gemeten','Naar accu','Import gemeten','Vermeden import','€ effect','Verlies','Cycli'].forEach(x=>th.append(el('th','',x)));const head=el('thead');head.append(th);table.append(head);const tb=el('tbody');rows.forEach(r=>{const tr=el('tr');[r.date,fmtKWh(r.exportRaw),fmtKWh(r.chargedGrid),fmtKWh(r.importRaw),fmtKWh(r.dischargedGrid),euro(r.netEuro),fmtKWh(r.losses),fmt(r.cycles,2)].forEach(x=>tr.append(el('td','',x)));tb.append(tr)});table.append(tb);const sc=el('div','ps-timeline-scroll');sc.append(table);sec.append(sc);
    sec.append(el('p','ps-footnote','Replay is een energetische en financiële upper-bound op basis van P1, het afgesproken batterijmodel en het expliciete huidige FIXED-tariefmodel. Geen jaarprognose; exclusief batterijdegradatie en afschrijving.'));
    return sec;
  }

  async function load(){
    const status=document.getElementById('ps-status');
    try{
      const [payload,history]=await Promise.all([
        fetchJson(root.dataset.source,'energy-planner-shadow.json',true),
        fetchJson(root.dataset.history,'energy-day-series-7d.json',false)
      ]);
      if(payload.observabilityOnly!==true||payload.controlImpact!=='NONE')throw new Error('observability safety marker ontbreekt');
      status.replaceChildren(renderDecision(history,payload),renderScore(payload),renderTimeline(payload),renderReplay(history,payload));
    }catch(e){status.replaceChildren(el('div','ps-error',`Planner Shadow kon niet worden geladen: ${e.message}`));}
  }
  load();
})();
