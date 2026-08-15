(function(){
  const BASE='/homey-energy-manual/';
  const fmtW=v=>`${Math.round(Number(v)||0).toLocaleString('nl-NL')} W`;
  const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
  async function get(path){const r=await fetch(`${BASE}data/${path}?ts=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`${path}: HTTP ${r.status}`);return r.json();}
  function edge(x1,y1,x2,y2,w,active=true,reverse=false,label=''){
    const width=active?clamp(2+Math.abs(w)/700,2.5,11):2;
    const marker=reverse?'url(#arrowBack)':'url(#arrow)';
    const lx=(x1+x2)/2, ly=(y1+y2)/2-7;
    return `<g><line class="energy-path ${active?'is-active':'is-idle'}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" style="stroke-width:${width}" marker-end="${marker}"/>${label?`<text x="${lx}" y="${ly}" text-anchor="middle" class="energy-edge-label">${label}</text>`:''}</g>`;
  }
  function node(x,y,w,h,title,value,sub='',cls=''){
    return `<g class="energy-node ${cls}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="12"/><text x="${x+w/2}" y="${y+27}" text-anchor="middle" class="energy-title">${title}</text><text x="${x+w/2}" y="${y+52}" text-anchor="middle" class="energy-value">${value}</text>${sub?`<text x="${x+w/2}" y="${y+73}" text-anchor="middle" class="energy-sub">${sub}</text>`:''}</g>`;
  }
  async function load(){
    const root=document.getElementById('live-energy-flow'); if(!root)return;
    try{
      const [phase,base,m7]=await Promise.all([get('pv-phase-24h.json'),get('shadow-baseline-v01.json'),get('m7-opportunity.json').catch(()=>null)]);
      const ps=(phase.samples||[]).at(-1)||{}, bs=base.latest||{}, ml=m7?.latest||{};
      const pv=Math.max(0,(Number(ps.solarEdgeW)||0)+(Number(ps.goodWe4200W)||0)+(Number(ps.goodWe2000W)||0));
      const p1=Number.isFinite(Number(ps.p1W))?Number(ps.p1W):Number(bs.p1W)||0;
      const tesla=Math.max(0,Number(bs.teslaW)||0), boiler=Math.max(0,Number(bs.boilerW)||0);
      const houseTotal=Math.max(0,pv+p1), normal=Math.max(0,houseTotal-tesla-boiler);
      let rem=pv; const pvNormal=Math.min(normal,rem); rem-=pvNormal; const pvTesla=Math.min(tesla,rem); rem-=pvTesla; const pvBoiler=Math.min(boiler,rem); rem-=pvBoiler;
      const exportW=Math.max(0,-p1), importW=Math.max(0,p1);
      const gridNormal=Math.max(0,normal-pvNormal), gridTesla=Math.max(0,tesla-pvTesla), gridBoiler=Math.max(0,boiler-pvBoiler);
      const freshness=[phase.generated_at,base.generated_at].filter(Boolean).map(x=>new Date(x).getTime()), newest=freshness.length?Math.max(...freshness):null;
      const stale=newest?Date.now()-newest>30*60*1000:true;
      const W=1000,H=720;
      let svg=`<svg class="energy-svg architecture-like" viewBox="0 0 ${W} ${H}" role="img" aria-label="Live energiestroom woning"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" class="energy-arrow"/></marker><marker id="arrowBack" markerWidth="8" markerHeight="8" refX="1" refY="3" orient="auto"><path d="M7,0 L7,6 L0,3 z" class="energy-arrow"/></marker></defs>`;
      svg+=node(390,25,220,90,'PV-bronnen',fmtW(pv),`SE ${fmtW(ps.solarEdgeW)} · GW42 ${fmtW(ps.goodWe4200W)} · GW20 ${fmtW(ps.goodWe2000W)}`,'source');
      svg+=node(390,155,220,90,'P1 / GRID',fmtW(Math.abs(p1)),p1>0?'import uit net':p1<0?'export naar net':'netto 0 W','grid');
      svg+=node(365,300,270,100,'ENERGY MANAGER','SHADOW',String(bs.status||'—'),'manager');
      svg+=node(40,515,190,90,'Huishouden',fmtW(normal),'prioriteit #1','load');
      svg+=node(290,515,190,90,'Tesla',fmtW(tesla),'prioriteit #2','load');
      svg+=node(540,515,190,90,'Boiler',fmtW(boiler),String(bs.boilerState||'—'),'load');
      svg+=node(790,515,170,90,'Net',fmtW(exportW),exportW>0?'teruglevering':'geen export','sink');
      svg+=edge(500,115,500,155,pv,pv>0,false,fmtW(pv));
      if(p1>=0) svg+=edge(500,245,500,300,importW,importW>0,false,importW>0?fmtW(importW):'');
      else svg+=edge(500,300,500,245,exportW,exportW>0,false,exportW>0?fmtW(exportW):'');
      svg+=edge(500,400,135,515,normal,normal>0,false,fmtW(normal));
      svg+=edge(500,400,385,515,tesla,tesla>0,false,tesla>0?fmtW(tesla):'');
      svg+=edge(500,400,635,515,boiler,boiler>0,false,boiler>0?fmtW(boiler):'');
      svg+=edge(500,400,875,515,exportW,exportW>0,false,exportW>0?fmtW(exportW):'');
      svg+=`<text x="500" y="650" text-anchor="middle" class="energy-rule">Boekhoudkundige toewijzing: huishouden → Tesla → boiler → net</text>`;
      svg+='</svg>';
      root.innerHTML=`<div class="energy-topline"><span><strong>Laatste data:</strong> ${newest?new Date(newest).toLocaleString('nl-NL'):'onbekend'}</span><span class="${stale?'energy-stale':'energy-ok'}">${stale?'● data ouder dan 30 min':'● actueel'}</span></div>${svg}<div class="energy-summary"><div><strong>PV</strong><br>${fmtW(pv)}</div><div><strong>Huishouden totaal</strong><br>${fmtW(houseTotal)}</div><div><strong>Grid</strong><br>${p1>=0?`${fmtW(importW)} import`:`${fmtW(exportW)} export`}</div><div><strong>M7</strong><br>${String(ml.advice||'—')}</div></div><p class="energy-footnote">De fysieke energiestroom wordt niet per elektron gemeten. De verdeling over huishouden, Tesla, boiler en net is daarom een boekhoudkundige toewijzing op basis van gemeten P1/PV/apparaatvermogens en de ingestelde prioriteitslogica.</p>`;
    }catch(e){root.innerHTML=`<p><em>Live energiestroom kon niet worden geladen: ${String(e.message||e)}</em></p>`;}
  }
  document.addEventListener('DOMContentLoaded',load);document.addEventListener('DOMContentSwitch',load);
})();
