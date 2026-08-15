# Schaduwmonitoring

Deze pagina toont de onafhankelijke shadowmetingen van de Energy Manager en M7. **Geen van deze gegevens stuurt apparaten aan.**

<div id="shadow-monitor">
  <p>Shadowdata laden…</p>
</div>

<script>
(function () {
  const root = document.getElementById('shadow-monitor');
  const DATA_URL = 'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/shadow-status.json';
  const esc = v => String(v ?? '–').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = ts => ts ? new Date(ts).toLocaleString('nl-NL') : '–';
  const yesno = v => v ? 'ACTIEF' : 'INACTIEF';
  function latestTable(x) {
    if (!x) return '<em>Nog geen sample.</em>';
    return '<table><tbody>' + Object.entries(x).filter(([k]) => k !== 'ts' && typeof x[k] !== 'object').map(([k,v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join('') + `<tr><th>tijd</th><td>${esc(fmt(x.ts))}</td></tr></tbody></table>`;
  }
  async function load() {
    try {
      const r = await fetch(DATA_URL + '?ts=' + Date.now(), {cache:'no-store'});
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const d = await r.json(), c = d.collection || {}, m = d.m7_opportunity?.latest || c.m7_opportunity?.latest || {};
      const samples = d.m7_opportunity?.samples || [];
      root.innerHTML = `
        <p><strong>Laatst gesynchroniseerd:</strong> ${esc(fmt(d.generated_at))}</p>
        <div class="grid cards" markdown="0">
          <div class="card"><h3>Baseline v0.1</h3><p><strong>${esc(c.baseline_v01?.sample_count ?? 0)}</strong> samples · ${yesno(c.baseline_v01?.enabled)}</p></div>
          <div class="card"><h3>Shadow v0.2 + Quooker</h3><p><strong>${esc(c.shadow_v02_quooker?.sample_count ?? 0)}</strong> samples · ${yesno(c.shadow_v02_quooker?.enabled)}</p></div>
          <div class="card"><h3>M7 Opportunity</h3><p><strong>${esc(c.m7_opportunity?.sample_count ?? 0)}</strong> kwartiersamples · ${yesno(c.m7_opportunity?.enabled)}</p></div>
        </div>
        <h2>Laatste M7-analyse</h2>
        <table><tbody><tr><th>Opportunity score</th><td>${esc(m.score)}</td></tr><tr><th>Advies</th><td>${esc(m.advice)}</td></tr><tr><th>Kandidaat</th><td>${esc(m.candidate)}</td></tr><tr><th>Reden</th><td>${esc(m.reason)}</td></tr></tbody></table>
        <h2>Actuele M7-context</h2>${latestTable(d.m7_context)}
        <h2>Laatste baselinebeslissing</h2>${latestTable(c.baseline_v01?.latest)}
        <h2>Laatste v0.2-beslissing</h2>${latestTable(c.shadow_v02_quooker?.latest)}
        <h2>Recente M7-samples</h2>
        <div style="overflow:auto"><table><thead><tr><th>Tijd</th><th>Score</th><th>Advies</th><th>Kandidaat</th><th>Net</th><th>Reden</th></tr></thead><tbody>${samples.slice(-24).reverse().map(x => `<tr><td>${esc(fmt(x.ts))}</td><td>${esc(x.score)}</td><td>${esc(x.advice)}</td><td>${esc(x.candidate)}</td><td>${esc(x.actual?.exportW > 0 ? '-' + x.actual.exportW + ' W export' : (x.actual?.importW ?? '–') + ' W import')}</td><td>${esc(x.reason)}</td></tr>`).join('')}</tbody></table></div>`;
    } catch (e) {
      root.innerHTML = `<div class="admonition warning"><p class="admonition-title">Shadowdata nog niet beschikbaar</p><p>${esc(e.message)}. De dedicated Homey shadow-sync publiceert docs/data/shadow-status.json.</p></div>`;
    }
  }
  load(); setInterval(load, 60000);
})();
</script>
