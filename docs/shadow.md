# Schaduwmonitoring

Deze pagina toont de onafhankelijke shadowmetingen van de Energy Manager en M7. **Geen van deze gegevens stuurt apparaten aan.** De shadowflows rekenen alleen uit wat de toekomstige energieregeling *zou* doen en bewaren die uitkomst voor analyse.

## Wat draait er in shadow mode?

### Baseline v0.1 — Energie Manager PV

Dit is de **nulmeting** van de Energy Manager. De flow kijkt naar P1/netvermogen, Tesla/Easee en boiler en berekent welk Tesla-laadniveau en welke boilerbeslissing bij het beschikbare PV-overschot zouden passen. Hij schakelt niets. Maximaal 720 twee-minutensamples worden lokaal bewaard.

Dezelfde HomeyScript-kaart die deze samples bezit publiceert ongeveer iedere 15 minuten naar `shadow-baseline-v01.json`.

### Shadow v0.2 — Energie Manager PV + Quooker

v0.2 voegt aan de basislogica toe:

- Quooker aan/uit en bestaand gebruiksvenster;
- Tesla-sessieregistratie;
- warmwatergarantie van **240 minuten vóór 19:00**;
- dynamische catch-up, waarbij de warmwatergarantie voorrang krijgt wanneer uitstel niet meer mogelijk is.

Deze versie blijft volledig read-only en publiceert na activatie zijn eigen lokale state naar `shadow-v02-quooker.json`.

### M7 Opportunity Score — prijs + PV-forecast

M7 is een **aparte parallelle analyselaag**. Vier relatieve signalen worden iedere 15 minuten via gedeelde Homey Logic-variabelen bijgewerkt:

- `priceNegative` — actuele prijs is negatief;
- `priceCheapNext4h` — nu is relatief goedkoop versus komende vier uur;
- `priceExpensiveNext4h` — nu is relatief duur versus komende vier uur;
- `pvTop4h` — huidig uur behoort tot de vier beste verwachte PV-uren tussen 09:00 en 18:00.

M7 combineert deze context met de werkelijke net-, Tesla-, boiler- en Quookerstatus. De uitkomst bestaat uit een **Opportunity Score**, advies, kandidaat en tekstuele reden. Maximaal 672 kwartiersamples worden in GitHub bewaard in `m7-opportunity.json`.

## Waarom drie gescheiden reeksen?

| Reeks | Doel | Besturing |
|---|---|---|
| Baseline v0.1 | Referentie van de oorspronkelijke Energy Manager | Geen |
| Shadow v0.2 + Quooker | Quooker + warmwatergarantie vergelijken met v0.1 | Geen |
| M7 Opportunity | Toegevoegde waarde van prijs- en PV-forecast beoordelen | Geen |

Door de datasets gescheiden te houden kunnen we achteraf dezelfde momenten vergelijken zonder dat een nieuwe analyse de oorspronkelijke baseline verandert.

## Publicatiearchitectuur

De centrale shadow-sync is niet meer nodig. De actieve shadowflows publiceren hun eigen dataset rechtstreeks naar GitHub. De GitHub-JSON-bestanden vormen daarbij de persistente websitehistorie.

## Live verzamelde shadowdata

<div id="shadow-monitor">
  <p>Shadowdata laden…</p>
</div>

<script>
(function () {
  const root = document.getElementById('shadow-monitor');
  const BASE = 'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/';
  const URLs = {
    status: BASE + 'homey-status.json',
    baseline: BASE + 'shadow-baseline-v01.json',
    v02: BASE + 'shadow-v02-quooker.json',
    m7: BASE + 'm7-opportunity.json'
  };
  const esc = v => String(v ?? '–').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = ts => ts ? new Date(ts).toLocaleString('nl-NL') : '–';
  async function get(url, optional=false) {
    const r = await fetch(url + '?ts=' + Date.now(), {cache:'no-store'});
    if (optional && r.status === 404) return null;
    if (!r.ok) throw new Error(`${url.split('/').pop()}: HTTP ${r.status}`);
    return r.json();
  }
  function enabledFrom(status, name, fallback) {
    const f = (status?.flows || []).find(x => x.name === name);
    return f ? !!f.enabled : !!fallback;
  }
  function latestTable(x) {
    if (!x) return '<em>Nog geen sample.</em>';
    return '<table><tbody>' + Object.entries(x).filter(([k]) => k !== 'ts' && typeof x[k] !== 'object').map(([k,v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join('') + `<tr><th>tijd</th><td>${esc(fmt(x.ts))}</td></tr></tbody></table>`;
  }
  async function load() {
    try {
      const [status, baseline, v02, m7] = await Promise.all([
        get(URLs.status, true), get(URLs.baseline, true), get(URLs.v02, true), get(URLs.m7, true)
      ]);
      const bEnabled = enabledFrom(status, 'Energie Manager PV - Shadow Mode', baseline?.enabled);
      const vEnabled = enabledFrom(status, 'Energie Manager PV - Shadow Mode v0.2 Quooker', v02?.enabled);
      const mEnabled = enabledFrom(status, 'M7 - Opportunity Score - Shadow', m7?.enabled);
      const latestTimes = [baseline?.generated_at, v02?.generated_at, m7?.generated_at].filter(Boolean).map(x => new Date(x).getTime()).filter(Number.isFinite);
      const latestSync = latestTimes.length ? new Date(Math.max(...latestTimes)).toISOString() : null;
      const ml = m7?.latest || null, samples = m7?.samples || [], ctx = ml?.context || null;
      const recentRows = samples.slice(-24).reverse().map(x => `<tr><td>${esc(fmt(x.ts))}</td><td>${esc(x.score)}</td><td>${esc(x.advice)}</td><td>${esc(x.candidate)}</td><td>${esc(x.actual?.exportW > 0 ? x.actual.exportW + ' W export' : (x.actual?.importW ?? '–') + ' W import')}</td><td>${esc(x.reason)}</td></tr>`).join('');
      root.innerHTML = `
        <p><strong>Laatste shadowpublicatie:</strong> ${esc(fmt(latestSync))}</p>
        <div class="grid cards" markdown="0">
          <div class="card"><h3>Baseline v0.1</h3><p><strong>${esc(baseline?.sample_count ?? 0)}</strong> samples · ${bEnabled?'ACTIEF':'INACTIEF'}</p><p><small>Bron: ${esc(fmt(baseline?.generated_at))}</small></p></div>
          <div class="card"><h3>Shadow v0.2 + Quooker</h3><p><strong>${esc(v02?.sample_count ?? 0)}</strong> samples · ${vEnabled?'ACTIEF':'INACTIEF'}</p><p><small>Bron: ${esc(fmt(v02?.generated_at))}</small></p></div>
          <div class="card"><h3>M7 Opportunity</h3><p><strong>${esc(m7?.sample_count ?? 0)}</strong> kwartiersamples · ${mEnabled?'ACTIEF':'INACTIEF'}</p><p><small>Bron: ${esc(fmt(m7?.generated_at))}</small></p></div>
        </div>
        <h2>Laatste M7-analyse</h2>
        ${ml ? `<table><tbody><tr><th>Opportunity score</th><td>${esc(ml.score)}</td></tr><tr><th>Advies</th><td>${esc(ml.advice)}</td></tr><tr><th>Kandidaat</th><td>${esc(ml.candidate)}</td></tr><tr><th>Reden</th><td>${esc(ml.reason)}</td></tr></tbody></table>` : '<em>Nog geen M7-sample.</em>'}
        <h2>Actuele M7-context</h2>${latestTable(ctx ? {...ctx, ts: ml?.ts} : null)}
        <h2>Laatste baselinebeslissing</h2>${latestTable(baseline?.latest)}
        <h2>Laatste v0.2-beslissing</h2>${latestTable(v02?.latest)}
        <h2>Recente M7-samples</h2>
        ${samples.length ? `<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse"><thead><tr><th>Tijd</th><th>Score</th><th>Advies</th><th>Kandidaat</th><th>Net</th><th>Reden</th></tr></thead><tbody>${recentRows}</tbody></table></div>` : '<em>Nog geen M7-samples gepubliceerd.</em>'}`;
    } catch (e) {
      root.innerHTML = `<div class="admonition warning"><p class="admonition-title">Shadowdata kon niet volledig worden geladen</p><p>${esc(e.message)}</p></div>`;
    }
  }
  load(); setInterval(load, 60000);
})();
</script>
