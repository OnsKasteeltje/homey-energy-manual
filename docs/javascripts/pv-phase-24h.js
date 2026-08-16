(function () {
  const BASE = '/homey-energy-manual/';
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = (v, d=3) => Number.isFinite(Number(v)) ? Number(v).toFixed(d) : '—';
  const fmtDate = (v) => {
    if (!v) return 'Nog geen publicatie';
    const d = new Date(v);
    return Number.isNaN(d.getTime()) ? esc(v) : d.toLocaleString('nl-NL');
  };

  function drawChart(samples) {
    if (!samples.length) return '<p><em>Nog geen fasepunten beschikbaar.</em></p>';
    const W=900,H=340,L=62,R=20,T=22,B=48,pw=W-L-R,ph=H-T-B;
    const vals=samples.flatMap(s=>[Number(s.l1W),Number(s.l2W),Number(s.l3W)]).filter(Number.isFinite);
    if(!vals.length) return '<p><em>Geen geldige L1/L2/L3-waarden beschikbaar.</em></p>';
    let ymin=Math.min(0,...vals), ymax=Math.max(0,...vals);
    if(ymin===ymax){ymin-=100;ymax+=100;}
    const pad=Math.max(100,(ymax-ymin)*0.08); ymin-=pad; ymax+=pad;
    const t0=new Date(samples[0].ts).getTime(), t1=new Date(samples.at(-1).ts).getTime();
    const span=Math.max(1,t1-t0);
    const x=s=>L+(new Date(s.ts).getTime()-t0)/span*pw;
    const y=v=>T+(ymax-v)/(ymax-ymin)*ph;
    const line=(key,cls)=>`<polyline class="phase-series ${cls}" points="${samples.map(s=>`${x(s).toFixed(1)},${y(Number(s[key])||0).toFixed(1)}`).join(' ')}"/>`;
    const grid=[];
    for(let i=0;i<=4;i++){const val=ymax-(ymax-ymin)*i/4, yy=y(val);grid.push(`<line class="phase-grid" x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}"/><text class="phase-axis-label" x="${L-8}" y="${yy+4}" text-anchor="end">${Math.round(val)} W</text>`)}
    const ticks=[];
    for(let i=0;i<=4;i++){const tt=t0+span*i/4, xx=L+pw*i/4;ticks.push(`<text class="phase-axis-label" x="${xx}" y="${H-18}" text-anchor="middle">${new Date(tt).toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'})}</text>`)}
    const zero=y(0);
    return `<div class="phase-chart-wrap"><svg class="phase-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="L1 L2 L3 vermogen laatste 24 uur">${grid.join('')}<line class="phase-zero" x1="${L}" x2="${W-R}" y1="${zero}" y2="${zero}"/>${line('l1W','phase-l1')}${line('l2W','phase-l2')}${line('l3W','phase-l3')}${ticks.join('')}</svg></div><div class="phase-legend"><span class="phase-l1-key">● L1</span><span class="phase-l2-key">● L2</span><span class="phase-l3-key">● L3</span><span>boven 0 = afname · onder 0 = teruglevering</span></div>`;
  }

  async function loadPhase(){
    const root=document.getElementById('pv-phase-24h'); if(!root) return;
    try{
      const res=await fetch(`${BASE}data/pv-phase-24h.json?ts=${Date.now()}`,{cache:'no-store'}); if(!res.ok) throw new Error(`HTTP ${res.status}`);
      const data=await res.json(), samples=Array.isArray(data.samples)?data.samples:[], a=data.analysis||{};
      const rows=Object.entries(a).map(([name,r])=>`<tr><td>${esc(name)}</td><td><strong>${esc(r.best_phase||'—')}</strong></td><td>${esc(r.confidence||'—')}</td><td>${fmt(r.best_score)}</td><td>${fmt(r.margin)}</td></tr>`).join('');
      const detail=Object.entries(a).map(([name,r])=>`<details><summary>${esc(name)}</summary><ul>${(Array.isArray(r.scores)?r.scores:[]).map(s=>`<li><strong>${esc(s.phase)}</strong>: corr ${fmt(s.correlation)}, Δ-corr ${fmt(s.delta_correlation)}</li>`).join('')||'<li>Nog geen scores</li>'}</ul></details>`).join('');
      const last=samples.at(-1)||{};
      const interval=Number(data.sample_interval_minutes);
      const intervalText=Number.isFinite(interval)&&interval>0?`${interval} min`:'onbekend';
      const generatedMs=new Date(data.generated_at).getTime();
      const ageMinutes=Number.isFinite(generatedMs)?Math.max(0,(Date.now()-generatedMs)/60000):null;
      const staleAfterMinutes=Number.isFinite(interval)&&interval>0?Math.max(15,interval*3):15;
      const freshness=ageMinutes===null?'onbekend':ageMinutes<=staleAfterMinutes?'actueel':'verouderd';
      const basis=data.analysis_basis==='timestamp'?'tijdstempels':esc(data.analysis_basis||'onbekend');
      root.innerHTML=`<div class="phase-live-meta"><strong>Laatste publicatie:</strong> ${fmtDate(data.generated_at)} · <strong>status:</strong> ${freshness} · <strong>meetinterval:</strong> ${intervalText} · <strong>analyse:</strong> ${basis} · <strong>samples:</strong> ${esc(data.sample_count??samples.length)} · <strong>venster:</strong> ${esc(data.window_hours??24)} uur</div>${drawChart(samples)}${samples.length?`<div class="phase-current"><strong>Laatste meetpunt:</strong> L1 ${Math.round(Number(last.l1W)||0)} W · L2 ${Math.round(Number(last.l2W)||0)} W · L3 ${Math.round(Number(last.l3W)||0)} W</div>`:''}${rows?`<h3>Automatische omvormer-faseanalyse</h3><div class="phase-table-wrap"><table><thead><tr><th>Omvormer</th><th>Beste fase</th><th>Confidence</th><th>Score</th><th>Marge</th></tr></thead><tbody>${rows}</tbody></table></div>`:'<p><em>Nog geen betrouwbare omvormeranalyse beschikbaar.</em></p>'}${detail}`;
    }catch(e){root.innerHTML=`<p><em>Live fase-analyse kon niet worden geladen: ${esc(e.message)}</em></p>`;}
  }
  document.addEventListener('DOMContentLoaded',loadPhase);
  document.addEventListener('DOMContentSwitch',loadPhase);
})();
