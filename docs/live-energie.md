# Live energiestroom

Deze pagina maakt de energiearchitectuur **live zichtbaar**. De kaart gebruikt uitsluitend de revision-consistente publieke snapshot van **Energy Core v2**.

<div id="live-energy-flow">
  <p><em>Live energiestroom wordt geladen…</em></p>
</div>

!!! info "Energy Core v2 is leidend"
    De website leest uitsluitend `energy-state-v2.json`. Een websitebezoek veroorzaakt **geen Homey-call**. De actieve `EM v2 | 00 Core Tick | v0.9.6` maakt iedere vijf minuten één centrale device-/Logic-snapshot en gebruikt diezelfde snapshot voor State, Decision, Shadow, Warm Water en publicatie.

## Meetketen

```text
Homey devices + Logic
        ↓
EM v2 | 00 Core Tick | v0.9.6
        ↓
EM2_State (revision N)
        ↓
Decision + Shadow + Warm Water (revision N)
        ↓
EM2_CORE_PUBLISH_V0.9.6 · schema 2.4
        ↓
docs/data/energy-state-v2.json
        ↓
website
```

De publicatie blijft revision-consistent: State, Decision en Shadow gebruiken dezelfde revision en dezelfde fysieke bron-sample.

## Gemeten versus afgeleid

De energiebalans is:

```text
woningverbruik = PV-productie + netimport - netexport ± batterij
```

Een negatieve P1-waarde betekent export; een positieve P1-waarde import. Rechtstreeks beschikbaar zijn P1, de drie PV-omvormers, Tesla/Easee, boiler en sinds Core v0.9.6 ook de Quatt CIC-gegevens.

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

Wanneer Quatt-vermogen in de snapshot numeriek beschikbaar is, geldt:

```text
Overig = woningverbruik - TeslaW - boilerW - QuattW
```

Het Quatt-vermogen komt rechtstreeks uit `heating.quatt_power_w`. Ook een klein standby-verbruik blijft daarmee onderdeel van de aparte tak Ruimteverwarming en wordt niet dubbel in Overig geteld.

## Ruimteverwarming — hybride Quatt

Core v0.9.6 publiceert binnen schema 2.4 een apart `heating`-blok met onder meer:

- `quatt_power_w` — actueel elektrisch vermogen van Quatt;
- `thermal_power_w` — thermisch vermogen van beide warmtepompmodules samen;
- `cop_1` en `cop_2`;
- `working_mode_1` en `working_mode_2`;
- `thermostat_heating_on` — warmtevraag volgens de Quatt/CiC-keten;
- `cv_requested` — CiC vraagt CV-ondersteuning;
- `cv_onoff_command` — ketel-aansturing vanuit CiC;
- `cv_flame` — fysieke branderstatus indien de Quatt-integratie die betrouwbaar levert.

De website gebruikt deze velden conservatief. `cv_flame = null` betekent **onbekend** en wordt nooit als bewezen `CV uit` geïnterpreteerd. `cv_requested` en `cv_onoff_command` tonen dat ondersteuning gevraagd/aangestuurd wordt, maar zijn op zichzelf geen bewijs dat de gasbrander daadwerkelijk brandt.

Mogelijke functionele statussen zijn onder meer `Quatt verwarmt`, `Quatt + CV · hybride`, `CV ondersteuning gevraagd`, `CV verwarmt`, `warmtevraag` en `geen warmtevraag`.

De CV-ketel blijft een **status binnen Ruimteverwarming** en wordt niet als elektrische stroom getekend. Gas wordt dus bewust niet als elektrische pijl in het energiediagram opgenomen.

De Energiemanager-balk toont Tesla, Boiler en Ruimteverwarming als functionele onderdelen. `Overig` blijft een meet-/restcategorie en wordt daarom niet als stuurbare Energiemanager-functie gepresenteerd.

## Actualiteit en Homey-load

De Quatt-uitbreiding gebruikt **dezelfde bestaande `Homey.devices.getDevices()` snapshot** van de centrale Core. Er is geen tweede Quatt-poll, geen extra periodieke flow en geen browser→Homey-route toegevoegd.

| Laag | Actieve versie | Functie |
|---|---|---|
| Core | `EM v2 | 00 Core Tick | v0.9.6` | één centrale device- en Logic-snapshot per 5 minuten; State/Decision/Shadow/WW/publicatie |
| Publieke state | schema `2.4` / `EM2_CORE_PUBLISH_V0.9.6` | revision-consistente snapshot inclusief `heating` |
| Website | `live-energy-v2.8.39.js` | vier parallelle verbruikstakken en hybride Quatt/CV-presentatie |

De live kaart toont revision en bron-timestamp expliciet. De status `actueel/vertraagd` komt uit dezelfde freshness-regels als de EM v2 health-indicator.

Later kan dezelfde kaart zonder architectuurwijziging worden uitgebreid met live Victron ESS-waarden voor batterij laden/ontladen, SOC en eilandbedrijf.

> Laatste update: **18 augustus 2026** — Quatt/CV-data opgenomen in de centrale Energy Core v0.9.6-snapshot en gekoppeld aan de Live energiestroom, zonder extra periodieke Homey-read.
