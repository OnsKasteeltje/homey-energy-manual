(() => {
  const root = document.getElementById('planner-shadow');
  if (!root) return;

  // FIXED-contract replay assumptions, based on the currently recorded contract.
  // Export is treated as a €0.150/kWh credit (opportunity cost when storing PV).
  const TARIFF = {
    importNormal: 0.23790,
    importOffPeak: 0.23548,
    importReplay: (0.23790 + 0.23548) / 2,
    exportCredit: 0.15000,
    label: 'FIXED huidig contract · import replaygemiddelde €0,23669/kWh · terugleververgoeding €0,15000/kWh'
  };

  const fmt = (v, d=2) => Number.isFinite(Number(v)) ? Number(v).toLocaleString('nl-NL',{minimumFractionDigits:d,maximumFractionDigits:d}) : '—';
  const euro = v => Number.isFinite(Number(v)) ? `€ ${fmt(v,2)}` : '—';
  const kwh = v => Number.isFinite(Number(v)) ? `${fmt(v,2)} kWh` : '—';

  async function fetchJson(primary, fallback) {
    let r = await fetch(primary, {cache:'no-store'});
    if (!r.ok && fallback) r = await fetch(fallback, {cache:'no-store'});
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  function replayDay(day, cfg) {
    const samples=(day.samples||[]).filter(s=>Number.isFinite(Number(s.p1W))).sort((a,b)=>new Date(a.ts)-new Date(b.ts));
    if(samples.length<2) return null;
    let stored=0, peakStored=0, charged=0, discharged=0, exportRaw=0, importRaw=0, clippedExport=0;
    for(let idx=0;idx<samples.length;idx++){
      const s=samples[idx], next=samples[idx+1]; let dtH=5/60;
      if(next){const d=(new Date(next.ts)-new Date(s.ts))/3600000;if(d>0&&d<0.5)dtH=d;}
      const p=Number(s.p1W);
      if(p<0){
        const available=(-p)*dtH/1000; exportRaw+=available;
        const powerCap=cfg.maxW*dtH/1000;
        const roomAc=Math.max(0,(cfg.usableKWh-stored)/cfg.etaC);
        const acIn=Math.max(0,Math.min(available,powerCap,roomAc));
        charged+=acIn; stored+=acIn*cfg.etaC; peakStored=Math.max(peakStored,stored); clippedExport+=Math.max(0,available-acIn);
      } else if(p>0){
        const demand=p*dtH/1000; importRaw+=demand;
        const powerCap=cfg.maxW*dtH/1000;
        const acOut=Math.max(0,Math.min(demand,powerCap,stored*cfg.etaD));
        discharged+=acOut; stored-=acOut/cfg.etaD;
      }
    }
    const avoidedImportValue=discharged*TARIFF.importReplay;
    const lostExportCredit=charged*TARIFF.exportCredit;
    const netEuro=avoidedImportValue-lostExportCredit;
    return {charged,discharged,exportRaw,importRaw,clippedExport,peakStored,netEuro,avoidedImportValue,lostExportCredit};
  }

  function aggregate(history,cfg){
    const rows=(history.days||[]).map(d=>replayDay(d,cfg)).filter(Boolean);
    return rows.reduce((a,r)=>{Object.keys(a).forEach(k=>a[k]+=r[k]||0);return a;},{days:rows.length,charged:0,discharged:0,exportRaw:0,importRaw:0,clippedExport:0,peakStored:0,netEuro:0,avoidedImportValue:0,lostExportCredit:0});
  }

  function makeCard(title,value,sub){const c=document.createElement('div');c.className='ps-card';c.innerHTML=`<div class="ps-card-title"></div><div class="ps-card-value"></div><div class="ps-card-sub"></div>`;c.children[0].textContent=title;c.children[1].textContent=value;c.children[2].textContent=sub||'';return c;}

  function render(history){
    const target=document.createElement('section'); target.className='ps-section ps-decision';
    const h=document.createElement('h2');h.textContent='Wat betekent dit voor de batterijkeuze?';target.append(h);

    const mainCfg={usableKWh:10.08,maxW:3300,etaC:0.95,etaD:0.95};
    const smallCfg={usableKWh:6.72,maxW:2500,etaC:0.95,etaD:0.95};
    const main=aggregate(history,mainCfg), small=aggregate(history,smallCfg);
    const deltaEuro=main.netEuro-small.netEuro;
    const deltaImport=main.discharged-small.discharged;
    const period=main.days ? `${main.days} afgeronde dag${main.days===1?'':'en'}` : 'geen afgeronde dagen';

    let judgement='Nog onvoldoende historie';
    if(main.days>=2){
      if(deltaEuro < 0.10 && deltaImport < 0.5) judgement='9,6 kWh presteert in deze meetperiode vrijwel gelijk';
      else if(deltaEuro < 0.50) judgement='14,4 kWh heeft beperkt maar zichtbaar voordeel';
      else judgement='14,4 kWh wordt in deze meetperiode aantoonbaar beter benut';
    }

    const lead=document.createElement('div'); lead.className='ps-decision-lead';
    lead.innerHTML='<strong></strong><span></span>'; lead.children[0].textContent=judgement; lead.children[1].textContent=` · gebaseerd op ${period}`; target.append(lead);

    const grid=document.createElement('div');grid.className='ps-grid';
    grid.append(
      makeCard('€ effect 14,4 kWh',euro(main.netEuro),`${kwh(main.discharged)} netimport vermeden`),
      makeCard('Waarde vermeden import',euro(main.avoidedImportValue),`tegen € ${fmt(TARIFF.importReplay,5)}/kWh`),
      makeCard('Gemiste terugleververgoeding',euro(main.lostExportCredit),`${kwh(main.charged)} opgeslagen export × € 0,15000`),
      makeCard('Verschil vs 9,6 kWh',euro(deltaEuro),`${kwh(deltaImport)} extra vermeden import`),
      makeCard('Export niet opgeslagen',kwh(main.clippedExport),'door vermogen/capaciteit/timing in replay')
    ); target.append(grid);

    const expl=document.createElement('div');expl.className='ps-empty';
    expl.textContent=`Euro-effect = waarde van vermeden netimport minus de terugleververgoeding die je misloopt doordat dezelfde kWh in de accu gaat. ${TARIFF.label}. Dit is een replay van gemeten P1-data, geen jaarprognose en exclusief batterijdegradatie/afschrijving.`;
    target.append(expl);

    const status=document.getElementById('ps-status');
    root.insertBefore(target,status);
  }

  (async()=>{
    try{
      const history=await fetchJson(root.dataset.history,'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-day-series-7d.json');
      render(history);
    }catch(e){
      const n=document.createElement('div');n.className='ps-error';n.textContent=`Beslissamenvatting kon niet worden geladen: ${e.message}`;const status=document.getElementById('ps-status');root.insertBefore(n,status);
    }
  })();
})();
