# Schaduwmonitoring

Deze pagina toont de onafhankelijke shadowmetingen van de Energy Manager en M7. **Geen van deze gegevens stuurt apparaten aan.** De shadowflows rekenen alleen uit wat de toekomstige energieregeling *zou* doen en bewaren die uitkomst voor analyse.

!!! info "Homey-flow en website horen bij elkaar"
    Wanneer een Homey-flow wordt gewijzigd, wordt ook de bijbehorende flowbeschrijving op deze website gecontroleerd en bijgewerkt. Daarbij worden onder andere trigger, frequentie, inputs, logica, outputs, afhankelijkheden, status en websitepublicatie meegenomen. De website hoort dus de **actueel geïmplementeerde Homey-situatie** te beschrijven en niet een oudere ontwerpversie.

## Wat draait er in shadow mode?

### Baseline v0.1 — Energie Manager PV

Dit is de **nulmeting** van de Energy Manager. De flow kijkt naar P1/netvermogen, Tesla/Easee en boiler en berekent welk Tesla-laadniveau en welke boilerbeslissing bij het beschikbare PV-overschot zouden passen. Hij schakelt niets.

Baseline heeft twee onafhankelijke takken binnen dezelfde Advanced Flow:

- een **2-minuten sampler** die maximaal 720 samples lokaal bewaart in `EM_SHADOW_STATE` en niets naar GitHub schrijft;
- een **15-minuten publisher** die de actuele P1-, Tesla- en boilerstatus uitleest, zelfstandig één baselinebeslissing berekent en die publiceert naar `shadow-baseline-v01.json`.

De 2-minutensampler registreert ook de waargenomen boilerstatus. De boiler wordt als `VERWARMEN` gezien bij meer dan 1.500 W. Pas nadat minimaal 15 minuten verwarmen is bevestigd en het vermogen daarna, terwijl de boiler AAN blijft, minimaal 10 minuten onder 100 W blijft, wordt `OP_TEMPERATUUR` geregistreerd. Tussenstatussen voorkomen dat een korte vermogensdip ten onrechte als thermostaat-afslag wordt gezien. **Deze detectie is observerend en schakelt de boiler niet.**

### Shadow v0.2 — Energie Manager PV + Quooker

v0.2 voegt aan de basislogica toe:

- Quooker aan/uit en bestaand gebruiksvenster;
- Tesla-sessieregistratie;
- warmwatergarantie van **240 minuten vóór 19:00**;
- dynamische catch-up, waarbij de warmwatergarantie voorrang krijgt wanneer uitstel niet meer mogelijk is.

Deze versie blijft volledig read-only en publiceert na activatie ongeveer iedere 15 minuten naar `shadow-v02-quooker.json`.

### M7 Opportunity Score — prijs + PV-forecast

M7 is een **aparte parallelle analyselaag**. Vier relatieve signalen worden iedere 15 minuten via gedeelde Homey Logic-variabelen bijgewerkt: `priceNegative`, `priceCheapNext4h`, `priceExpensiveNext4h` en `pvTop4h`.

M7 combineert deze context met de werkelijke net-, Tesla-, boiler- en Quookerstatus. De uitkomst bestaat uit een **Opportunity Score**, advies, kandidaat en tekstuele reden. Iedere kwartier-run voegt rechtstreeks één sample toe aan `m7-opportunity.json`; maximaal 672 kwartiersamples worden daar als persistente websitehistorie bewaard.

## Waarom drie gescheiden reeksen?

| Reeks | Doel | Besturing |
|---|---|---|
| Baseline v0.1 | Referentie van de oorspronkelijke Energy Manager | Geen |
| Shadow v0.2 + Quooker | Quooker + warmwatergarantie vergelijken met v0.1 | Geen |
| M7 Opportunity | Toegevoegde waarde van prijs- en PV-forecast beoordelen | Geen |

Door de datasets gescheiden te houden kunnen we achteraf dezelfde momenten vergelijken zonder dat een nieuwe analyse de oorspronkelijke baseline verandert.

## Logging en bewaartermijnen

De baseline gebruikt bewust drie informatieniveaus. Daardoor blijft de snelle logging lokaal en wordt GitHub niet iedere twee minuten bijgewerkt.

| Niveau | Opslag | Interval | Bewaartermijn | Doel |
|---|---|---:|---:|---|
| Detail | Homey `EM_SHADOW_STATE` | 2 min | ca. 24 uur (720 samples) | diagnose, boilertransities en detailanalyse |
| Operationeel | `shadow-baseline-v01.json` | 15 min | ca. 7,5 dagen (720 samples) | websitehistorie en vergelijking van beslissingen |
| Langlopend | `energy-daily-history.json` | per afgeronde dag | 90 dagen | trends en optimalisatie over meerdere weken/maanden |

### Automatische daghistorie

De 15-minutenpublisher controleert na iedere normale baselinepublicatie of er een **afgeronde kalenderdag** aanwezig is die nog niet in `energy-daily-history.json` staat. Alleen wanneer zo'n dag ontbreekt wordt het daghistoriebestand opnieuw geschreven. De lopende dag wordt dus niet voortijdig als compleet opgeslagen; na middernacht kan de voorafgaande dag worden toegevoegd.

Per dag worden compacte kengetallen bewaard, waaronder geschatte P1-import en -export, boiler- en Tesla-energie, beschikbare PV-energie, boiler-aan- en verwarmminuten, of `OP_TEMPERATUUR` is bereikt en het eerste waargenomen tijdstip daarvan, maximale P1-import/PV-beschikbaarheid en aantallen per shadowstatus.

!!! note "Energiewaarden zijn benaderingen"
    Waarden met `_est` worden uit de 15-minutensamples berekend en zijn daarom **schattingen**, geen vervanging voor een gecertificeerde energiemeter of een volledige integraal over alle 2-minutenmetingen.

## Publicatiearchitectuur

Er is geen centrale shadow-poller meer nodig. Iedere actieve analyselaag publiceert op zijn eigen ritme. **Lokale Homey-state, gedeelde Logic-state en GitHub-historie hebben daarbij verschillende functies:**

| Opslag | Functie |
|---|---|
| HomeyScript lokale state | snelle tijdelijke runtime-/analysehistorie |
| Homey Logic | informatie die betrouwbaar tussen verschillende flows moet worden gedeeld |
| GitHub 15-minuten JSON | persistente operationele historie voor analyse en website |
| GitHub daghistorie | compacte 90-daagse trendhistorie |

Dit ontwerp beperkt Homey- en GitHub-belasting: de 2-minuten baseline-sampling veroorzaakt geen 2-minuten GitHub-publicatie en de daghistorie wordt alleen gewijzigd wanneer een nieuwe afgeronde dag kan worden toegevoegd.

De algemene **Live status** op de homepage en de timestamps hieronder zijn onafhankelijk. `homey-status.json` toont de algemene Homey-sync; iedere shadowdataset toont zijn eigen laatste publicatie. Verschillende timestamps zijn dus normaal zolang ze bij het ingestelde ritme passen.

## Live verzamelde shadowdata

<div id="shadow-monitor">
  <p>Shadowdata laden…</p>
</div>

<script>
(function () {
  const root = document.getElementById('shadow-monitor');
  const BASE = 'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/';
  const URLs = {status:BASE+'homey-status.json',baseline:BASE+'shadow-baseline-v01.json',v02:BASE+'shadow-v02-quooker.json',m7:BASE+'m7-opportunity.json',daily:BASE+'energy-daily-history.json'};
  const esc = v => String(v ?? '–').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = ts => ts ? new Date(ts).toLocaleString('nl-NL') : '–';
  async function get(url, optional=false){const r=await fetch(url+'?ts='+Date.now(),{cache:'no-store'});if(optional&&r.status===404)return null;if(!r.ok)throw new Error(`${url.split('/').pop()}: HTTP ${r.status}`);return r.json();}
  function enabledFrom(status,name,fallback){const f=(status?.flows||[]).find(x=>x.name===name);return f?!!f.enabled:!!fallback;}
  function latestTable(x){if(!x)return '<em>Nog geen sample.</em>';return '<table><tbody>'+Object.entries(x).filter(([k])=>k!=='ts'&&typeof x[k]!=='object').map(([k,v])=>`<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join('')+`<tr><th>tijd</th><td>${esc(fmt(x.ts))}</td></tr></tbody></table>`;}
  async function load(){try{
    const [status,baseline,v02,m7,daily]=await Promise.all([get(URLs.status,true),get(URLs.baseline,true),get(URLs.v02,true),get(URLs.m7,true),get(URLs.daily,true)]);
    const bEnabled=enabledFrom(status,'Energie Manager PV - Shadow Mode',baseline?.enabled),vEnabled=enabledFrom(status,'Energie Manager PV - Shadow Mode v0.2 Quooker',v02?.enabled),mEnabled=enabledFrom(status,'M7 - Opportunity Score - Shadow',m7?.enabled);
    const latestTimes=[baseline?.generated_at,v02?.generated_at,m7?.generated_at].filter(Boolean).map(x=>new Date(x).getTime()).filter(Number.isFinite),latestSync=latestTimes.length?new Date(Math.max(...latestTimes)).toISOString():null;
    const ml=m7?.latest||null,samples=m7?.samples||[],ctx=ml?.context||null,days=daily?.days||[],lastDay=days.length?days[days.length-1]:null;
    const recentRows=samples.slice(-24).reverse().map(x=>`<tr><td>${esc(fmt(x.ts))}</td><td>${esc(x.score)}</td><td>${esc(x.advice)}</td><td>${esc(x.candidate)}</td><td>${esc(x.actual?.exportW>0?x.actual.exportW+' W export':(x.actual?.importW??'–')+' W import')}</td><td>${esc(x.reason)}</td></tr>`).join('');
    root.innerHTML=`<p><strong>Laatste shadowpublicatie:</strong> ${esc(fmt(latestSync))}</p><div class="grid cards" markdown="0"><div class="card"><h3>Baseline v0.1</h3><p><strong>${esc(baseline?.sample_count??0)}</strong> samples · ${bEnabled?'ACTIEF':'INACTIEF'}</p><p><small>15-min historie · bron ${esc(fmt(baseline?.generated_at))}</small></p></div><div class="card"><h3>90-daagse historie</h3><p><strong>${esc(days.length)}</strong> afgeronde dagen</p><p><small>${lastDay?'Laatste dag: '+esc(lastDay.date):'Nog geen afgeronde dag opgeslagen'}</small></p></div><div class="card"><h3>Shadow v0.2 + Quooker</h3><p><strong>${esc(v02?.sample_count??0)}</strong> samples · ${vEnabled?'ACTIEF':'INACTIEF'}</p></div><div class="card"><h3>M7 Opportunity</h3><p><strong>${esc(m7?.sample_count??0)}</strong> kwartiersamples · ${mEnabled?'ACTIEF':'INACTIEF'}</p></div></div><h2>Laatste baselinebeslissing</h2>${latestTable(baseline?.latest)}<h2>Laatste afgeronde dag</h2>${lastDay?latestTable({...lastDay,ts:lastDay.last_ts}):'<em>De eerste dag wordt na middernacht toegevoegd.</em>'}<h2>Laatste M7-analyse</h2>${ml?`<table><tbody><tr><th>Opportunity score</th><td>${esc(ml.score)}</td></tr><tr><th>Advies</th><td>${esc(ml.advice)}</td></tr><tr><th>Kandidaat</th><td>${esc(ml.candidate)}</td></tr><tr><th>Reden</th><td>${esc(ml.reason)}</td></tr></tbody></table>`:'<em>Nog geen M7-sample.</em>'}<h2>Actuele M7-context</h2>${latestTable(ctx?{...ctx,ts:ml?.ts}:null)}<h2>Laatste v0.2-beslissing</h2>${latestTable(v02?.latest)}<h2>Recente M7-samples</h2>${samples.length?`<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse"><thead><tr><th>Tijd</th><th>Score</th><th>Advies</th><th>Kandidaat</th><th>Net</th><th>Reden</th></tr></thead><tbody>${recentRows}</tbody></table></div>`:'<em>Nog geen M7-samples gepubliceerd.</em>'}`;
  }catch(e){root.innerHTML=`<div class="admonition warning"><p class="admonition-title">Shadowdata kon niet volledig worden geladen</p><p>${esc(e.message)}</p></div>`;}}
  load();setInterval(load,60000);
})();
</script>