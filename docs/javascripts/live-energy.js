(function(){
  const BASE='/homey-energy-manual/';
  const fmtW=v=>`${Math.round(Number(v)||0).toLocaleString('nl-NL')} W`;
  const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
  async function get(path){const r=await fetch(`${BASE}data/${path}?ts=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`${path}: HTTP ${r.status}`);return r.json();}
  function path(id,x1,y1,x2,y2,w,active=true){const width=active?clamp(2+Math.abs(w)/700,2.5,11):2;return `<line id="${id}" class="energy-path ${active?'is-active':'is-idle'}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" style="stroke-width:${width}" marker-end="url(#arrow)"/>`;}
  function node(x,y,w,h,title,value,sub=''){return `<g class="energy-node"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="12"/><text x="${x+w/2}" y="${y+27}" text-anchor="middle" class="energy-title">${title}</text><text x="${x+w/2}" y="${y+52}" text-anchor="middle" class="energy-value">${value}</text>${sub?`<text x="${x+w/2}" y="${y+72}" text-anchor="middle" class="energy-sub">${sub}</text>`:''}</g>`;}
  async function load(){
    const root=document.getElementById('live-energy-flow'); if(!root)return;
    try{
      const [phase,base,m7]=await Promise.all([get('pv-phase-24h.json'),get('shadow-baseline-v01.json'),get('m7-opportunity.json').catch(()=>null)]);
      const ps=(phase.samples||[]).at(-1)||{}, bs=base.latest||{}, ml=m7?.latest||{};
      const pv=Math.max(0,(Number(ps.solarEdgeW)||0)+(Number(ps.goodWe4200W)||0)+(Number(ps.goodWe2000W)||0));
      const p1=Number.isFinite(Number(ps.p1W))?Number(ps.p1W):Number(bs.p1W)||0;
      const tesla=Math.max(0,Number(bs.teslaW)||0), boiler=Math.max(0,Number(bs.boilerW)||0);
      const houseTotal=Math.max(0,pv+p1); const normal=Math.max(0,houseTotal-tesla-boiler);
      let rem=pv; const pvNormal=Math.min(normal,rem); rem-=pvNormal; const pvTesla=Math.min(tesla,rem); rem-=pvTesla; const pvBoiler=Math.min(boiler,rem); rem-=pvBoiler; const exportW=Math.max(0,-p1); const importW=Math.max(0,p1);
      const gridNormal=Math.max(0,normal-pvNormal), gridTesla=Math.max(0,tesla-pvTesla), gridBoiler=Math.max(0,boiler-pvBoiler);
      const freshness=[phase.generated_at,base.generated_at].filter(Boolean).map(x=>new Date(x).getTime()); const newest=freshness.length?Math.max(...freshness):null;
      const stale=newest?Date.now()-newest>30*60*1000:true;
      const W=980,H=560;
      let svg=`<svg class="energy-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Live energiestroom woning"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" class="energy-arrow"/></marker></defs>`;
      svg+=node(40,30,180,88,'PV-productie',fmtW(pv),`SE ${fmtW(ps.solarEdgeW)} · GW42 ${fmtW(ps.goodWe4200W)} · GW20 ${fmtW(ps.goodWe2000W)}`);
      svg+=node(760,30,180,88,'Net / P1',fmtW(Math.abs(p1)),p1>0?'afname':p1<0?'teruglevering':'in balans');
      svg+=node(400,165,180,92,'Energy Manager','SHADOW',String(bs.status||'—'));
      svg+=node(70,390,180,88,'Huishouden',fmtW(normal),'niet-flexibel / overig');
      svg+=node(400,390,180,88,'Tesla',fmtW(tesla),tesla>0?'actief vermogen':'niet actief');
      svg+=node(730,390,180,88,'Boiler',fmtW(boiler),String(bs.boilerState||'—'));
      if(pv>0){svg+=path('pv-em',220,74,400,205,pv,true);svg+=path('pv-house',150,118,150,390,pvNormal,pvNormal>0);svg+=path('pv-tesla',190,118,470,390,pvTesla,pvTesla>0);svg+=path('pv-boiler',210,108,790,390,pvBoiler,pvBoiler>0);if(exportW>0)svg+=path('pv-grid',220,58,760,58,exportW,true);}
      if(importW>0){svg+=path('grid-em',760,88,580,205,importW,true);if(gridNormal>0)svg+=path('grid-house',790,118,210,390,gridNormal,true);if(gridTesla>0)svg+=path('grid-tesla',820,118,520,390,gridTesla,true);if(gridBoiler>0)svg+=path('grid-boiler',850,118,850,390,gridBoiler,true);}
      svg+='</svg>';
      root.innerHTML=`<div class="energy-topline"><span><strong>Laatste data:</strong> ${newest?new Date(newest).toLocaleString('nl-NL'):'onbekend'}</span><span class="${stale?'energy-stale':'energy-ok'}">${stale?'● data ouder dan 30 min':'● actueel'}</span></div>${svg}<div class="energy-summary"><div><strong>PV</strong><br>${fmtW(pv)}</div><div><strong>Huishouden totaal</strong><br>${fmtW(houseTotal)}</div><div><strong>Net</strong><br>${p1>=0?`${fmtW(importW)} import`:`${fmtW(exportW)} export`}</div><div><strong>M7</strong><br>${String(ml.advice||'—')}</div></div><p class="energy-footnote">Toewijzing PV is boekhoudkundig volgens: huishouden → Tesla → boiler → net. Gemeten bronnen blijven P1/PV/apparaatvermogen.</p>`;
    }catch(e){root.innerHTML=`<p><em>Live energiestroom kon niet worden geladen: ${String(e.message||e)}</em></p>`;}
  }
  document.addEventListener('DOMContentLoaded',load);document.addEventListener('DOMContentSwitch',load);
})();
