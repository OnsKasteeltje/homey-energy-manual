# Live energiestroom

Deze pagina maakt de energiearchitectuur **live zichtbaar**. De kaart gebruikt uitsluitend de revision-consistente publieke snapshot van **Energy Core v2**.

<div id="live-energy-flow">
  <p><em>Live energiestroom wordt geladen…</em></p>
</div>

!!! info "Energy Core v2 is leidend"
    De website leest `energy-state-v2.json`. Een websitebezoek veroorzaakt **geen Homey-call**. `EM v2 | 10 State | Collector v0.3` verzamelt de bronwaarden; Decision/Shadow en Publisher gebruiken daarna dezelfde revision.

## Meetketen

```text
Homey devices + Logic
        ↓
EM v2 | 10 State | Collector v0.3
        ↓
EM2_State (revision N)
        ↓
EM v2 | 20 Decision + 80 Shadow | v0.2
        ↓
EM2_Decision / EM2_Shadow (revision N)
        ↓
EM v2 | 90 Publish | State Publisher v0.2
        ↓
docs/data/energy-state-v2.json
        ↓
website
```

Publisher v0.2 publiceert alleen wanneer State, Decision en Shadow dezelfde revision hebben. Daardoor kan de live kaart geen nieuwe fysieke meting combineren met een oudere beslissing.

## Gemeten versus afgeleid

De energiebalans is:

```text
woningverbruik = PV-productie + netimport - netexport ± batterij
```

Een negatieve P1-waarde betekent export; een positieve P1-waarde import. Rechtstreeks beschikbaar zijn P1, de drie PV-omvormers, Tesla/Easee en boiler.

De woning splitst op de live kaart in **vier parallelle verbruikstakken**:

```text
Huis
 ├─ Tesla
 ├─ Boiler
 ├─ Ruimteverwarming
 └─ Overig
```

Er bestaan **geen onderlinge energiestromen** tussen deze vier categorieën. Iedere pijl loopt rechtstreeks van de woning naar de betreffende verbruikstak.

### Overig verbruik

Zolang Quatt-vermogen nog niet in de Energy Core v2-snapshot aanwezig is, blijft:

```text
Overig = woningverbruik - TeslaW - boilerW
```

Ruimteverwarming wordt in dat geval als afzonderlijke functionele categorie getoond met vermogen/status `onbekend`. De website trekt geen geschat Quatt-vermogen van Overig af en verzint geen warmtepompdata.

Zodra een toekomstige v2-snapshot betrouwbaar `space_heating`/`heating` met Quatt-vermogen bevat, kan de bestaande renderer automatisch rekenen met:

```text
Overig = woningverbruik - TeslaW - boilerW - QuattW
```

## Ruimteverwarming — hybride Quatt

De tegel **Ruimteverwarming** vertegenwoordigt het hybride verwarmingssysteem als één functionele verbruiker:

- **Quatt** is de elektrische verwarmingsbron en kan later met werkelijk elektrisch vermogen worden getoond;
- **CV-ketel** is ondersteunende/alternatieve warmtebron en wordt als status weergegeven, niet als elektrische energiestroom;
- mogelijke toestanden zijn onder meer `Quatt verwarmt`, `hybride (Quatt + CV)`, `CV verwarmt`, `geen warmtevraag` en `status onbekend`;
- gas wordt bewust niet als elektrische pijl in het energiediagram getekend.

De Energiemanager-balk toont Tesla, Boiler en Ruimteverwarming als functionele onderdelen. `Overig` blijft een meet-/restcategorie en wordt daarom niet als stuurbare Energiemanager-functie gepresenteerd.

## Grootverbruikers

- **Tesla / Easee** — werkelijk gemeten laadvermogen en gevraagde laadstroom;
- **Boiler** — werkelijk vermogen en aan/uit-status;
- **Ruimteverwarming** — Quatt/CV-functionele status; elektrisch Quatt-vermogen alleen zodra betrouwbaar gepubliceerd;
- **Overig huishouden** — resterend woningverbruik.

Wasmachine en droger blijven beschikbaar in de achterliggende Homey-context/groepenindeling, maar zijn in de hoofd-liveflow geen aparte energietakken zolang er geen betrouwbaar individueel live wattage beschikbaar is.

## Actualiteit en Homey-load

De live pagina hergebruikt de sitebrede Energy Core v2-adapter. De browser leest dus hetzelfde `energy-state-v2.json` als de health-indicator en doet geen afzonderlijke Homey- of legacy-live-data-aanroep.

De actuele Quatt/CV-uitbreiding is **uitsluitend websitepresentatie**. Er zijn geen extra Homey-device-reads, flows, pollingcycli of publicatieroutes toegevoegd.

De actieve kern is:

| Laag | Actieve versie | Functie |
|---|---|---|
| State | `EM v2 | 10 State | Collector v0.3` | één centrale read-only device-snapshot per 5 minuten |
| Decision + Shadow | `EM v2 | 20 Decision + 80 Shadow | v0.2` | uitsluitend Logic/state; geen device-read |
| Publish | `EM v2 | 90 Publish | State Publisher v0.2` | publiceert alleen revision-consistente snapshots |

De live kaart toont de gebruikte revision en bron-timestamp expliciet. De status `actueel/vertraagd` komt uit dezelfde freshness-regels als de EM v2 health-indicator.

Later kan dezelfde kaart zonder architectuurwijziging worden uitgebreid met live Victron ESS-waarden voor batterij laden/ontladen, SOC en eilandbedrijf.

> Laatste update: **18 augustus 2026** — Live energiestroom toont Tesla, Boiler, Ruimteverwarming en Overig als vier onafhankelijke parallelle verbruikstakken. Hybride Quatt/CV-presentatie toegevoegd zonder extra Homey-load.
