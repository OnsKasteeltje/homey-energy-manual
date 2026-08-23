(() => {
  const root = document.getElementById('planner-shadow');
  if (!root) return;

  const RAW_BASE = 'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/';
  const BC = {
    importPrice: 0.25500,
    exportValue: 0.00250,
    etaRT: 0.85,
    nominalKWh: 14.4,
    oldWindowKWh: 10.08,   // 20–90% SOC
    wideWindowKWh: 12.24,  // 10–95% SOC
    acLimitW: 3300,
    feederLimitA: 16,
    voltageV: 230,
    batteryContinuousW: 3600,
    investmentEuro: 4880,
    oldAnnualEuro: 687,
    oldAnnualOutputKWh: 2720,
    theoreticalWideAnnualEuro: 834,
    theoreticalWideAnnualOutputKWh: 3303
  };
  BC.hardwareMaxW = Math.min(BC.acLimitW, BC.feederLimitA * BC.voltageV, BC.batteryContinuousW);

  const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
  const fmt=(v,d=1)=>Number.isFinite(Number(v))?Number(v).toLocaleString('nl-NL',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
  const fmtKWh=v=>`${fmt(v,2)} kWh`, fmtW=v=>Number.isFinite(Number(v))?`${Math.round(Number(v))} W`:'—';
  const euro=v=>Number.isFinite(Number(v))?`€ ${fmt(v,2)}`:'—';
  const local=iso=>{if(!iso)return'—';const d=new Date(iso);return Number.isNaN(d.getTime())?'—':d.toLocaleString('nl-NL',{dateStyle:'short',timeStyle:'short'});};
  const badge=(text,kind='')=>el('span',`ps-badge ${kind}`,text);

  async function fetchJson(primary,rawFile,required=true){
    const urls=[primary,`${RAW_BASE}${rawFile}?ts=${Date.now()}`].filter(Boolean); let last='geen bron geprobeerd';
    for(const url of urls){try{const r=await fetch(url,{cache:'no-store'});if(!r.ok){last=`HTTP ${r.status} op ${url}`;continue;}return await r.json();}catch(e){last=`${e.message} op ${url}`;}}
    if(required) throw new Error(last); return {days:[]};
  }
  function card(title,value,sub=''){const c=el('div','ps-card');c.append(el('div','ps-card-title',title),el('div','ps-card-value',value));if(sub)c.append(el('div','ps-card-sub',sub));return c;}

  function renderScore(payload){
    const p=payload.plan||{},i=p.inputs||{},st=payload.status||{};const sec=el('section','ps-section');sec.append(el('h2','','Actuele plannerstatus'));const g=el('div','ps-grid');
    g.append(
      card('Status',p.plannerStatus||st.status||'—',`gegenereerd ${local(p.generatedAt)}`),
      card('Batterij','14,4 kWh','3 × Pylontech US5000'),
      card('SOC-vergelijking','20–90% ↔ 10–95%',`${fmtKWh(BC.oldWindowKWh)} ↔ ${fmtKWh(BC.wideWindowKWh)} bruikbaar`),
      card('Hardwaregrens',fmtW(BC.hardwareMaxW),`${BC.feederLimitA} A × ${BC.voltageV} V = ${fmtW(BC.feederLimitA*BC.voltageV)}; ESS bewust lager begrensd`),
      card('Contractscenario','Zonder saldering',`€ ${fmt(BC.importPrice,4)}/kWh afname · € ${fmt(BC.exportValue,4)}/kWh terugleverwaarde`),
      card('Tesla',i.tesla?.deadlineActive?`${fmtKWh(i.tesla.remainingKWh)} resterend`:'Geen deadline-MUST',i.tesla?.deadlineActive?`deadline ${local(i.tesla.deadlineAt)}`:''),
      card('Warm water',i.warmWater?.goalReachedToday?'Dagdoel gehaald':`${fmt(i.warmWater?.remainingFallbackMin,0)} min resterend`,i.warmWater?.catchupRequired?'MUST_CATCHUP':'deadline 19:00')
    );sec.append(g);const q=el('div','ps-quality');q.append(badge('SHADOW','good'),badge('CONTROL IMPACT: NONE','good'),badge(`PV forecast: ${i.pvForecast?.quality||'—'}`,i.pvForecast?.quality==='SUMMARY_ONLY'?'warn':''));sec.append(q);return sec;
  }

  function renderTimeline(payload){
    const actions=payload.plan?.plan?.actions||[];const sec=el('section','ps-section');sec.append(el('h2','','24-uurs plan'));
    if(!actions.length){sec.append(el('div','ps-empty','Bij het vaste contract zijn er nu geen kunstmatige kwartierprijzen en dus geen dispatch-slots. De historische replay hieronder blijft wel bruikbaar.'));return sec;}
    const sc=el('div','ps-timeline-scroll'),t=el('table','ps-timeline'),h=el('tr');['Tijd','Prijs','Batterij','Tesla','Warm water'].forEach(x=>h.append(el('th','',x)));const hd=el('thead');hd.append(h);t.append(hd);const b=el('tbody');
    actions.forEach(a=>{const tr=el('tr');[new Date(a.start).toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'}),Number.isFinite(Number(a.price))?`€ ${Number(a.price).toFixed(3)}`:'—',a.battery||'HOLD',a.tesla||'HOLD',a.warmWater||'HOLD'].forEach((x,j)=>tr.append(el('td',j>1&&x!=='HOLD'?'ps-active':'',x)));b.append(tr);});t.append(b);sc.append(t);sec.append(sc);return sec;
  }

  function simulateDay(day,cfg,initialStored=0){
    const samples=(day.samples||[]).filter(s=>Number.isFinite(Number(s.p1W))).sort((a,b)=>new Date(a.ts)-new Date(b.ts));if(samples.length<2)return null;
    let stored=Math.max(0,Math.min(cfg.usableKWh,Number(initialStored)||0)),charged=0,discharged=0,loss=0,exportRaw=0,importRaw=0,clipped=0,powerMiss=0,capacityMiss=0,maxW=0;const startStored=stored;
    for(let i=0;i<samples.length;i++){
      const s=samples[i],n=samples[i+1];let dt=5/60;if(n){const d=(new Date(n.ts)-new Date(s.ts))/3600000;if(d>0&&d<0.5)dt=d;}const p=Number(s.p1W),pCap=cfg.maxW*dt/1000;
      if(p<0){const e=(-p)*dt/1000;exportRaw+=e;const cCap=Math.max(0,(cfg.usableKWh-stored)/cfg.etaC),acIn=Math.max(0,Math.min(e,pCap,cCap));powerMiss+=Math.max(0,Math.min(e,cCap)-acIn);capacityMiss+=Math.max(0,Math.min(e,pCap)-acIn);if(acIn>0){const add=acIn*cfg.etaC;stored+=add;charged+=acIn;loss+=acIn-add;maxW=Math.max(maxW,acIn/dt*1000);}clipped+=Math.max(0,e-acIn);}
      else if(p>0){const e=p*dt/1000;importRaw+=e;const eCap=Math.max(0,stored*cfg.etaD),acOut=Math.max(0,Math.min(e,pCap,eCap));powerMiss+=Math.max(0,Math.min(e,eCap)-acOut);if(acOut>0){const take=acOut/cfg.etaD;stored-=take;discharged+=acOut;loss+=take-acOut;maxW=Math.max(maxW,acOut/dt*1000);}}
    }
    const avoid=discharged*BC.importPrice,lost=charged*BC.exportValue;
    return {date:day.date_local,startStored,endStored:stored,charged,discharged,loss,exportRaw,importRaw,clipped,powerMiss,capacityMiss,maxW,avoid,lost,net:avoid-lost};
  }
  function replayRows(history,cfg){const rows=[];let stored=0;for(const day of (history.days||[]).slice(-7)){const r=simulateDay(day,cfg,stored);if(!r)continue;rows.push(r);stored=r.endStored;}return rows;}
  function aggregate(rows){return rows.reduce((a,r)=>{['charged','discharged','loss','exportRaw','importRaw','clipped','powerMiss','capacityMiss','avoid','lost','net'].forEach(k=>a[k]+=r[k]||0);if(a.count===0)a.startStored=r.startStored||0;a.endStored=r.endStored||0;a.maxW=Math.max(a.maxW,r.maxW||0);a.count++;return a;},{charged:0,discharged:0,loss:0,exportRaw:0,importRaw:0,clipped:0,powerMiss:0,capacityMiss:0,avoid:0,lost:0,net:0,startStored:0,endStored:0,maxW:0,count:0});}

  function renderDecision(history){
    const sec=el('section','ps-section ps-decision');sec.append(el('h2','','Potentiële besparing'));
    const eta=Math.sqrt(BC.etaRT);
    const oldCfg={usableKWh:BC.oldWindowKWh,maxW:BC.hardwareMaxW,etaC:eta,etaD:eta};
    const wideCfg={usableKWh:BC.wideWindowKWh,maxW:BC.hardwareMaxW,etaC:eta,etaD:eta};
    const oldRows=replayRows(history,oldCfg),wideRows=replayRows(history,wideCfg),old=aggregate(oldRows),wide=aggregate(wideRows);
    if(!wideRows.length){sec.append(el('div','ps-empty','Nog onvoldoende daghistorie voor vergelijking.'));return sec;}

    const measuredExtraEuro=wide.net-old.net, measuredExtraKWh=wide.discharged-old.discharged;
    const measuredPct=old.net>0?100*measuredExtraEuro/old.net:0;
    const capacityPct=100*(BC.wideWindowKWh/BC.oldWindowKWh-1);
    const theoreticalPayback=BC.investmentEuro/BC.theoreticalWideAnnualEuro;

    sec.append(el('h3','','Nieuwe BC · grotere SOC-range 10–95%'));
    sec.append(el('p','ps-footnote','De grotere range geeft 12,24 kWh bruikbare opslag in plaats van 10,08 kWh: +21,4%. De €834/jaar hieronder is de theoretische bovengrens als die extra ruimte jaarlijks volledig evenredig benut kan worden. De replay eronder laat zien hoeveel voordeel de huidige meetdagen werkelijk tonen.'));
    const forecast=el('div','ps-grid');forecast.append(
      card('Bruikbaar venster',`${fmtKWh(BC.wideWindowKWh)}`,`10–95% SOC · +${fmt(capacityPct,1)}% t.o.v. 20–90%`),
      card('Theoretisch jaarpotentieel',`€ ${fmt(BC.theoreticalWideAnnualEuro,0)} / jaar`,`oude referentie € ${fmt(BC.oldAnnualEuro,0)}/jaar · bovengrens, nog niet empirisch bewezen`),
      card('Theoretische nuttige output',`${fmt(BC.theoreticalWideAnnualOutputKWh,0)} kWh / jaar`,`oude referentie ${fmt(BC.oldAnnualOutputKWh,0)} kWh/jaar`),
      card('Theoretische TVT',`${fmt(theoreticalPayback,1)} jaar`,`€ ${fmt(BC.investmentEuro,0)} ÷ € ${fmt(BC.theoreticalWideAnnualEuro,0)}/jaar`)
    );sec.append(forecast);

    sec.append(el('h3','',`Replay-vergelijking · ${wideRows.length} gemeten dagen`));
    sec.append(el('p','ps-footnote','Beide scenario’s gebruiken exact dezelfde P1-data, 3,3 kW hardwarelimiet, 85% round-trip rendement en continu SOC over daggrenzen. Alleen het bruikbare SOC-venster verschilt.'));
    const compare=el('div','ps-grid');compare.append(
      card('20–90% SOC',euro(old.net),`${fmtKWh(old.discharged)} vermeden netimport · ${fmtKWh(BC.oldWindowKWh)} bruikbaar`),
      card('10–95% SOC',euro(wide.net),`${fmtKWh(wide.discharged)} vermeden netimport · ${fmtKWh(BC.wideWindowKWh)} bruikbaar`),
      card('Extra door grotere range',euro(measuredExtraEuro),`${fmtKWh(measuredExtraKWh)} extra vermeden netimport in deze meetperiode`),
      card('Gemeten relatieve verbetering',`${fmt(measuredPct,1)}%`,`tegenover +${fmt(capacityPct,1)}% extra bruikbare capaciteit`)
    );sec.append(compare);

    const story=el('div','ps-empty');story.append(el('strong','',`Met 10–95% SOC zou de batterij in deze meetperiode ${euro(wide.net)} netto hebben bespaard.`));story.append(document.createTextNode(` Daarvoor nam zij ${fmtKWh(wide.charged)} PV-overschot op en voorkwam later ${fmtKWh(wide.discharged)} netinkoop. De oude 20–90%-range kwam in dezelfde periode uit op ${euro(old.net)}. Het verschil van ${euro(measuredExtraEuro)} is dus het daadwerkelijk gemeten voordeel van de 2,16 kWh extra bruikbare opslagruimte in deze replay.`));sec.append(story);

    sec.append(el('h4','','Energiebalans 10–95%'));
    const residual=wide.charged-wide.discharged-wide.loss-(wide.endStored-wide.startStored);
    const energy=el('div','ps-grid');energy.append(
      card('PV naar batterij',fmtKWh(wide.charged),'AC-energie die anders zou zijn teruggeleverd'),
      card('Batterij naar huis',fmtKWh(wide.discharged),'netinkoop die daarmee wordt voorkomen'),
      card('Conversieverlies',fmtKWh(wide.loss),'85% round-trip rendement'),
      card('Eindvoorraad batterij',fmtKWh(wide.endStored),'loopt continu door over daggrenzen'),
      card('Balansafwijking',fmtKWh(Math.abs(residual)),'hoort circa 0 kWh te zijn'),
      card('PV nog teruggeleverd',fmtKWh(wide.clipped),'niet opgeslagen door timing, vermogen of volle batterij'),
      card('Gemist door 3,3 kW-grens',fmtKWh(wide.powerMiss),'potentieel buiten de ingestelde vermogensgrens'),
      card('Gemist doordat batterij vol was',fmtKWh(wide.capacityMiss),'directe indicatie of extra SOC-range waarde toevoegt')
    );sec.append(energy);

    sec.append(el('p','ps-footnote','Interpretatie BC: €834/jaar blijft voorlopig een optimistische bovengrens. De replay-vergelijking is de empirische validatie. Naarmate meer representatieve dagen en seizoenen beschikbaar zijn, kan de vaste jaarreferentie worden vervangen door een uit meetdata afgeleide businesscase.'));
    return sec;
  }

  function renderReplay(history){
    const sec=el('section','ps-section');sec.append(el('h2','','Historische batterijreplay · 10–95% SOC'));
    const eta=Math.sqrt(BC.etaRT),cfg={usableKWh:BC.wideWindowKWh,maxW:BC.hardwareMaxW,etaC:eta,etaD:eta},rows=replayRows(history,cfg);
    if(!rows.length){sec.append(el('div','ps-empty','Nog onvoldoende daghistorie voor replay.'));return sec;}
    const sum=aggregate(rows),g=el('div','ps-grid ps-replay-summary');g.append(card('Netto voordeel',euro(sum.net),`${euro(sum.avoid)} vermeden inkoop − ${euro(sum.lost)} gemiste teruglevering`),card('PV naar batterij',fmtKWh(sum.charged),'AC energie richting gesimuleerde accu'),card('Batterij naar huis',fmtKWh(sum.discharged),'vermeden netinkoop'),card('Conversieverlies',fmtKWh(sum.loss),`ηRT ${fmt(BC.etaRT*100,0)}%`),card('Eindenergie batterij',fmtKWh(sum.endStored),'voorraad loopt door over daggrenzen'));sec.append(g);
    const sc=el('div','ps-timeline-scroll'),t=el('table','ps-replay-table'),h=el('tr');['Dag','Start accu','PV-export','PV naar accu','Netimport','Door accu vermeden','Netto € voordeel','Eind accu'].forEach(x=>h.append(el('th','',x)));const hd=el('thead');hd.append(h);t.append(hd);const b=el('tbody');rows.slice().reverse().forEach(r=>{const tr=el('tr');[r.date,fmtKWh(r.startStored),fmtKWh(r.exportRaw),fmtKWh(r.charged),fmtKWh(r.importRaw),fmtKWh(r.discharged),euro(r.net),fmtKWh(r.endStored)].forEach(x=>tr.append(el('td','',x)));b.append(tr);});t.append(b);sc.append(t);sec.append(sc);return sec;
  }

  async function load(){
    const status=document.getElementById('ps-status');
    try{const[payload,history]=await Promise.all([fetchJson(root.dataset.source,'energy-planner-shadow.json',true),fetchJson(root.dataset.history,'energy-day-series-7d.json',false)]);if(payload.observabilityOnly!==true||payload.controlImpact!=='NONE')throw new Error('observability safety marker ontbreekt');status.replaceChildren(renderDecision(history),renderScore(payload),renderTimeline(payload),renderReplay(history));}
    catch(e){status.replaceChildren(el('div','ps-error',`Planner Shadow kon niet worden geladen: ${e.message}`));}
  }
  load();
})();