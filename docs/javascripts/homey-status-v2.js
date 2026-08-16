(function () {
  const LIVE_STATUS_URL = "https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/homey-status.json";
  const PHASE_24H_URL = "https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/pv-phase-24h.json";
  const BASE = "/homey-energy-manual/";

  const statusLabels = { active:"Actief", shadow:"Shadow actief", off:"Uit", error:"Fout", unknown:"Onbekend" };
  const statusClass = s => ["active","shadow","off","error"].includes(s) ? `status-${s}` : "status-unknown";

  const capabilityDefs = [
    { key:"warmwater", title:"Warmwateroptimalisatie", category:"WARM WATER", match:n=>n.startsWith("Warm water optimalisatie - PV boiler + CV advies"), href:`${BASE}warm-water/`, detail:"Boilerregeling en CV-advies", prefer:n=>/v1\.2/.test(n) },
    { key:"energy", title:"Energie Manager", category:"ENERGIE MANAGER", match:n=>/^Energie Manager PV - Shadow Mode v1\./.test(n), href:`${BASE}energie-manager/`, detail:"Centrale energie-observatie en voorbereiding op Victron", prefer:n=>/v1\.6\.6/.test(n) },
    { key:"tesla", title:"Tesla-regeling", category:"TESLA", match:n=>n==="Tesla laden", href:null, detail:"Bestaande Tesla PV-laadregeling" },
    { key:"m7", title:"M7 Opportunity", category:"M7 / SHADOW", match:n=>n.startsWith("M7 - Opportunity Score - Shadow"), href:`${BASE}m7-opportunity-shadow/`, detail:"Opportunity-analyse voor flexibele energiesturing", prefer:n=>/v1\.3/.test(n) },
    { key:"forecast", title:"Prijs- en PV-forecast", category:"M7 / SHADOW", match:n=>n.startsWith("M7 - Prijs en PV forecast context - read only"), href:`${BASE}m7-prijs-pv-forecast/`, detail:"Read-only prijs- en PV-forecastcontext" },
    { key:"status", title:"Website-statuspublicatie", category:"SYSTEEM", match:n=>n.startsWith("GitHub status sync - Homey lokaal"), href:`${BASE}github-sync-flows/`, detail:"Publiceert de operationele Homey-status naar de website", prefer:n=>/v1\.2/.test(n) }
  ];

  function escapeHtml(v){return String(v??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");}
  async function fetchJson(url){const u=new URL(url,document.baseURI);u.searchParams.set("_",Date.now());const r=await fetch(u,{cache:"no-store"});if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();}
  function flowStatus(f){return f.status||(f.broken?"error":f.enabled?"active":"off");}
  function chooseFlow(flows,def){
    const matches=flows.filter(f=>def.match(String(f.name||"")));
    if(!matches.length)return null;
    const healthy=matches.filter(f=>f.enabled&&!f.broken);
    const pool=healthy.length?healthy:matches;
    if(def.prefer){const p=pool.find(f=>def.prefer(String(f.name||"")));if(p)return p;}
    return pool[0];
  }

  async function loadStatus(){
    const dashboard=document.getElementById("homey-flow-dashboard"), update=document.getElementById("homey-last-update"), health=document.getElementById("homey-sync-health");
    if(!dashboard)return;
    try{
      let data; try{data=await fetchJson(LIVE_STATUS_URL);}catch(_){data=await fetchJson(`${BASE}data/homey-status.json`);}
      const flows=data.flows||[]; dashboard.innerHTML="";
      for(const def of capabilityDefs){
        const flow=chooseFlow(flows,def); if(!flow)continue;
        const status=flowStatus(flow), card=document.createElement("article"); card.className=`flow-card ${statusClass(status)}`;
        const title=def.href?`<a class="flow-title-link" href="${escapeHtml(def.href)}" title="Open functionele beschrijving">${escapeHtml(def.title)}</a>`:escapeHtml(def.title);
        card.innerHTML=`<div class="flow-card-header"><div><div class="flow-category">${escapeHtml(def.category)}</div><div class="flow-card-title">${title}</div></div><span class="status-pill ${statusClass(status)}">● ${escapeHtml(statusLabels[status]||statusLabels.unknown)}</span></div><div class="flow-detail">${escapeHtml(def.detail)}</div><div class="flow-meta"><span>Actuele implementatie: <strong>${escapeHtml(flow.name)}</strong></span><span>Enabled: <strong>${flow.enabled?"ja":"nee"}</strong></span><span>Broken: <strong>${flow.broken?"ja":"nee"}</strong></span></div>`;
        dashboard.appendChild(card);
      }
      const dt=data.generated_at?new Date(data.generated_at):null;
      update.textContent=dt&&!Number.isNaN(dt.getTime())?`Laatst gesynchroniseerd: ${dt.toLocaleString("nl-NL")} · bron: ${data.source||"Homey"}`:"Synchronisatietijd onbekend";
      if(data.sync_ok===false){health.className="health-badge health-error";health.textContent="● synchronisatiefout";}else{health.className="health-badge health-ok";health.textContent="● synchronisatie OK";}
    }catch(error){dashboard.innerHTML=`<article class="flow-card status-error"><div class="flow-card-title">Homey-status kon niet worden geladen</div><div class="flow-detail">${escapeHtml(error.message)}</div></article>`;update.textContent="Geen actuele synchronisatie beschikbaar";health.className="health-badge health-error";health.textContent="● synchronisatiefout";}
  }

  function phaseSvg(samples){
    const W=1000,H=410,L=72,R=24,T=28,B=62,PW=W-L-R,PH=H-T-B;
    const valid=samples.map(s=>({ts:new Date(s.ts).getTime(),l1:Number(s.l1W),l2:Number(s.l2W),l3:Number(s.l3W)})).filter(s=>Number.isFinite(s.ts)&&[s.l1,s.l2,s.l3].every(Number.isFinite)).sort((a,b)=>a.ts-b.ts);
    if(!valid.length)return '<p><em>Nog geen geldige fasemeetpunten beschikbaar.</em></p>';
    const now=Date.now(),minX=now-24*3600000,maxX=now,vals=valid.flatMap(s=>[s.l1,s.l2,s.l3,0]);let minY=Math.min(...vals),maxY=Math.max(...vals);if(minY===maxY){minY-=100;maxY+=100;}const pad=Math.max(100,(maxY-minY)*.08);minY-=pad;maxY+=pad;
    const x=t=>L+(Math.max(minX,Math.min(maxX,t))-minX)/(maxX-minX)*PW,y=v=>T+(maxY-v)/(maxY-minY)*PH,fmtW=v=>`${Math.round(v).toLocaleString('nl-NL')} W`,colors={l1:'#1976d2',l2:'#ef6c00',l3:'#2e7d32'},poly=key=>valid.map(s=>`${x(s.ts).toFixed(1)},${y(s[key]).toFixed(1)}`).join(' ');let grid='';for(let i=0;i<=4;i++){const v=maxY-(maxY-minY)*i/4,yy=y(v);grid+=`<line x1="${L}" y1="${yy}" x2="${W-R}" y2="${yy}" class="phase-grid"/><text x="${L-10}" y="${yy+4}" text-anchor="end" class="phase-axis-label">${escapeHtml(fmtW(v))}</text>`;}let xt='';for(let i=0;i<=4;i++){const t=minX+(maxX-minX)*i/4,xx=x(t),d=new Date(t);xt+=`<line x1="${xx}" y1="${T}" x2="${xx}" y2="${H-B}" class="phase-grid phase-grid-x"/><text x="${xx}" y="${H-B+24}" text-anchor="middle" class="phase-axis-label">${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}</text>`;}const zero=(minY<=0&&maxY>=0)?`<line x1="${L}" y1="${y(0)}" x2="${W-R}" y2="${y(0)}" class="phase-zero"/>`:'',last=valid[valid.length-1];return `<div class="phase-chart-wrap"><svg class="phase-chart" viewBox="0 0 ${W} ${H}">${grid}${xt}${zero}<polyline points="${poly('l1')}" fill="none" stroke="${colors.l1}" class="phase-line"/><polyline points="${poly('l2')}" fill="none" stroke="${colors.l2}" class="phase-line"/><polyline points="${poly('l3')}" fill="none" stroke="${colors.l3}" class="phase-line"/></svg></div><div class="phase-legend"><span><i style="background:${colors.l1}"></i>L1 <strong>${escapeHtml(fmtW(last.l1))}</strong></span><span><i style="background:${colors.l2}"></i>L2 <strong>${escapeHtml(fmtW(last.l2))}</strong></span><span><i style="background:${colors.l3}"></i>L3 <strong>${escapeHtml(fmtW(last.l3))}</strong></span></div>`;
  }
  function phaseAnalysisHtml(data){const entries=Object.entries(data.analysis||{});if(!entries.length)return '';return `<div class="phase-analysis-grid">${entries.map(([name,a])=>`<article class="phase-analysis-card"><strong>${escapeHtml(name)}</strong><div>Beste fase: <strong>${escapeHtml(a.best_phase||'–')}</strong></div><div>Confidence: <strong>${escapeHtml(a.confidence||'–')}</strong></div><div>Score: ${Number.isFinite(Number(a.best_score))?Number(a.best_score).toFixed(2):'–'}</div></article>`).join('')}</div>`;}
  async function loadPhase24h(){const root=document.getElementById('pv-phase-24h');if(!root)return;try{let data;try{data=await fetchJson(PHASE_24H_URL);}catch(_){data=await fetchJson(`${BASE}data/pv-phase-24h.json`);}const generated=data.generated_at?new Date(data.generated_at):null;root.innerHTML=`<div class="phase-chart-meta"><strong>L1/L2/L3 netto vermogen</strong><span>${data.sample_count??0} meetpunten · ${generated&&!Number.isNaN(generated.getTime())?`bijgewerkt ${generated.toLocaleString('nl-NL')}`:'nog niet bijgewerkt'}</span></div>${data.error?`<p class="phase-warning">${escapeHtml(data.error)}</p>`:''}${phaseSvg(Array.isArray(data.samples)?data.samples:[])}${phaseAnalysisHtml(data)}<p class="muted">Positief = netafname op de fase. Negatief = teruglevering. De grafiek toont een schuivend venster van maximaal 24 uur.</p>`;}catch(error){root.innerHTML=`<p><strong>24-uurs fasegegevens konden niet worden geladen:</strong> ${escapeHtml(error.message)}</p>`;}}
  function loadAll(){loadStatus();loadPhase24h();}document.addEventListener("DOMContentLoaded",loadAll);document.addEventListener("DOMContentSwitch",loadAll);
})();
