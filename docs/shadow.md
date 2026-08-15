# Schaduwmonitoring

Deze pagina toont de onafhankelijke shadowmetingen van de Energy Manager en M7. **Geen van deze gegevens stuurt apparaten aan.** De shadowflows rekenen alleen uit wat de toekomstige energieregeling *zou* doen en bewaren die uitkomst voor analyse.

## Wat draait er in shadow mode?

### Baseline v0.1 — Energie Manager PV

Dit is de **nulmeting** van de Energy Manager. De flow kijkt naar de actuele energietoestand van de woning en berekent op basis daarvan een advies voor flexibel verbruik, zonder iets te schakelen.

**Gebruikte informatie:**

- P1/netvermogen: import of export;
- actuele Tesla/Easee-status en laadvermogen;
- boilerstatus en boilervermogen;
- beschikbare PV-/netoverschotcontext;
- tijdvensters voor Tesla en boiler.

**Wat wordt berekend:**

- hoeveel vermogen als beschikbaar PV-/netoverschot kan worden beschouwd;
- welk Tesla-laadniveau daarbij zou passen;
- of na reservering voor de Tesla nog voldoende vermogen voor de boiler overblijft;
- een korte status/beslissing die als sample wordt opgeslagen.

De flow **wijzigt geen laadstroom, schakelt de boiler niet en stuurt geen andere apparaten aan**. De verzamelde v0.1-samples vormen de referentie waarmee latere versies worden vergeleken.

### Shadow v0.2 — Energie Manager PV + Quooker

v0.2 gebruikt dezelfde basislogica als de baseline, maar voegt de **Quooker als extra context** toe. Ook deze versie blijft volledig read-only.

Naast de informatie uit v0.1 kijkt deze flow naar:

- of de Quooker op dat moment aan of uit staat;
- of het tijdstip binnen het bestaande Quooker-tijdvenster valt;
- een shadowadvies `TOEGESTAAN` of `BUITEN_VENSTER` voor de Quooker-context.

De bestaande Quooker-flows blijven leidend voor de echte aansturing. v0.2 observeert alleen hoe Quooker-gebruik samenvalt met PV, Tesla en boiler. Daardoor kunnen we later beoordelen of centrale coördinatie voordeel oplevert zonder de huidige werking te verstoren.

### M7 Opportunity Score — prijs + PV-forecast

M7 is een **aparte parallelle analyselaag**. Deze flow verandert de baseline- of v0.2-logica niet en schrijft naar een eigen shadowstate.

M7 combineert vier relatieve forecasts/signalen:

- `priceNegative` — de actuele stroomprijs is negatief;
- `priceCheapNext4h` — nu is relatief goedkoop ten opzichte van de komende vier uur;
- `priceExpensiveNext4h` — nu is relatief duur ten opzichte van de komende vier uur;
- `pvTop4h` — het huidige uur behoort tot de vier beste verwachte PV-uren tussen 09:00 en 18:00.

Daarbij wordt de forecastcontext gecombineerd met de **werkelijke situatie**: netimport/-export, Tesla, boiler en Quooker. M7 maakt daar een Opportunity Score, advies, kandidaat en tekstuele reden van. Voorbeelden van mogelijke adviezen zijn een flexibel verbruiksmoment benutten, PV-overschot gebruiken, flexibel verbruik uitstellen of neutraal blijven.

M7 bepaalt dus niet rechtstreeks *wat een apparaat moet doen*. Het beoordeelt eerst **hoe aantrekkelijk het huidige kwartier energetisch/economisch is**. Later kunnen we vergelijken of dit extra inzicht betere beslissingen zou opleveren dan de bestaande Energy Manager alleen.

## Waarom drie gescheiden reeksen?

De drie datasets worden bewust gescheiden gehouden:

| Reeks | Doel | Besturing |
|---|---|---|
| Baseline v0.1 | Referentie van de oorspronkelijke Energy Manager | Geen |
| Shadow v0.2 + Quooker | Effect van Quooker-context vergelijken met v0.1 | Geen |
| M7 Opportunity | Toegevoegde waarde van prijs- en PV-forecast beoordelen | Geen |

Hierdoor kunnen we achteraf dezelfde momenten naast elkaar leggen: **wat adviseerde de baseline, wat zou v0.2 hebben gedaan, wat vond M7 een aantrekkelijk moment en wat gebeurde er werkelijk?** Pas na voldoende vergelijking worden wijzigingen overwogen voor de actieve regelarchitectuur.

## Live verzamelde shadowdata

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
        ${samples.length ? `<div style="overflow:auto"><table><thead><tr><th>Tijd</th><th>Score</th><th>Advies</th><th>Kandidaat</th><th>Net</th><th>Reden</th></tr></thead><tbody>${samples.slice(-24).reverse().map(x => `<tr><td>${esc(fmt(x.ts))}</td><td>${esc(x.score)}</td><td>${esc(x.advice)}</td><td>${esc(x.candidate)}</td><td>${esc(x.actual?.exportW > 0 ? '-' + x.actual.exportW + ' W export' : (x.actual?.importW ?? '–') + ' W import')}</td><td>${esc(x.reason)}</td></tr>`).join('')}</tbody></table></div>` : '<em>Nog geen M7-samples gepubliceerd.</em>'}`;
    } catch (e) {
      root.innerHTML = `<div class="admonition warning"><p class="admonition-title">Shadowdata nog niet beschikbaar</p><p>${esc(e.message)}. De dedicated Homey shadow-sync publiceert docs/data/shadow-status.json.</p></div>`;
    }
  }
  load(); setInterval(load, 60000);
})();
</script>
