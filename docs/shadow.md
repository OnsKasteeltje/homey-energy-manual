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

## Hoe herkennen we dat de boiler op temperatuur is?

Homey leest de interne thermostaat of watertemperatuur van de boiler niet rechtstreeks uit. We leiden de toestand daarom af uit twee signalen die wél beschikbaar zijn: **de AAN/UIT-stand en het werkelijk gemeten elektrische vermogen van de boiler**.

De volledige herkenningsketen is:

**`VERWARMEN → AFKOELEN_WACHT → OP_TEMPERATUUR → boiler-cycles.json`**

### Stap 1 — `VERWARMEN`

Wanneer de boiler AAN staat en meer dan **1.500 W** gebruikt, is het verwarmingselement aantoonbaar actief. Bij normaal verwarmen ligt het werkelijke vermogen rond 2 kW. De observer noemt dit `VERWARMEN`.

Voordat een latere vermogensdaling als thermostaat-afslag mag worden geïnterpreteerd, moet minimaal **15 minuten** verwarmen zijn bevestigd. Een toevallige korte vermogenspiek kan daardoor niet direct een volledige verwarmingscyclus opleveren.

### Stap 2 — `AFKOELEN_WACHT`

Wanneer de boiler aantoonbaar heeft verwarmd en het vermogen vervolgens onder **100 W** zakt terwijl de boiler zelf nog steeds AAN staat, is de meest waarschijnlijke verklaring dat de **interne thermostaat het verwarmingselement heeft uitgeschakeld**.

We verklaren de boiler niet onmiddellijk op temperatuur. Eerst wordt `AFKOELEN_WACHT` gebruikt. Het vermogen moet **10 minuten onder 100 W** blijven. Daarmee worden korte dips, meetfouten of tijdelijke onderbrekingen uitgefilterd.

### Stap 3 — `OP_TEMPERATUUR`

Als de boiler nog steeds AAN staat, eerder minimaal 15 minuten echt heeft verwarmd en vervolgens minimaal 10 minuten vrijwel geen vermogen meer gebruikt, wordt de status **`OP_TEMPERATUUR`**.

Dit betekent praktisch:

> Homey heeft indirect maar aantoonbaar vastgesteld dat de boiler na een echte verwarmingsperiode zelf is gestopt met elektrisch verwarmen. Daarmee beschouwen we de ingestelde boilertemperatuur als bereikt.

Deze methode heeft geen extra temperatuursensor nodig. De status blijft wel een afgeleide toestand: we meten de thermostaat niet rechtstreeks, maar herkennen zijn elektrische effect.

### Stap 4 — cyclus opslaan

Zodra `OP_TEMPERATUUR` is bevestigd, is de verwarmingscyclus voltooid. De cyclus wordt vervolgens klaargezet voor publicatie naar **`boiler-cycles.json`**. Daar bewaren we onder andere start- en eindtijd, duur, boiler-kWh, geschat PV- en netaandeel en of de temperatuurstatus daadwerkelijk is bereikt.

Een cyclus kan bijvoorbeeld conceptueel opleveren: start 23:15, `OP_TEMPERATUUR` 01:40, 2 uur 25 minuten looptijd, 4,8 kWh boilerenergie en een bepaald PV-/netaandeel. De echte waarden worden uiteraard uit de Homey-metingen berekend.

!!! info "Waarom dit belangrijk is voor de toekomstige warmwaterregeling"
    Als deze detectieketen in de praktijk betrouwbaar blijkt, kan `OP_TEMPERATUUR` uiteindelijk het **primaire dagelijkse warmwaterdoel** worden. De huidige 240-minutenregel vóór 19:00 kan dan als veiligheids-/fallbackregel blijven bestaan in plaats van het primaire succescriterium te zijn.

### Overige boilerstatussen

- `UIT`: boiler is uit;
- `AAN_WACHT`: boiler staat aan, maar deze observer heeft nog geen voldoende lange verwarmingsperiode gezien om een thermostaat-afslag te mogen bevestigen;
- `VERWARMEN`: boiler staat aan en gebruikt meer dan 1.500 W;
- `AFKOELEN_WACHT`: eerder bevestigd verwarmd en nu minder dan 100 W, maar de 10-minutenbevestiging loopt nog;
- `OP_TEMPERATUUR`: thermostaat-afslag is volgens bovenstaande regels bevestigd.

**Deze detectie is uitsluitend observerend en stuurt de boiler niet aan.**

## Nachtelijke praktijktest

Een natuurlijke nachtelijke opwarmcyclus is juist een goede acceptatietest. Wanneer vóór het slapen warm water wordt gebruikt en de boiler daarna elektrisch gaat bijverwarmen, kan v1.6.4 de volledige overgang automatisch volgen.

Voor een geslaagde test verwachten we achtereenvolgens:

1. boiler AAN en >1.500 W → `VERWARMEN`;
2. minimaal 15 minuten aantoonbaar verwarmen;
3. na het bereiken van de thermostaattemperatuur daalt het vermogen tot <100 W → `AFKOELEN_WACHT`;
4. na 10 minuten blijvend <100 W → `OP_TEMPERATUUR`;
5. de afgeronde cyclus verschijnt bij een publisher-run in `boiler-cycles.json`.

De gebruiker hoeft hiervoor niet wakker te blijven of handmatig het vermogen te controleren. De 2-minutenobserver houdt de toestand bij en de 15-minutenpublisher bewaart de relevante resultaten. De volgende ochtend kan de cyclus worden beoordeeld op statusovergang, duur, energiegebruik en geschat PV-/netaandeel.

!!! warning "Voorwaarde voor deze test"
    De boiler moet tijdens de nacht **AAN mogen blijven** totdat zijn interne thermostaat het verwarmingselement uitschakelt. Als een andere actieve Homey-regeling de boiler eerder UIT zet, eindigt de cyclus met reden `UIT` en is dat geen volledige acceptatietest van `OP_TEMPERATUUR`.

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

Per cyclus worden onder andere opgeslagen: start- en eindtijd, duur en eindreden; geschat totaal boilerverbruik; geschat PV- en netaandeel; gemiddeld en maximaal P1-netimport; aantal samples; geïntegreerde minuten; en of `OP_TEMPERATUUR` is bereikt.

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
  const URLs = {status:BASE+'homey-status.json',baseline:BASE+'shadow-baseline-v01.json',cycles:BASE+'boiler-cycles.json',daily:BASE+'energy-daily-history.json',v02:BASE+'shadow-v02-quooker.json',m7:BASE+'m7-opportunity.json'};
  const esc = v => String(v ?? '–').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = ts => ts ? new Date(ts).toLocaleString('nl-NL') : '–';
  async function get(url,optional=false){const r=await fetch(url+'?ts='+Date.now(),{cache:'no-store'});if(optional&&r.status===404)return null;if(!r.ok)throw new Error(`${url.split('/').pop()}: HTTP ${r.status}`);return r.json();}
  function enabledFrom(status,name,fallback){const f=(status?.flows||[]).find(x=>x.name===name);return f?!!f.enabled:!!fallback;}
  function latestTable(x,tsField='ts'){if(!x)return '<em>Nog geen gegevens.</em>';return '<table><tbody>'+Object.entries(x).filter(([k])=>k!==tsField&&typeof x[k]!=='object').map(([k,v])=>`<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join('')+`<tr><th>tijd</th><td>${esc(fmt(x[tsField]))}</td></tr></tbody></table>`;}
  async function load(){try{const [status,baseline,cycles,daily,v02,m7]=await Promise.all([get(URLs.status,true),get(URLs.baseline,true),get(URLs.cycles,true),get(URLs.daily,true),get(URLs.v02,true),get(URLs.m7,true)]);const bEnabled=enabledFrom(status,'Energie Manager PV - Shadow Mode v1.6.4',baseline?.enabled),vEnabled=enabledFrom(status,'Energie Manager PV - Shadow Mode v0.2 Quooker',v02?.enabled),mEnabled=enabledFrom(status,'M7 - Opportunity Score - Shadow',m7?.enabled),cycleList=cycles?.cycles||[],lastCycle=cycleList.length?cycleList[cycleList.length-1]:null,days=daily?.days||[],lastDay=days.length?days[days.length-1]:null,ml=m7?.latest||null,latestTimes=[baseline?.generated_at,cycles?.generated_at,daily?.generated_at,m7?.generated_at].filter(Boolean).map(x=>new Date(x).getTime()).filter(Number.isFinite),latestSync=latestTimes.length?new Date(Math.max(...latestTimes)).toISOString():null;root.innerHTML=`<p><strong>Laatste shadowpublicatie:</strong> ${esc(fmt(latestSync))}</p><div class="grid cards" markdown="0"><div class="card"><h3>Baseline v1.6.4</h3><p><strong>${esc(baseline?.sample_count??0)}</strong> samples · ${bEnabled?'ACTIEF':'INACTIEF'}</p><p><small>${esc(fmt(baseline?.generated_at))}</small></p></div><div class="card"><h3>Boilercycli</h3><p><strong>${esc(cycleList.length)}</strong> cycli · 90 dagen</p><p><small>${lastCycle?esc(lastCycle.boiler_kWh_est)+' kWh · '+esc(lastCycle.pv_share_pct_est)+'% PV':'Nog geen afgeronde v1.6.4-cyclus'}</small></p></div><div class="card"><h3>Daghistorie</h3><p><strong>${esc(days.length)}</strong> afgeronde dagen</p><p><small>${lastDay?'Laatste: '+esc(lastDay.date):'Nog geen afgeronde dag'}</small></p></div><div class="card"><h3>M7 Opportunity</h3><p><strong>${esc(m7?.sample_count??0)}</strong> samples · ${mEnabled?'ACTIEF':'INACTIEF'}</p></div></div><h2>Laatste baselinebeslissing</h2>${latestTable(baseline?.latest)}<h2>Laatste boilercyclus</h2>${lastCycle?latestTable(lastCycle,'end_ts'):'<em>Nog geen afgeronde boilercyclus gepubliceerd.</em>'}<h2>Laatste afgeronde dag</h2>${lastDay?latestTable(lastDay,'last_ts'):'<em>De eerste dag wordt na middernacht toegevoegd.</em>'}<h2>Laatste M7-analyse</h2>${ml?latestTable(ml):'<em>Nog geen M7-sample.</em>'}<h2>Shadow v0.2 + Quooker</h2><p>${vEnabled?'ACTIEF':'INACTIEF'} · ${esc(v02?.sample_count??0)} samples</p>`;}catch(e){root.innerHTML=`<div class="admonition warning"><p class="admonition-title">Shadowdata kon niet volledig worden geladen</p><p>${esc(e.message)}</p></div>`;}}load();setInterval(load,60000);})();
</script>