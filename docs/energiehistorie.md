# Energiehistorie

<div id="energy-history-dashboard">
  <p><em>Energiehistorie wordt geladen…</em></p>
</div>

!!! info "Energy Core v2 is leidend voor Dag én persistentie"
    **Dag** gebruikt `energy-day-v2.json` uit `EM v2 | 70 History | Day Series v0.5`. Deze flow leest uitsluitend `EM2_State` en veroorzaakt **geen extra device-reads**. Naast vandaag bewaart v0.5 maximaal **6 afgesloten dagen op volledige 5-minutenresolutie** in `energy-day-series-7d.json`. Daarmee kan Dag maximaal zeven kalenderdagen tonen: vandaag plus de zes voorafgaande beschikbare dagen. **Week**, **Maand** en **Jaar** blijven de compacte records uit `energy-daily-history.json` gebruiken.

!!! warning "Tesla legacy-historie uitgesloten"
    De oude `tesla_kWh_est` uit Shadow Mode is een 15-minuten-schatting en wordt vanaf 18 augustus 2026 niet meer als feitelijk Tesla-verbruik weergegeven. Nieuwe Tesla-energie wordt opgebouwd uit `teslaW` in de Energy Core v2-dagreeks en over de werkelijke sample-timestamps geïntegreerd. Totdat een dag volledig via deze methode is gearchiveerd, toont de historische Tesla-waarde bewust `—` in plaats van een legacy-schatting.

!!! note "Rolling daghistorie vanaf 19 augustus"
    De full-resolution rolling archive is op 19 augustus 2026 ingevoerd. Oude 5-minutenreeksen worden niet fictief teruggevuld. De keuzelijst in **Dag** groeit daarom vanaf dit moment vanzelf aan tot maximaal vandaag + 6 afgesloten dagen. Compacte oudere dagaggregaties voor Week/Maand/Jaar blijven gewoon beschikbaar waar ze al aanwezig zijn.

!!! note "Rollover en herstel 18 augustus"
    Day Series v0.2 publiceerde de actuele dag wel, maar reset bij een kalenderwissel de lokale buffer zonder de afgesloten dag eerst naar `energy-daily-history.json` te archiveren. Daardoor ontbraken 17 en 18 augustus in Week/Maand/Jaar. Vanaf v0.3 is dit fail-safe gemaakt. V0.5 breidt die regel uit: **compact archive first, full-resolution archive second, reset last**. De vrijwel dagdekkende v2-snapshot van 18 augustus is eenmalig uit de immutable Git-historie gereconstrueerd voor de compacte daghistorie; 17 augustus blijft bewust onvolledig waar geen volledige bron beschikbaar is.

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

Vanaf twee echte tijdspunten worden kWh met trapeziumintegratie over de tijd berekend. Een interval wordt voor robuustheid gemaximeerd op tien minuten zodat een langere datagaping niet stilzwijgend als een volledig gemeten periode wordt meegerekend. Dezelfde methode wordt gebruikt voor de live dagweergave en de definitieve compacte dagarchive.

## Persistente dagketen

```text
EM2_State
   ↓ iedere 5 min, logic-only
EM2_Day_History (lopende dagbuffer)
   ↓ iedere 5 min
energy-day-v2.json  → Dag / vandaag
   ↓ kalenderwissel
finaliseer afgesloten dag
   ↓ 1. succesvolle compacte write
energy-daily-history.json → Week / Maand / Jaar
   ↓ 2. succesvolle full-resolution write
energy-day-series-7d.json → Dag / vorige 6 dagen
   ↓ pas daarna
nieuwe EM2_Day_History-buffer
```

De rolling full-resolution file bewaart alleen afgesloten dagen en de-dupliceert op datum. Een herhaalde rollover na een tijdelijke fout kan daardoor veilig opnieuw worden geprobeerd. De oudste dag valt automatisch weg zodra er meer dan zes afgesloten dagen aanwezig zijn.

Als één van de twee persistente archive-writes bij de dagwissel faalt, wordt de oude lokale buffer **niet** weggegooid. De flow stopt met een fout en probeert bij een volgende run opnieuw. Daarmee kan een tijdelijke GitHub- of netwerkfout niet stilzwijgend een volledige dag wissen.

## Dag kiezen

De Dag-interface gebruikt één en dezelfde grafiek- en kaartweergave voor vandaag en de bewaarde historische dagseries. De selector toont, afhankelijk van beschikbare data, **Vandaag**, **Gisteren** en de oudere kalenderdatums. De activiteitstijdlijn volgt dezelfde geselecteerde dag; hij blijft dus niet op vandaag staan wanneer een historische dag wordt gekozen.

Dit maakt ook analyse achteraf mogelijk van korte gebeurtenissen, zoals oven-, wasmachine- of drogercycli, zolang ze binnen de rolling 7-dagenperiode vallen en in de 5-minutenreeks zichtbaar zijn.

## Activiteitstijdlijn

De dagreeks bevat naast P1 en PV ook de reeds in `EM2_State` aanwezige status van Tesla, boiler, wasmachine en droger. De tijdlijn wordt daardoor uit dezelfde v2-dataset opgebouwd. Er is geen aparte legacy-baselinefeed meer nodig voor het Dagoverzicht.

## Homey-load

```text
EM v2 State (bestaande centrale read)
        ↓
EM2_State
        ↓ Logic-only, iedere 5 min
EM v2 | 70 History | Day Series v0.5
        ↓ lokale dagbuffer
GitHub live-publicatie iedere 5 min
        ↓
energy-day-v2.json
        ↓ alleen bij kalenderwissel
compacte archive + full-resolution rolling archive
```

De extra Homey-belasting blijft Logic-only; er wordt **geen extra `getDevices()`** uitgevoerd. Ten opzichte van v0.4 komt er alleen bij een kalenderwissel één extra GitHub read/write voor de full-resolution rolling archive bij. Week/Maand/Jaar veranderen architectonisch niet.

De interface bevat al **Accu geladen** en **Accu ontladen**. Totdat live Victron ESS-metingen beschikbaar zijn, blijven deze waarden bewust op 0 / nog geen opslagmeting; er wordt geen batterijdata geschat.

> Laatste update: **19 augustus 2026** — Day Series v0.5 bewaart naast vandaag maximaal zes afgesloten dagen op 5-minutenresolutie. Dag kan daarmee tot zeven kalenderdagen terugkijken zonder extra Homey-device-reads; Week/Maand/Jaar blijven op de compacte dagaggregaties draaien.
