# Energiehistorie

<div id="energy-history-dashboard">
  <p><em>Energiehistorie wordt geladen…</em></p>
</div>

!!! info "Energy Core v2 is leidend voor Dag én persistentie"
    **Dag** gebruikt `energy-day-v2.json` uit `EM v2 | 70 History | Day Series v0.3`. Deze flow leest uitsluitend `EM2_State` en veroorzaakt **geen extra device-reads**. Bij een kalenderwissel archiveert v0.3 de afgesloten dag eerst definitief naar `energy-daily-history.json`; pas na een succesvolle persistente GitHub-write wordt de lokale dagbuffer voor de nieuwe dag gestart. **Week**, **Maand** en **Jaar** lezen vervolgens deze persistente dagrecords.

!!! warning "Tesla legacy-historie uitgesloten"
    De oude `tesla_kWh_est` uit Shadow Mode is een 15-minuten-schatting en wordt vanaf 18 augustus 2026 niet meer als feitelijk Tesla-verbruik weergegeven. Nieuwe Tesla-energie wordt opgebouwd uit `teslaW` in de Energy Core v2-dagreeks en over de werkelijke sample-timestamps geïntegreerd. Totdat een dag volledig via deze methode is gearchiveerd, toont de historische Tesla-waarde bewust `—` in plaats van een legacy-schatting.

!!! note "Rollover en herstel 18 augustus"
    Day Series v0.2 publiceerde de actuele dag wel, maar reset bij een kalenderwissel de lokale buffer zonder de afgesloten dag eerst naar `energy-daily-history.json` te archiveren. Daardoor ontbraken 17 en 18 augustus in Week/Maand/Jaar. In v0.3 is dit fail-safe gemaakt: **archive first, reset second**. De vrijwel dagdekkende v2-snapshot van 18 augustus is eenmalig uit de immutable Git-historie gereconstrueerd en met expliciete kwaliteitsmetadata teruggezet. De beschikbare v2-reeks van 17 augustus begint pas rond 08:52 lokale tijd en wordt daarom niet als volledige dag teruggevuld.

!!! note "Herstel v2.8.37"
    De eerste presentatiefilter voor legacy Tesla-data gebruikte onbedoeld een `MutationObserver` op het dashboard dat hij zelf wijzigde. Daardoor kon een zelf-triggerende DOM-lus ontstaan, waardoor Week/Maand/Jaar en ook de Material-navigatie/inhoudsopgave niet meer reageerden. In `energy-history-tesla-quality-v2.8.37.js` is die observer verwijderd; de filter draait nu alleen bij laden, paginaswitch en een klik op de historie-tabs.

!!! note "Opbouw vanaf migratiemoment"
    De nieuwe v2-dagreeks start op het moment van migratie. Er worden geen fictieve eerdere meetpunten aangemaakt. Ontbrekende perioden worden dus niet achteraf verzonnen; alleen aantoonbaar aanwezige v2-samples mogen als historie worden geïntegreerd.

## Berekeningsprincipes

Op dagniveau geldt:

```text
PV-productie = SolarEdge + GoodWe GW4200D-NS + GoodWe GW2000-XS
Woningverbruik = PV-productie + P1-netvermogen
Netimport = max(P1, 0)
Netexport = max(-P1, 0)
Direct eigen PV-verbruik = max(PV - netexport, 0)
Tesla-energie = integraal(teslaW × werkelijke sampletijd)
```

De history-flow draait iedere vijf minuten. Hij doet geen eigen meting van apparaten, maar leest de centrale `EM2_State`. Wanneer die state door de deadband niet is vernieuwd, wordt de laatst bekende toestand als **hold-last-value** gebruikt en krijgt het historypunt `held=true`. Daarmee ontstaat een regelmatige meetreeks zonder een tweede Homey-device-scan.

Vanaf twee echte tijdspunten worden kWh met trapeziumintegratie over de tijd berekend. Een interval wordt voor robuustheid gemaximeerd op tien minuten zodat een langere datagaping niet stilzwijgend als een volledig gemeten periode wordt meegerekend. Dezelfde integratiemethode wordt zowel voor live Dag als voor de definitieve v0.3-dagarchive gebruikt.

## Persistente dagketen

```text
EM2_State
   ↓ iedere 5 min, logic-only
EM2_Day_History (lopende dagbuffer)
   ↓ max. iedere 15 min
energy-day-v2.json  → Dag / vandaag
   ↓ kalenderwissel
finaliseer afgesloten dag
   ↓ EERST succesvolle persistente write
energy-daily-history.json
   ↓
Week / Maand / Jaar
   ↓ DAARNA
nieuwe EM2_Day_History-buffer
```

Als de persistente archive-write bij de dagwissel faalt, wordt de oude buffer **niet** weggegooid. De flow stopt met een fout en kan bij een volgende run opnieuw proberen. Daarmee kan een tijdelijke GitHub- of netwerkfout niet meer stilzwijgend een volledige dag wissen.

## Activiteitstijdlijn

De dagreeks bevat naast P1 en PV ook de reeds in `EM2_State` aanwezige status van Tesla, boiler, wasmachine en droger. De tijdlijn wordt daardoor uit dezelfde v2-dataset opgebouwd. Er is geen aparte legacy-baselinefeed meer nodig voor het Dagoverzicht.

## Homey-load

```text
EM v2 State (bestaande centrale read)
        ↓
EM2_State
        ↓ Logic-only, iedere 5 min
EM v2 | 70 History | Day Series v0.3
        ↓ lokale ringbuffer
GitHub live-publicatie max. iedere 15 min
        ↓
energy-day-v2.json
```

De extra Homey-belasting blijft Logic-only; er wordt **geen extra `getDevices()`** uitgevoerd. De persistente daily archive voegt alleen bij een kalenderwissel een GitHub read/write toe.

De interface bevat al **Accu geladen** en **Accu ontladen**. Totdat live Victron ESS-metingen beschikbaar zijn, blijven deze waarden bewust op 0 / nog geen opslagmeting; er wordt geen batterijdata geschat.

> Laatste update: **19 augustus 2026** — Day Series v0.3 maakt de dagrollover atomisch (`archive first, reset second`) en 18 augustus is gecontroleerd vanuit de v2 Git-snapshot teruggezet; 17 augustus blijft bewust onvolledig/ontbrekend omdat geen volledige v2-dagbron beschikbaar is.
