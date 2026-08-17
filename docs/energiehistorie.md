# Energiehistorie

<div id="energy-history-dashboard">
  <p><em>Energiehistorie wordt geladen…</em></p>
</div>

!!! info "Energy Core v2 is leidend voor Dag"
    **Dag** gebruikt vanaf 17 augustus 2026 de nieuwe `energy-day-v2.json`-reeks uit `EM v2 | 70 History | Day Series v0.1`. Deze flow leest uitsluitend `EM2_State` en veroorzaakt **geen extra device-reads**. **Week**, **Maand** en **Jaar** gebruiken voorlopig de bestaande compacte `energy-daily-history.json`.

!!! note "Opbouw vanaf migratiemoment"
    De nieuwe v2-dagreeks start op het moment van migratie. Er worden geen fictieve eerdere meetpunten aangemaakt. Daarom beginnen de dag-kWh en de grafiek vanaf het eerste echte v2-historypunt van vandaag en groeien daarna automatisch verder.

## Berekeningsprincipes

Op dagniveau geldt:

```text
PV-productie = SolarEdge + GoodWe GW4200D-NS + GoodWe GW2000-XS
Woningverbruik = PV-productie + P1-netvermogen
Netimport = max(P1, 0)
Netexport = max(-P1, 0)
Direct eigen PV-verbruik = max(PV - netexport, 0)
```

De history-flow draait iedere vijf minuten. Hij doet geen eigen meting van apparaten, maar leest de centrale `EM2_State`. Wanneer die state door de deadband niet is vernieuwd, wordt de laatst bekende toestand als **hold-last-value** gebruikt en krijgt het historypunt `held=true`. Daarmee ontstaat een regelmatige meetreeks zonder een tweede Homey-device-scan. De pagina toont hoeveel historypunten hiervan hold-punten zijn.

Vanaf twee echte tijdspunten berekent de website de kWh met trapeziumintegratie over de tijd. Een interval wordt voor robuustheid gemaximeerd op tien minuten zodat een langere datagaping niet stilzwijgend als een volledig gemeten periode wordt meegerekend.

## Activiteitstijdlijn

De dagreeks bevat naast P1 en PV ook de reeds in `EM2_State` aanwezige status van Tesla, boiler, wasmachine en droger. De tijdlijn wordt daardoor uit dezelfde v2-dataset opgebouwd. Er is geen aparte legacy-baselinefeed meer nodig voor het Dagoverzicht.

## Homey-load

```text
EM v2 State (bestaande centrale read)
        ↓
EM2_State
        ↓ Logic-only, iedere 5 min
EM v2 | 70 History | Day Series v0.1
        ↓ lokale ringbuffer
GitHub-publicatie max. iedere 15 min
        ↓
energy-day-v2.json
        ↓
Energiehistorie · Dag
```

De extra Homey-belasting bestaat daarmee uit één Logic-read/-write per vijf minuten. Er wordt **geen extra `getDevices()`** uitgevoerd. GitHub wordt maximaal vier keer per uur bijgewerkt.

De interface bevat al **Accu geladen** en **Accu ontladen**. Totdat live Victron ESS-metingen beschikbaar zijn, blijven deze waarden bewust op 0 / nog geen opslagmeting; er wordt geen batterijdata geschat.

> Laatste update: **17 augustus 2026** — Dagoverzicht gemigreerd naar Energy Core v2-daghistorie; legacy `pv-phase-24h.json` en `shadow-baseline-v01.json` zijn niet langer nodig voor de Dag-tab.
