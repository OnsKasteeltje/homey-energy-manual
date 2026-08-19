# Energiehistorie

<div id="energy-history-dashboard">
  <p><em>Energiehistorie wordt geladen…</em></p>
</div>

!!! info "Energy Core v2 is leidend voor Dag én persistentie"
    **Dag** gebruikt `energy-day-v2.json` uit `EM v2 | 70 History | Day Series v0.5.2`. Deze flow leest uitsluitend `EM2_State` en veroorzaakt **geen extra device-reads**. Naast vandaag bewaart v0.5.2 maximaal **6 afgesloten dagen op volledige 5-minutenresolutie** in `energy-day-series-7d.json`. Daarmee kan Dag maximaal zeven kalenderdagen tonen: vandaag plus de zes voorafgaande beschikbare dagen. **Week**, **Maand** en **Jaar** blijven de compacte records uit `energy-daily-history.json` gebruiken.

!!! note "Schema-hardening v0.5.2"
    History blokkeert niet meer op één exact Core-schema zoals `ENERGY_STATE_V2.3`. V0.5.2 accepteert compatibele `ENERGY_STATE_V2.x`-states en valideert daarnaast de daadwerkelijk benodigde velden en numerieke waarden. Een kleine Core-schema-bump hoeft daardoor de historieketen niet meer stil te leggen; incompatibele of ongeldige input blijft wel fail-safe geweigerd.

!!! warning "Tesla legacy-historie uitgesloten"
    De oude `tesla_kWh_est` uit Shadow Mode is een 15-minuten-schatting en wordt vanaf 18 augustus 2026 niet meer als feitelijk Tesla-verbruik weergegeven. Nieuwe Tesla-energie wordt opgebouwd uit `teslaW` in de Energy Core v2-dagreeks en over de werkelijke sample-timestamps geïntegreerd. Totdat een dag volledig via deze methode is gearchiveerd, toont de historische Tesla-waarde bewust `—` in plaats van een legacy-schatting.

!!! note "Rolling daghistorie vanaf 19 augustus"
    De full-resolution rolling archive is op 19 augustus 2026 ingevoerd. Oude 5-minutenreeksen worden niet fictief teruggevuld. De keuzelijst in **Dag** groeit daarom vanaf dit moment vanzelf aan tot maximaal vandaag + 6 afgesloten dagen. Compacte oudere dagaggregaties voor Week/Maand/Jaar blijven gewoon beschikbaar waar ze al aanwezig zijn.

## Berekeningsprincipes

```text
PV-productie = SolarEdge + GoodWe GW4200D-NS + GoodWe GW2000-XS
Woningverbruik = PV-productie + P1-netvermogen
Netimport = max(P1, 0)
Netexport = max(-P1, 0)
Direct eigen PV-verbruik = max(PV - netexport, 0)
Tesla-energie = integraal(teslaW × werkelijke sampletijd)
```

De history-flow draait iedere vijf minuten. Hij doet geen eigen meting van apparaten, maar leest de centrale `EM2_State`. Wanneer die state door de deadband niet is vernieuwd, wordt de laatst bekende toestand als **hold-last-value** gebruikt en krijgt het historypunt `held=true`. Vanaf twee echte tijdspunten worden kWh met trapeziumintegratie berekend; intervallen worden voor robuustheid gemaximeerd op tien minuten.

## Persistente dagketen

```text
EM2_State
   ↓ iedere 5 min, logic-only
EM2_Day_History (lopende dagbuffer)
   ↓
energy-day-v2.json → Dag / vandaag
   ↓ kalenderwissel
1. compacte dagarchive → energy-daily-history.json
2. full-resolution archive → energy-day-series-7d.json
3. pas na beide succesvolle writes: reset dagbuffer
```

De rolling file bewaart maximaal zes afgesloten dagen en de-dupliceert op datum. Als één archive-write faalt, wordt de oude lokale buffer niet weggegooid en kan de rollover veilig opnieuw worden geprobeerd.

## Freshness en health

De history-publicatie bevat healthinformatie over het bron-schema, de leeftijd van de bronstate, het laatste historiesample en eventuele `held`-status. De interface gebruikt één freshnessmodel:

- **< 15 minuten:** actueel;
- **15–30 minuten:** vertraagd / waarschuwing;
- **> 30 minuten:** data verouderd / foutstatus.

Hierdoor is zichtbaar of een oud tijdstip echte publicatievertraging is en niet alleen een oude schermweergave.

## Dag kiezen

De Dag-interface gebruikt dezelfde grafiek- en kaartweergave voor vandaag en bewaarde historische dagseries. De selector toont afhankelijk van beschikbare data **Vandaag**, **Gisteren** en oudere kalenderdatums. De activiteitstijdlijn volgt dezelfde geselecteerde dag. Dit ondersteunt ook analyse achteraf van korte gebeurtenissen zoals oven-, wasmachine- en drogercycli binnen de rolling periode.

## Homey-load

```text
Energy Core v2 centrale device-read
        ↓
EM2_State
        ↓ logic-only
Day Series v0.5.2 iedere 5 min
        ↓
GitHub feeds / rolling archive
```

Er wordt **geen extra `getDevices()`** uitgevoerd. De rolling historie en freshnessinformatie verhogen dus niet de Homey-devicepolling. Week/Maand/Jaar blijven architectonisch ongewijzigd.

## Open acceptatiecontrole

Na invoering van de rolling historie resteert één productiecontrole: bij de eerste kalenderrollover moet de Dag-selector automatisch **Vandaag + Gisteren** tonen, waarbij Gisteren de volledige beschikbare 5-minutenreeks bevat. Tegelijk moeten Week/Maand/Jaar ongewijzigd correct blijven.

> Laatste update: **19 augustus 2026** — Day Series **v0.5.2**: rolling 7-daagse 5-minutenhistorie, compatibele `ENERGY_STATE_V2.x`-validatie, expliciete freshness/health en fail-safe rollover zonder extra Homey-device-reads.
