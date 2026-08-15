# Schaduwmonitoring

Deze pagina toont de onafhankelijke shadowmetingen van de Energy Manager en M7. **Geen van deze gegevens stuurt apparaten aan.** De shadowflows rekenen alleen uit wat de toekomstige energieregeling *zou* doen en bewaren de uitkomst voor analyse.

!!! info "Homey-flow en website horen bij elkaar"
    Wanneer een Homey-flow wordt gewijzigd, wordt ook de bijbehorende flowbeschrijving op deze website gecontroleerd en bijgewerkt. De website beschrijft de **actueel geïmplementeerde Homey-situatie**.

## Wat draait er in shadow mode?

### Baseline — Energie Manager PV v1.6.4

De actieve implementatie is **`Energie Manager PV - Shadow Mode v1.6.4`**. Oudere subversies blijven als audit-/terugvalversie in Homey aanwezig maar zijn uitgeschakeld.

v1.6.4 kijkt naar P1/netvermogen, Tesla/Easee en boiler en berekent welk Tesla-laadniveau en welke boilerbeslissing bij het beschikbare PV-overschot zouden passen. De flow schakelt niets.

Dezelfde HomeyScript-kaart wordt door twee timers gebruikt:

- iedere **2 minuten** voor boilerstatus en energie-integratie van een actieve boilercyclus;
- iedere **15 minuten** voor de operationele GitHub-publicatie.

De persistente runtime-state staat in één unieke Homey Logic-string: **`EM Shadow Runtime State v1.6.4`**. Daarmee gebruikt v1.6.4 geen HomeyScript `get()/set()` meer voor persistente state. De Logic-state blijft bewust compact en bevat alleen observerstatus, actieve cyclus, nog te publiceren afgeronde cycli en timinginformatie.

### Boilerstatus

De observer gebruikt de volgende regels:

- `UIT`: boiler is uit;
- `VERWARMEN`: boiler staat aan en gebruikt meer dan **1.500 W**;
- verwarmen moet eerst minimaal **15 minuten** zijn bevestigd;
- daarna leidt minimaal **10 minuten onder 100 W**, terwijl de boiler aan blijft, tot `OP_TEMPERATUUR`;
- tussenstatussen zoals `AAN_WACHT` en `AFKOELEN_WACHT` voorkomen een te vroege thermostaatdetectie.

**Deze detectie is uitsluitend observerend en stuurt de boiler niet aan.**

### Shadow v0.2 — Energie Manager PV + Quooker

v0.2 is een aparte experimentele analyselaag met Quooker, Tesla-sessieregistratie en de warmwatergarantie van 240 minuten vóór 19:00. Deze versie blijft volledig read-only wanneer geactiveerd.

### M7 Opportunity Score — prijs + PV-forecast

M7 is een aparte parallelle analyselaag. De Opportunity Score combineert prijs- en PV-forecastcontext met de werkelijke net-, Tesla-, boiler- en Quookerstatus.

## Logging en bewaartermijnen

| Niveau | Opslag | Interval | Bewaartermijn | Doel |
|---|---|---:|---:|---|
| Runtime | Homey Logic `EM Shadow Runtime State v1.6.4` | 2 min | actuele compacte state | boilerobserver en cyclusintegratie |
| Operationeel | `shadow-baseline-v01.json` | ca. 15 min | ca. 7,5 dagen (720 samples) | websitehistorie en shadowbeslissingen |
| Boilercycli | `boiler-cycles.json` | na afronding, publicatie bij publisher-run | 90 dagen | energieboekhouding per verwarmingscyclus |
| Langlopend | `energy-daily-history.json` | per afgeronde dag | 90 dagen | trends over weken/maanden |

!!! note "Geen grote 2-minutenhistorie in Homey Logic"
    In eerdere ontwerpen werd een lokale 720-samplebuffer voorzien. In v1.6.4 wordt dat bewust niet in Homey Logic opgeslagen om de gedeelde Logic-string compact en robuust te houden. De 2-minutenruns worden wel gebruikt voor de integratie van de actieve boilercyclus; de persistente tijdreeksen staan in GitHub.

## Energieboekhouding per boilercyclus

Een boilercyclus start zodra de boiler AAN staat en meer dan **1.500 W** gebruikt. De cyclus eindigt wanneer de boiler wordt uitgezet of wanneer `OP_TEMPERATUUR` is bevestigd.

De energie wordt geïntegreerd uit de werkelijke tijd tussen opeenvolgende 2-minutenruns. Om een meetonderbreking niet als fictief energiegebruik mee te tellen, wordt een interval op maximaal **5 minuten** begrensd.

Per cyclus worden onder andere opgeslagen:

- start- en eindtijd, duur en eindreden;
- geschat totaal boilerverbruik in kWh;
- geschat PV- en netaandeel in kWh plus PV-percentage;
- gemiddeld en maximaal P1-netimport tijdens de cyclus;
- aantal samples en daadwerkelijk geïntegreerde minuten;
- of `OP_TEMPERATUUR` is bereikt en het eerste waargenomen tijdstip daarvan.

De toerekening is een schatting:

`boiler_grid_W = min(boiler_W, max(0, P1_W))`

`boiler_PV_W = boiler_W - boiler_grid_W`

Deze methode is geschikt voor optimalisatieanalyse maar is geen afzonderlijke fysiek gemeten energiestroom op de boilergroep.

!!! warning "Eerste cyclus na versie-activatie kan gedeeltelijk zijn"
    Wanneer een nieuwe shadowversie wordt geactiveerd terwijl de boiler al verwarmt, begint die versie pas vanaf haar eerste eigen sample te integreren. De eerste geregistreerde cyclus kan daarom gedeeltelijk zijn.

## Automatische daghistorie

Na een succesvolle baselinepublicatie wordt gecontroleerd of een **afgeronde kalenderdag** ontbreekt in `energy-daily-history.json`. Alleen dan wordt een dagsamenvatting geschreven. De lopende dag wordt niet voortijdig als compleet opgeslagen.

Waarden met `_est` zijn schattingen op basis van samples en zijn geen vervanging voor een gecertificeerde energiemeter.

## Publicatiearchitectuur

v1.6.4 gebruikt één scriptkaart en één compacte gedeelde Logic-state. De publisher schrijft eerst de primaire baseline en probeert daarna de secundaire datasets bij te werken. Fouten in daghistorie of boilercycli worden apart gelogd zodat de baseline niet afhankelijk wordt van een secundaire dataset.

| Opslag | Functie |
|---|---|
| Homey Logic runtime-state | observer, actieve cyclus, timing en pending cycli |
| `shadow-baseline-v01.json` | 15-minuten operationele historie |
| `boiler-cycles.json` | 90-daagse cyclusboekhouding |
| `energy-daily-history.json` | compacte 90-daagse daghistorie |

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
    cycles: BASE + 'boiler-cycles.json',
    daily: BASE + 'energy-daily-history.json',
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
  function latestTable(x, tsField='ts') {
    if (!x) return '<em>Nog geen gegevens.</em>';
    return '<table><tbody>' + Object.entries(x)
      .filter(([k]) => k !== tsField && typeof x[k] !== 'object')
      .map(([k,v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join('') +
      `<tr><th>tijd</th><td>${esc(fmt(x[tsField]))}</td></tr></tbody></table>`;
  }
  async function load() {
    try {
      const [status, baseline, cycles, daily, v02, m7] = await Promise.all([
        get(URLs.status,true), get(URLs.baseline,true), get(URLs.cycles,true),
        get(URLs.daily,true), get(URLs.v02,true), get(URLs.m7,true)
      ]);
      const bEnabled = enabledFrom(status, 'Energie Manager PV - Shadow Mode v1.6.4', baseline?.enabled);
      const vEnabled = enabledFrom(status, 'Energie Manager PV - Shadow Mode v0.2 Quooker', v02?.enabled);
      const mEnabled = enabledFrom(status, 'M7 - Opportunity Score - Shadow', m7?.enabled);
      const cycleList = cycles?.cycles || [], lastCycle = cycleList.length ? cycleList[cycleList.length-1] : null;
      const days = daily?.days || [], lastDay = days.length ? days[days.length-1] : null;
      const ml = m7?.latest || null;
      const latestTimes = [baseline?.generated_at, cycles?.generated_at, daily?.generated_at, m7?.generated_at]
        .filter(Boolean).map(x=>new Date(x).getTime()).filter(Number.isFinite);
      const latestSync = latestTimes.length ? new Date(Math.max(...latestTimes)).toISOString() : null;
      root.innerHTML = `
        <p><strong>Laatste shadowpublicatie:</strong> ${esc(fmt(latestSync))}</p>
        <div class="grid cards" markdown="0">
          <div class="card"><h3>Baseline v1.6.4</h3><p><strong>${esc(baseline?.sample_count ?? 0)}</strong> samples · ${bEnabled?'ACTIEF':'INACTIEF'}</p><p><small>${esc(fmt(baseline?.generated_at))}</small></p></div>
          <div class="card"><h3>Boilercycli</h3><p><strong>${esc(cycleList.length)}</strong> cycli · 90 dagen</p><p><small>${lastCycle ? esc(lastCycle.boiler_kWh_est) + ' kWh · ' + esc(lastCycle.pv_share_pct_est) + '% PV' : 'Nog geen afgeronde v1.6.4-cyclus'}</small></p></div>
          <div class="card"><h3>Daghistorie</h3><p><strong>${esc(days.length)}</strong> afgeronde dagen</p><p><small>${lastDay ? 'Laatste: '+esc(lastDay.date) : 'Nog geen afgeronde dag'}</small></p></div>
          <div class="card"><h3>M7 Opportunity</h3><p><strong>${esc(m7?.sample_count ?? 0)}</strong> samples · ${mEnabled?'ACTIEF':'INACTIEF'}</p></div>
        </div>
        <h2>Laatste baselinebeslissing</h2>${latestTable(baseline?.latest)}
        <h2>Laatste boilercyclus</h2>${lastCycle ? latestTable(lastCycle,'end_ts') : '<em>Nog geen afgeronde boilercyclus gepubliceerd.</em>'}
        <h2>Laatste afgeronde dag</h2>${lastDay ? latestTable(lastDay,'last_ts') : '<em>De eerste dag wordt na middernacht toegevoegd.</em>'}
        <h2>Laatste M7-analyse</h2>${ml ? latestTable(ml) : '<em>Nog geen M7-sample.</em>'}
        <h2>Shadow v0.2 + Quooker</h2><p>${vEnabled?'ACTIEF':'INACTIEF'} · ${esc(v02?.sample_count ?? 0)} samples</p>`;
    } catch (e) {
      root.innerHTML = `<div class="admonition warning"><p class="admonition-title">Shadowdata kon niet volledig worden geladen</p><p>${esc(e.message)}</p></div>`;
    }
  }
  load();
  setInterval(load,60000);
})();
</script>
