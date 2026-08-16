(function(){
  const BASE='/homey-energy-manual/';
  const REFRESH_MS=5*60*1000;
  const SYNC_TOLERANCE_MS=90*1000;
  const LIVE_FRESH_MS=5*60*1000;
  const fmtW=v=>`${Math.round(Number(v)||0).toLocaleString('nl-NL')} W`;
  const fmtTime=ts=>Number.isFinite(ts)?new Date(ts).toLocaleString('nl-NL'):'onbekend';
  const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
  async function get(path){const r=await fetch(`${BASE}data/${path}?ts=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`${path}: HTTP ${r.status}`);return r.json();}
  const numOrNull=v=>Number.isFinite(Number(v))?Number(v):null;
  const appliance=(bs,key,phase)=>{const w=numOrNull(bs[`${key}W`]);const active=bs[`${key}Active`];return {w,active:active===true?true:active===false?false:null,phase};};
  const applianceValue=a=>a.w!==null?fmtW(Math.max(0,a.w)):a.active===true?'ACTIEF':a.active===false?'idle':'—';
  const applianceSub=a=>`${a.phase?`${a.phase} · `:''}${a.w!==null?'live gemeten':a.active!==null?'Homey-status':'geen live wattage'}`;

  function node(x,y,w,h,kicker,title,value,sub='',cls=''){
    return `<g class="energy-node ${cls}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="14"/><text x="${x+w/2}" y="${y+22}" text-anchor="middle" class="energy-kicker">${kicker}</text><text x="${x+w/2}" y="${y+47}" text-anchor="middle" class="energy-title">${title}</text><text x="${x+w/2}" y="${y+75}" text-anchor="middle" class="energy-value">${value}</text>${sub?`<text x="${x+w/2}" y="${y+97}" text-anchor="middle" class="energy-sub">${sub}</text>`:''}</g>`;
  }
  function path(d,w,kind='grid',active=true,label='',lx=0,ly=0,forceWidth=null){
    const width=forceWidth!==null?forceWidth:(active?clamp(2.5+Math.abs(Number(w)||0)/750,3,10):2);
    return `<g><path class="energy-path energy-${kind} ${active?'is-active':'is-idle'}" d="${d}" style="stroke-width:${width}" marker-end="url(#arrow-${kind})"/>${label?`<text x="${lx}" y="${ly}" text-anchor="middle" class="energy-edge-label">${label}</text>`:''}</g>`;
  }

  function closestPhaseSample(samples,targetTs){
    if(!samples.length || !Number.isFinite(targetTs))return {sample:null,delta:Infinity};
    let best=null,bestDelta=Infinity;
    for(const sample of samples){
      const ts=new Date(sample.ts||sample.generated_at||0).getTime();
      if(!Number.isFinite(ts))continue;
      const delta=Math.abs(ts-targetTs);
      if(delta<bestDelta){best=sample;bestDelta=delta;}
    }
    return {sample:best,delta:bestDelta};
  }

  async function load(){
    const root=document.getElementById('live-energy-flow'); if(!root)return;
    try{
      const [phase,base,m7]=await Promise.all([get('pv-phase-24h.json'),get('shadow-baseline-v01.json'),get('m7-opportunity.json').catch(()=>null)]);
      const phaseSamples=phase.samples||[], bs=base.latest||{}, ml=m7?.latest||{};
      const livePs=phaseSamples.at(-1)||{};
      const liveTs=new Date(livePs.ts||phase.generated_at||0).getTime();
      const shadowTs=new Date(bs.ts||base.generated_at||0).getTime();
      const match=closestPhaseSample(phaseSamples,shadowTs);
      const splitPs=match.sample||{};
      const splitSynchronized=!!match.sample && match.delta<=SYNC_TOLERANCE_MS;
      const splitNearLive=Number.isFinite(liveTs)&&Number.isFinite(shadowTs)&&Math.abs(liveTs-shadowTs)<=SYNC_TOLERANCE_MS;
      const liveFresh=Number.isFinite(liveTs)&&Date.now()-liveTs<=LIVE_FRESH_MS;
      const splitUsable=splitSynchronized&&splitNearLive;

      // Bovenste energiebalans gebruikt altijd de nieuwste 2-minuten P1/PV-meetset.
      const se=Math.max(0,Number(livePs.solarEdgeW)||0), gw42=Math.max(0,Number(livePs.goodWe4200W)||0), gw20=Math.max(0,Number(livePs.goodWe2000W)||0), pv=se+gw42+gw20;
      const p1=Number.isFinite(Number(livePs.p1W))?Number(livePs.p1W):0;
      const importW=Math.max(0,p1), exportW=Math.max(0,-p1), houseTotal=Math.max(0,pv+p1);
      const l1=numOrNull(livePs.l1W),l2=numOrNull(livePs.l2W),l3=numOrNull(livePs.l3W);
      const phaseSub=[l1!==null?`L1 ${fmtW(l1)}`:'',l2!==null?`L2 ${fmtW(l2)}`:'',l3!==null?`L3 ${fmtW(l3)}`:''].filter(Boolean).join(' · ');

      // Apparaatuitsplitsing mag alleen aan de live balans worden gekoppeld als de timestamps <=90 s verschillen.
      const teslaRaw=Math.max(0,Number(bs.teslaW)||0), boilerRaw=Math.max(0,Number(bs.boilerW)||0);
      const tesla=splitUsable?teslaRaw:null, boiler=splitUsable?boilerRaw:null;
      const washer=appliance(bs,'washer','L2'), dryer=appliance(bs,'dryer','L3');
      let other=null;
      if(splitUsable){
        const splitPv=Math.max(0,Number(splitPs.solarEdgeW)||0)+Math.max(0,Number(splitPs.goodWe4200W)||0)+Math.max(0,Number(splitPs.goodWe2000W)||0);
        const splitP1=Number.isFinite(Number(splitPs.p1W))?Number(splitPs.p1W):Number(bs.p1W)||0;
        const splitHouse=Math.max(0,splitPv+splitP1);
        const knownLoads=teslaRaw+boilerRaw+[washer.w,dryer.w].filter(v=>v!==null).reduce((a,b)=>a+Math.max(0,b),0);
        other=Math.max(0,splitHouse-knownLoads);
      }

      const requestedA=Math.max(0,Number(bs.teslaRequestedA??bs.targetA)||0);
      const actualA=Math.max(0,Number(bs.teslaActualAEst)||0);
      const chargeState=String(bs.chargeState||'').toLowerCase();
      const charging=teslaRaw>100 || chargeState.includes('charging');
      let equalizerText='begrenzing niet actief';
      let equalizerDetail='Geen actief laadverzoek';
      if(requestedA>0 && charging){
        if(actualA+0.5<requestedA){equalizerText='mogelijk begrensd'; equalizerDetail='Werkelijke laadstroom lager dan gevraagd';}
        else {equalizerText='geen begrenzing zichtbaar'; equalizerDetail='Werkelijk volgt gevraagd';}
      } else if(requestedA>0 && !charging){
        equalizerText='begrenzing niet vastgesteld'; equalizerDetail='Laadverzoek aanwezig, Tesla levert nog niet';
      }

      const W=1200,H=805;
      let svg=`<svg class="energy-svg energy-dashboard" viewBox="0 0 ${W} ${H}" role="img" aria-label="Live energiestroom"><defs>
        <marker id="arrow-pv" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L0,8 L8,4 z" class="arrow-pv"/></marker>
        <marker id="arrow-grid" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L0,8 L8,4 z" class="arrow-grid"/></marker>
        <marker id="arrow-battery" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L0,8 L8,4 z" class="arrow-battery"/></marker>
      </defs>`;

      svg+=node(30,30,340,115,'PRODUCTIE','SolarEdge SE3680H',fmtW(se),'PV-omvormer','source');
      svg+=node(430,30,340,115,'PRODUCTIE','GoodWe GW4200D-NS',fmtW(gw42),'PV-omvormer','source');
      svg+=node(830,30,340,115,'PRODUCTIE','GoodWe GW2000-XS',fmtW(gw20),'PV-omvormer','source');
      svg+=path(`M200 145 V190 H600`,se,'pv',se>0,'',0,0);
      svg+=path(`M600 145 V220`,gw42,'pv',gw42>0,'',0,0);
      svg+=path(`M1000 145 V190 H600`,gw20,'pv',gw20>0,'',0,0);

      svg+=node(55,255,310,125,'NET / METER (P1)','Grid',fmtW(Math.abs(p1)),p1>0?'import':p1<0?'export':'in balans','grid');
      svg+=node(445,255,310,125,'WONING','Huis',fmtW(houseTotal),phaseSub||'centrale energiebalans','house');
      svg+=node(835,255,310,125,'BATTERIJ','Victron batterij','Niet actief','voorbereid op ESS','battery');

      if(importW>0) svg+=path(`M365 317 H445`,importW,'grid',true,fmtW(importW),405,303);
      else if(exportW>0) svg+=path(`M445 317 H365`,exportW,'grid',true,fmtW(exportW),405,303);
      else svg+=path(`M365 317 H445`,0,'grid',false,'',0,0);
      svg+=path(`M755 317 H795 V317 H835`,0,'battery',false,'',0,0);
      svg+=path(`M600 220 V255`,pv,'pv',pv>0,pv>0?fmtW(pv):'',630,242);

      const loadBendY=455;
      const splitNote=splitUsable?'zelfde meetmoment als live balans':`wacht op synchrone meting · laatste shadow ${fmtTime(shadowTs)}`;
      const loads=[
        {x:20,title:'Tesla laden',value:tesla===null?'—':fmtW(tesla),sub:splitUsable?'flexibele belasting':splitNote,w:tesla||0,active:tesla!==null&&tesla>0,sourceX:485},
        {x:250,title:'Boiler',value:boiler===null?'—':fmtW(boiler),sub:splitUsable?String(bs.boilerState||'—'):splitNote,w:boiler||0,active:boiler!==null&&boiler>0,sourceX:540},
        {x:480,title:'Wasmachine',value:splitUsable?applianceValue(washer):'—',sub:splitUsable?applianceSub(washer):splitNote,w:splitUsable?(washer.w||0):0,active:splitUsable&&(washer.w!==null?washer.w>0:washer.active===true),statusOnly:splitUsable&&washer.w===null&&washer.active===true,sourceX:600},
        {x:710,title:'Droger',value:splitUsable?applianceValue(dryer):'—',sub:splitUsable?applianceSub(dryer):splitNote,w:splitUsable?(dryer.w||0):0,active:splitUsable&&(dryer.w!==null?dryer.w>0:dryer.active===true),statusOnly:splitUsable&&dryer.w===null&&dryer.active===true,sourceX:660},
        {x:940,title:'Overig verbruik',value:other===null?'—':fmtW(other),sub:splitUsable?'sluitpost woning':'niet berekend uit gemengde timestamps',w:other||0,active:other!==null&&other>0,sourceX:715}
      ];
      loads.forEach(a=>{
        const cx=a.x+110;
        const forceWidth=a.statusOnly?6:null;
        svg+=path(`M${a.sourceX} 380 V${loadBendY} H${cx} V525`,a.w,'grid',a.active,'',0,0,forceWidth);
        svg+=node(a.x,525,220,120,'VERBRUIK',a.title,a.value,a.sub,'load');
      });

      svg+=`<text x="600" y="704" text-anchor="middle" class="energy-rule">Live PV/net/woning komt uit de nieuwste 2-minutenmeting. Apparaatverdeling wordt alleen getoond wanneer de shadowmeting maximaal 90 s afwijkt.</text>`;
      svg+=`<g class="energy-legend" transform="translate(130 745)"><line x1="0" y1="0" x2="45" y2="0" class="legend-pv"/><text x="55" y="5">Productie</text><line x1="230" y1="0" x2="275" y2="0" class="legend-grid"/><text x="285" y="5">Net / verbruik</text><line x1="520" y1="0" x2="565" y2="0" class="legend-battery"/><text x="575" y="5">Batterij (inactief)</text></g>`;
      svg+=`</svg>`;

      const teslaPanel=`<div class="tesla-regulation"><div class="tesla-regulation-title"><strong>Tesla laadregeling — gevraagd vs. werkelijk</strong><span>Laatste Energy Manager-shadowmeting: ${fmtTime(shadowTs)}</span></div><div class="tesla-regulation-grid"><div class="tesla-step"><small>HOMEY VRAAGT</small><strong>${requestedA.toFixed(0)} A</strong><span>${requestedA>0?'actief laadverzoek':'geen laadverzoek'}</span></div><div class="tesla-arrow">→</div><div class="tesla-step equalizer"><small>EASEE EQUALIZER</small><strong>${equalizerText}</strong><span>${equalizerDetail}</span></div><div class="tesla-arrow">→</div><div class="tesla-step actual"><small>LAATSTE SHADOW TESLA</small><strong>${actualA.toFixed(1)} A</strong><span>${fmtW(teslaRaw)}</span></div></div><p class="tesla-regulation-note">Tesla- en apparaatwaarden worden niet meer gecombineerd met een nieuwere P1/PV-balans wanneer de timestamps meer dan 90 seconden verschillen. In dat geval toont de verbruiksuitsplitsing bewust ‘—’ in plaats van vermogen ten onrechte onder Overig verbruik te boeken.</p></div>`;

      const splitStatus=splitUsable?'✓ apparaatuitsplitsing synchroon':'⚠ apparaatuitsplitsing vertraagd';
      root.innerHTML=`<div class="energy-topline"><span><strong>Live balans:</strong> ${fmtTime(liveTs)} · <strong>apparaten:</strong> ${fmtTime(shadowTs)}</span><span class="${liveFresh?'energy-ok':'energy-stale'}">${liveFresh?'● actueel':'● live balans vertraagd'} · ${splitStatus}</span></div>${svg}${teslaPanel}<div class="energy-summary"><div><strong>PV</strong><br>${fmtW(pv)}</div><div><strong>Woning</strong><br>${fmtW(houseTotal)}</div><div><strong>Grid</strong><br>${p1>=0?`${fmtW(importW)} import`:`${fmtW(exportW)} export`}</div><div><strong>M7</strong><br>${String(ml.advice||'—')}</div></div><p class="energy-footnote">De actuele energiebalans gebruikt de nieuwste P1/PV-publicatie. Apparaten zoals Tesla en boiler komen uit de Energy Manager-shadowpublicatie en worden alleen in dezelfde balans uitgesplitst wanneer beide timestamps maximaal 90 seconden verschillen. Zo wordt een Tesla-start of -stop niet meer tijdelijk als Overig verbruik weergegeven.</p>`;
    }catch(e){root.innerHTML=`<p><em>Live energiestroom kon niet worden geladen: ${String(e.message||e)}</em></p>`;}
  }
  let timer=null;function start(){load();if(timer)clearInterval(timer);timer=setInterval(()=>{if(!document.hidden)load();},REFRESH_MS);}document.addEventListener('DOMContentLoaded',start);document.addEventListener('DOMContentSwitch',start);
})();
