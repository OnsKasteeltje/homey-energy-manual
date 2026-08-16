(function () {
  const LIVE_STATUS_URL = "https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/homey-status.json";
  const PHASE_24H_URL = "https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/pv-phase-24h.json";
  const BASE = "/homey-energy-manual/";

  const statusLabels = { active:"Actief", shadow:"Shadow/Test", off:"Uit", error:"Fout", unknown:"Onbekend" };
  const statusClass = s => ["active","shadow","off","error"].includes(s) ? `status-${s}` : "status-unknown";

  function flowHref(name){
    if(name.startsWith("Warm water optimalisatie - PV boiler + CV advies")) return `${BASE}warm-water/`;
    if(/^Energie Manager PV - Shadow Mode v1\./.test(name) || name === "Energie Manager PV - Shadow Mode" || name === "Energie Manager PV - Shadow Mode v0.2 Quooker") return `${BASE}energie-manager/`;
    if(name.startsWith("M7 - Prijs en PV forecast context - read only")) return `${BASE}m7-prijs-pv-forecast/`;
    if(name.startsWith("M7 - Opportunity Score - Shadow")) return `${BASE}m7-opportunity-shadow/`;
    if(name.startsWith("Energie Manager - omschakeling")) return `${BASE}energie-manager/`;
    if(name.startsWith("GitHub status sync - Homey lokaal") || name.startsWith("GitHub shadow sync - Homey lokaal")) return `${BASE}github-sync-flows/`;
    return null;
  }

  function escapeHtml(v){return String(v??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");}
  async function fetchJson(url){const u=new URL(url,document.baseURI);u.searchParams.set("_",Date.now());const r=await fetch(u,{cache:"no-store"});if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();}

  async function loadStatus(){
    const dashboard=document.getElementById("homey-flow-dashboard"), update=document.getElementById("homey-last-update"), health=document.getElementById("homey-sync-health");
    if(!dashboard)return;
    try{
      let data; try{data=await fetchJson(LIVE_STATUS_URL);}catch(_){data=await fetchJson(`${BASE}data/homey-status.json`);}
      dashboard.innerHTML="";
      for(const flow of (data.flows||[])){
        const status=flow.status||(flow.broken?"error":flow.enabled?"active":"off");
        const href=flowHref(flow.name);
        const card=document.createElement("article");
        card.className=`flow-card ${statusClass(status)}`;
        const title=href?`<a class="flow-title-link" href="${escapeHtml(href)}" title="Open flowbeschrijving">${escapeHtml(flow.name)}</a>`:escapeHtml(flow.name);
        card.innerHTML=`<div class="flow-card-header"><div><div class="flow-category">${escapeHtml(flow.category||"Flow")}</div><div class="flow-card-title">${title}</div></div><span class="status-pill ${statusClass(status)}">● ${escapeHtml(statusLabels[status]||statusLabels.unknown)}</span></div><div class="flow-detail">${escapeHtml(flow.detail||"")}</div><div class="flow-meta"><span>Enabled: <strong>${flow.enabled?"ja":"nee"}</strong></span><span>Broken: <strong>${flow.broken?"ja":"nee"}</strong></span></div>`;
        dashboard.appendChild(card);
      }
      const dt=data.generated_at?new Date(data.generated_at):null;
      update.textContent=dt&&!Number.isNaN(dt.getTime())?`Laatst gesynchroniseerd: ${dt.toLocaleString("nl-NL")} · bron: ${data.source||"Homey"}`:"Synchronisatietijd onbekend";
      if(data.sync_ok===false){health.className="health-badge health-error";health.textContent="● synchronisatiefout";}else{health.className="health-badge health-ok";health.textContent="● synchronisatie OK";}
    }catch(error){dashboard.innerHTML=`<article class="flow-card status-error"><div class="flow-card-title">Homey-status kon niet worden geladen</div><div class="flow-detail">${escapeHtml(error.message)}</div></article>`;update.textContent="Geen actuele synchronisatie beschikbaar";health.className="health-badge health-error";health.textContent="● synchronisatiefout";}
  }

  function phaseSvg(samples){
    const W=1000,H=410,L=72,R=24,T=28,B=62, PW=W-L-R,PH=H-T-B;
    const valid=samples.map(s=>({ts:new Date(s.ts).getTime(),l1:Number(s.l1W),l2:Number(s.l2W),l3:Number(s.l3W)})).filter(s=>Number.isFinite(s.ts)&&[s.l1,s.l2,s.l3].every(Number.isFinite)).sort((a,b)=>a.ts-b.ts);
    if(!valid.length)return '<p><em>Nog geen geldige fasemeetpunten beschikbaar.</em></p>';
    const now=Date.now(), minX=now-24*3600000, maxX=now;
    const vals=valid.flatMap(s=>[s.l1,s.l2,s.l3,0]);
    let minY=Math.min(...vals),maxY=Math.max(...vals); if(minY===maxY){minY-=100;maxY+=100;}
    const pad=Math.max(100,(maxY-minY)*.08); minY-=pad;maxY+=pad;
    const x=t=>L+(Math.max(minX,Math.min(maxX,t))-minX)/(maxX-minX)*PW;
    const y=v=>T+(maxY-v)/(maxY-minY)*PH;
    const fmtW=v=>`${Math.round(v).toLocaleString('nl-NL')} W`;
    const colors={l1:'#1976d2',l2:'#ef6c00',l3:'#2e7d32'};
    const poly=(key)=>valid.map(s=>`${x(s.ts).toFixed(1)},${y(s[key]).toFixed(1)}`).join(' ');
    let grid='';
    for(let i=0;i<=4;i++){const v=maxY-(maxY-minY)*i/4, yy=y(v);grid+=`<line x1="${L}" y1="${yy}" x2="${W-R}" y2="${yy}" class="phase-grid"/><text x="${L-10}" y="${yy+4}" text-anchor="end" class="phase-axis-label">${escapeHtml(fmtW(v))}</text>`;}
    let xt=''; for(let i=0;i<=4;i++){const t=minX+(maxX-minX)*i/4,xx=x(t),d=new Date(t);xt+=`<line x1="${xx}" y1="${T}" x2="${xx}" y2="${H-B}" class="phase-grid phase-grid-x"/><text x="${xx}" y="${H-B+24}" text-anchor="middle" class="phase-axis-label">${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}</text>`;}
    const zero=(minY<=0&&maxY>=0)?`<line x1="${L}" y1="${y(0)}" x2="${W-R}" y2="${y(0)}" class="phase-zero"/><text x="${W-R}" y="${y(0)-6}" text-anchor="end" class="phase-zero-label">0 W</text>`:'';
    const pointIfSingle=valid.length===1?['l1','l2','l3'].map(k=>`<circle cx="${x(valid[0].ts)}" cy="${y(valid[0][k])}" r="5" fill="${colors[k]}"/>`).join(''):'';
    const last=valid[valid.length-1];
    return `<div class="phase-chart-wrap"><svg class="phase-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Netto vermogen L1, L2 en L3 over de laatste 24 uur">${grid}${xt}${zero}<polyline points="${poly('l1')}" fill="none" stroke="${colors.l1}" class="phase-line"/><polyline points="${poly('l2')}" fill="none" stroke="${colors.l2}" class="phase-line"/><polyline points="${poly('l3')}" fill="none" stroke="${colors.l3}" class="phase-line"/>${pointIfSingle}</svg></div><div class="phase-legend"><span><i style="background:${colors.l1}"></i>L1 <strong>${escapeHtml(fmtW(last.l1))}</strong></span><span><i style="background:${colors.l2}"></i>L2 <strong>${escapeHtml(fmtW(last.l2))}</strong></span><span><i style="background:${colors.l3}"></i>L3 <strong>${escapeHtml(fmtW(last.l3))}</strong></span></div>`;
  }

  function phaseAnalysisHtml(data){
    const entries=Object.entries(data.analysis||{});
    if(!entries.length)return '';
    return `<div class="phase-analysis-grid">${entries.map(([name,a])=>`<article class="phase-analysis-card"><strong>${escapeHtml(name)}</strong><div>Beste fase: <strong>${escapeHtml(a.best_phase||'–')}</strong></div><div>Confidence: <strong>${escapeHtml(a.confidence||'–')}</strong></div><div>Score: ${Number.isFinite(Number(a.best_score))?Number(a.best_score).toFixed(2):'–'}</div></article>`).join('')}</div>`;
  }

  async function loadPhase24h(){
    const root=document.getElementById('pv-phase-24h'); if(!root)return;
    try{
      let data; try{data=await fetchJson(PHASE_24H_URL);}catch(_){data=await fetchJson(`${BASE}data/pv-phase-24h.json`);}
      const generated=data.generated_at?new Date(data.generated_at):null;
      root.innerHTML=`<div class="phase-chart-meta"><strong>L1/L2/L3 netto vermogen</strong><span>${data.sample_count??0} meetpunten · ${generated&&!Number.isNaN(generated.getTime())?`bijgewerkt ${generated.toLocaleString('nl-NL')}`:'nog niet bijgewerkt'}</span></div>${data.error?`<p class="phase-warning">${escapeHtml(data.error)}</p>`:''}${phaseSvg(Array.isArray(data.samples)?data.samples:[])}${phaseAnalysisHtml(data)}<p class="muted">Positief = netafname op de fase. Negatief = teruglevering. De grafiek toont een schuivend venster van maximaal 24 uur.</p>`;
    }catch(error){root.innerHTML=`<p><strong>24-uurs fasegegevens konden niet worden geladen:</strong> ${escapeHtml(error.message)}</p>`;}
  }

  function loadAll(){loadStatus();loadPhase24h();}
  document.addEventListener("DOMContentLoaded",loadAll);
  document.addEventListener("DOMContentSwitch",loadAll);
})();
