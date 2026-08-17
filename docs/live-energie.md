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

Een negatieve P1-waarde betekent export; een positieve P1-waarde import. Rechtstreeks beschikbaar zijn P1, de drie PV-omvormers, Tesla/Easee en boiler. Wasmachine en droger leveren momenteel status maar geen afzonderlijk live wattage; hun vermogen wordt daarom niet geschat.

**Overig verbruik** is:

```text
Overig = woningverbruik - TeslaW - boilerW
```

## Grootverbruikers

- **Tesla / Easee** — werkelijk gemeten laadvermogen en gevraagde laadstroom;
- **Boiler** — werkelijk vermogen en aan/uit-status;
- **Wasmachine — L2, groep 1, aardlek 1** — Homey-status, geen individueel wattage;
- **Droger — L3, groep 2, aardlek 1** — Homey-status, geen individueel wattage;
- **Overig huishouden** — resterend woningverbruik.

## Actualiteit en Homey-load

De live pagina hergebruikt de sitebrede Energy Core v2-adapter. De browser leest dus hetzelfde `energy-state-v2.json` als de health-indicator en doet geen afzonderlijke Homey- of legacy-live-data-aanroep.

De actieve kern is:

| Laag | Actieve versie | Functie |
|---|---|---|
| State | `EM v2 | 10 State | Collector v0.3` | één centrale read-only device-snapshot per 5 minuten |
| Decision + Shadow | `EM v2 | 20 Decision + 80 Shadow | v0.2` | uitsluitend Logic/state; geen device-read |
| Publish | `EM v2 | 90 Publish | State Publisher v0.2` | publiceert alleen revision-consistente snapshots |

De live kaart toont de gebruikte revision en bron-timestamp expliciet. De status `actueel/vertraagd` komt uit dezelfde freshness-regels als de EM v2 health-indicator.

Later kan dezelfde kaart zonder architectuurwijziging worden uitgebreid met live Victron ESS-waarden voor batterij laden/ontladen, SOC en eilandbedrijf.

> Laatste update: **17 augustus 2026** — Live energiestroom gemigreerd van de legacy `pv-phase-24h.json`/`energy-live.json` route naar de revision-consistente Energy Core v2-state.
