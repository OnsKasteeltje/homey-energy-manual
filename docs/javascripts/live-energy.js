(function(){
  const BASE='/homey-energy-manual/';
  const REFRESH_MS=5*60*1000;
  const fmtW=v=>`${Math.round(Number(v)||0).toLocaleString('nl-NL')} W`;
  const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
  async function get(path){const r=await fetch(`${BASE}data/${path}?ts=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`${path}: HTTP ${r.status}`);return r.json();}
  function flow(x1,y1,x2,y2,w,active=true,label=''){const width=active?clamp(2+Math.abs(w)/700,2.5,11):2,lx=(x1+x2)/2,ly=(y1+y2)/2-7;return `<g><line class="energy-path ${active?'is-active':'is-idle'}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" style="stroke-width:${width}" marker-end="url(#arrow)"/>${label?`<text x="${lx}" y="${ly}" text-anchor="middle" class="energy-edge-label">${label}</text>`:''}</g>`;}
  function control(x1,y1,x2,y2,label=''){const lx=(x1+x2)/2,ly=(y1+y2)/2-5;return `<g><line class="energy-control-path" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" marker-end="url(#controlArrow)"/>${label?`<text x="${lx}" y="${ly}" text-anchor="middle" class="energy-control-label">${label}</text>`:''}</g>`;}
  function node(x,y,w,h,title,value,sub='',cls=''){return `<g class="energy-node ${cls}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="12"/><text x="${x+w/2}" y="${y+27}" text-anchor="middle" class="energy-title">${title}</text><text x="${x+w/2}" y="${y+52}" text-anchor="middle" class="energy-value">${value}</text>${sub?`<text x="${x+w/2}" y="${y+73}" text-anchor="middle" class="energy-sub">${sub}</text>`:''}</g>`;}
  const numOrNull=v=>Number.isFinite(Number(v))?Number(v):null;
  async function load(){
    const root=document.getElementById('live-energy-flow');if(!root)return;
    try{
      const [phase,base,m7]=await Promise.all([get('pv-phase-24h.json'),get('shadow-baseline-v01.json'),get('m7-opportunity.json').catch(()=>null)]);
      const ps=(phase.samples||[]).at(-1)||{},bs=base.latest||{},ml=m7?.latest||{};
      const pv=Math.max(0,(Number(ps.solarEdgeW)||0)+(Number(ps.goodWe4200W)||0)+(Number(ps.goodWe2000W)||0));
      const p1=Number.isFinite(Number(ps.p1W))?Number(ps.p1W):Number(bs.p1W)||0;
      const tesla=Math.max(0,Number(bs.teslaW)||0),boiler=Math.max(0,Number(bs.boilerW)||0);
      const houseTotal=Math.max(0,pv+p1),normal=Math.max(0,houseTotal-tesla-boiler),exportW=Math.max(0,-p1),importW=Math.max(0,p1);
      // Alleen gebruiken als een toekomstige publisher deze waarden werkelijk levert.
      const washerW=numOrNull(bs.washerW),dryerW=numOrNull(bs.dryerW),dishwasherW=numOrNull(bs.dishwasherW);
      const measuredHeavy=[washerW,dryerW,dishwasherW].filter(v=>v!==null).reduce((a,b)=>a+Math.max(0,b),0);
      const otherHouse=Math.max(0,normal-measuredHeavy);
      const deviceValue=v=>v===null?'—':fmtW(Math.max(0,v));
      const deviceSub=v=>v===null?'niet afzonderlijk gemeten':'live gemeten';
      const freshness=[phase.generated_at,base.generated_at].filter(Boolean).map(x=>new Date(x).getTime()),newest=freshness.length?Math.max(...freshness):null,stale=newest?Date.now()-newest>30*60*1000:true;
      const W=1050,H=930;
      let svg=`<svg class="energy-svg architecture-like" viewBox="0 0 ${W} ${H}" role="img" aria-label="Live energiestroom en Homey-orchestratie"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" class="energy-arrow"/></marker><marker id="controlArrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" class="energy-control-arrow"/></marker></defs>`;
      svg+=`<text x="525" y="24" text-anchor="middle" class="energy-layer-title">BESTURING / ORCHESTRATIE</text>`+node(405,40,240,92,'ENERGY MANAGER','SHADOW',String(bs.status||'Homey orchestratie'),'manager');
      svg+=`<line x1="30" y1="165" x2="1020" y2="165" class="energy-layer-separator"/><text x="525" y="192" text-anchor="middle" class="energy-layer-title">FYSIEKE / BOEKHOUDKUNDIGE ENERGIESTROOM</text>`;
      svg+=node(55,245,190,90,'PV-bronnen',fmtW(pv),'SE · GW4200 · GW2000','source')+node(430,245,190,90,'HUISBUS',fmtW(houseTotal),'centrale elektrische balans','bus')+node(805,245,190,90,'GRID / P1',fmtW(Math.abs(p1)),p1>0?'import':p1<0?'export':'in balans','grid');
      svg+=node(55,500,190,90,'Huishouden',fmtW(normal),'prioriteit #1','load')+node(305,500,190,90,'Tesla',fmtW(tesla),'prioriteit #2','load')+node(555,500,190,90,'Boiler',fmtW(boiler),String(bs.boilerState||'—'),'load')+node(805,500,190,90,'Netto net',p1>=0?fmtW(importW):fmtW(exportW),p1>=0?'afname':'teruglevering','sink');
      if(pv>0)svg+=flow(245,290,430,290,pv,true,fmtW(pv));if(importW>0)svg+=flow(805,300,620,300,importW,true,fmtW(importW));if(exportW>0)svg+=flow(620,280,805,280,exportW,true,fmtW(exportW));
      svg+=flow(500,335,150,500,normal,normal>0,normal>0?fmtW(normal):'')+flow(515,335,400,500,tesla,tesla>0,tesla>0?fmtW(tesla):'')+flow(535,335,650,500,boiler,boiler>0,boiler>0?fmtW(boiler):'');if(exportW>0)svg+=flow(555,335,900,500,exportW,true,fmtW(exportW));
      svg+=control(465,132,400,500,'sturing')+control(525,132,650,500,'sturing');

      // Uitsplitsing huishouden: geen extra Homey-calls; alleen reeds gepubliceerde velden gebruiken.
      svg+=`<text x="150" y="630" text-anchor="middle" class="energy-layer-title">GROOTVERBRUIKERS BINNEN HUISHOUDEN</text>`;
      svg+=node(20,660,190,90,'Wasmachine',deviceValue(washerW),deviceSub(washerW),'house-subload');
      svg+=node(230,660,190,90,'Droger',deviceValue(dryerW),deviceSub(dryerW),'house-subload');
      svg+=node(440,660,190,90,'Vaatwasser',deviceValue(dishwasherW),deviceSub(dishwasherW),'house-subload');
      svg+=node(650,660,190,90,'Overig huishouden',fmtW(otherHouse),measuredHeavy>0?'rest na gemeten grootverbruikers':'sluitpost huishouden','house-subload');
      svg+=flow(150,590,115,660,washerW||0,washerW!==null&&washerW>0,washerW?fmtW(washerW):'');
      svg+=flow(150,590,325,660,dryerW||0,dryerW!==null&&dryerW>0,dryerW?fmtW(dryerW):'');
      svg+=flow(150,590,535,660,dishwasherW||0,dishwasherW!==null&&dishwasherW>0,dishwasherW?fmtW(dishwasherW):'');
      svg+=flow(150,590,745,660,otherHouse,otherHouse>0,otherHouse>0?fmtW(otherHouse):'');

      svg+=`<text x="525" y="840" text-anchor="middle" class="energy-rule">Toewijzingslogica: huishouden → Tesla → boiler → net</text><text x="525" y="868" text-anchor="middle" class="energy-rule">Energy Manager ligt buiten het elektrische stroompad en stuurt alleen flexibele verbruikers.</text></svg>`;
      root.innerHTML=`<div class="energy-topline"><span><strong>Laatste data:</strong> ${newest?new Date(newest).toLocaleString('nl-NL'):'onbekend'}</span><span class="${stale?'energy-stale':'energy-ok'}">${stale?'● data ouder dan 30 min':'● actueel'}</span></div>${svg}<div class="energy-summary"><div><strong>PV</strong><br>${fmtW(pv)}</div><div><strong>Huishouden totaal</strong><br>${fmtW(houseTotal)}</div><div><strong>Grid</strong><br>${p1>=0?`${fmtW(importW)} import`:`${fmtW(exportW)} export`}</div><div><strong>M7</strong><br>${String(ml.advice||'—')}</div></div><p class="energy-footnote">Dashboard controleert elke 5 minuten op nieuw gepubliceerde data. Doorgetrokken dikke lijnen tonen energie; dunne gestippelde lijnen tonen orchestratie. Wasmachine, droger en vaatwasser krijgen alleen een eigen wattage zodra dat al in de bestaande publicatiedata beschikbaar is; er wordt hiervoor geen extra Homey-polling gestart.</p>`;
    }catch(e){root.innerHTML=`<p><em>Live energiestroom kon niet worden geladen: ${String(e.message||e)}</em></p>`;}
  }
  let timer=null;
  function start(){load();if(timer)clearInterval(timer);timer=setInterval(()=>{if(!document.hidden)load();},REFRESH_MS);}
  document.addEventListener('DOMContentLoaded',start);document.addEventListener('DOMContentSwitch',start);
})();
