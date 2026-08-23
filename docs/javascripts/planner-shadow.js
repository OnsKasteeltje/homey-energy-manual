(() => {
  const root = document.getElementById('planner-shadow');
  if (!root) return;

  const RAW_BASE = 'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/';
  const el = (tag, cls, text) => { const n=document.createElement(tag); if(cls)n.className=cls; if(text!==undefined)n.textContent=text; return n; };
  const fmt = (v,d=1) => Number.isFinite(Number(v)) ? Number(v).toFixed(d) : '—';
  const fmtKWh = v => `${fmt(v,2)} kWh`;
  const fmtW = v => Number.isFinite(Number(v)) ? `${Math.round(Number(v))} W` : '—';
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

  function simulateDay(day, scenario){
    const samples=(day.samples||[]).filter(s=>Number.isFinite(Number(s.p1W))).sort((a,b)=>new Date(a.ts)-new Date(b.ts));
    if(samples.length<2)return null;
    const cap=Number(scenario.usableWindowKWh)||10.08, maxW=Number(scenario.acChargeLimitW)||3300, etaC=Number(scenario.chargeEfficiency)||0.95, etaD=Number(scenario.dischargeEfficiency)||0.95;
    let stored=0, chargedGrid=0, dischargedGrid=0, losses=0, exportRaw=0, importRaw=0;
    for(let idx=0;idx<samples.length;idx++){
      const s=samples[idx], next=samples[idx+1]; let dtH=5/60;
      if(next){const d=(new Date(next.ts)-new Date(s.ts))/3600000;if(d>0&&d<0.5)dtH=d;}
      const p=Number(s.p1W); if(p<0){
        const exportKWh=(-p)*dtH/1000; exportRaw+=exportKWh; const acIn=Math.min(exportKWh,maxW*dtH/1000,(cap-stored)/etaC); if(acIn>0){const add=acIn*etaC;stored+=add;chargedGrid+=acIn;losses+=acIn-add;}
      } else if(p>0){
        const importKWh=p*dtH/1000; importRaw+=importKWh; const acOut=Math.min(importKWh,maxW*dtH/1000,stored*etaD); if(acOut>0){const take=acOut/etaD;stored-=take;dischargedGrid+=acOut;losses+=take-acOut;}
      }
    }
    const throughput=chargedGrid+dischargedGrid, cycles=throughput/(2*cap);
    return {date:day.date_local,samples:samples.length,exportRaw,importRaw,chargedGrid,dischargedGrid,losses,cycles,endStored:stored};
  }

  function renderReplay(history,payload){
    const sec=el('section','ps-section'); sec.append(el('h2','', 'Historische batterijreplay'));
    const scenario=payload.plan?.scenario||{}; const rows=(history.days||[]).map(d=>simulateDay(d,scenario)).filter(Boolean).slice(-7).reverse();
    if(!rows.length){sec.append(el('div','ps-empty','Nog onvoldoende daghistorie voor replay.'));return sec;}
    const sum=rows.reduce((a,r)=>{Object.keys(a).forEach(k=>a[k]+=r[k]||0);return a;},{chargedGrid:0,dischargedGrid:0,losses:0,cycles:0,exportRaw:0,importRaw:0});
    const grid=el('div','ps-grid ps-replay-summary'); grid.append(
      card('Opgeslagen PV/netexport',fmtKWh(sum.chargedGrid),'AC energie richting gesimuleerde accu'),
      card('Vermeden netimport',fmtKWh(sum.dischargedGrid),'theoretisch geleverd uit accu'),
      card('Conversieverlies',fmtKWh(sum.losses),'η laden/ontladen volgens shadow-scenario'),
      card('Equivalent cycli',fmt(sum.cycles,2),'over getoonde afgeronde dagen'),
      card('€ effect','Nog niet berekend','wacht op expliciet reproduceerbaar tariefmodel')
    ); sec.append(grid);
    const table=el('table','ps-replay-table'); const th=el('tr');['Dag','Export gemeten','Naar accu','Import gemeten','Vermeden import','Verlies','Cycli'].forEach(x=>th.append(el('th','',x)));const head=el('thead');head.append(th);table.append(head);const tb=el('tbody');rows.forEach(r=>{const tr=el('tr');[r.date,fmtKWh(r.exportRaw),fmtKWh(r.chargedGrid),fmtKWh(r.importRaw),fmtKWh(r.dischargedGrid),fmtKWh(r.losses),fmt(r.cycles,2)].forEach(x=>tr.append(el('td','',x)));tb.append(tr)});table.append(tb);const sc=el('div','ps-timeline-scroll');sc.append(table);sec.append(sc);
    sec.append(el('p','ps-footnote','Replay is een energetische upper-bound op basis van P1 en het afgesproken batterijmodel. Hij kent nog geen echte batterij-SOC, degradatiekosten, net-/fasebeperkingen of tariefwaarde per interval en is daarom geen gerealiseerde besparing.'));
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
      status.replaceChildren(renderScore(payload),renderTimeline(payload),renderReplay(history,payload));
    }catch(e){status.replaceChildren(el('div','ps-error',`Planner Shadow kon niet worden geladen: ${e.message}`));}
  }
  load();
})();
