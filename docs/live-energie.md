# Live energiestroom

Deze pagina maakt de energiearchitectuur **live zichtbaar**. De kaart gebruikt uitsluitend de revision-consistente publieke snapshot van **Energy Core v2**.

<div id="live-energy-flow">
  <p><em>Live energiestroom wordt geladen…</em></p>
</div>

!!! info "Energy Core v2 is leidend"
    De website leest uitsluitend `energy-state-v2.json`. Een websitebezoek veroorzaakt **geen Homey-call**. De actieve `EM v2 | 00 Core Tick | v0.9.7` maakt iedere vijf minuten één centrale device-/Logic-snapshot en gebruikt diezelfde snapshot voor State, Decision, Shadow, Warm Water en publicatie.

## Meetketen

```text
Homey devices + Logic
        ↓
EM v2 | 00 Core Tick | v0.9.7
        ↓
EM2_State (revision N)
        ↓
Decision + Shadow + Warm Water (revision N)
        ↓
EM2_CORE_PUBLISH_V0.9.7 · schema 2.5
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

Een negatieve P1-waarde betekent export; een positieve P1-waarde import. Rechtstreeks beschikbaar zijn P1, de drie PV-omvormers, Tesla/Easee, boiler en Quatt CIC.

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

`Overig` is nadrukkelijk het **residu na alle individueel bekende vermogens**:

```text
Overig = woningverbruik
       - TeslaW
       - boilerW
       - QuattW
       - wasmachineW
       - drogerW
       - vaatwasserW
       - QuookerW
       - overige toekomstige individueel gemeten loads
```

Alleen een werkelijk gepubliceerd wattage wordt afgetrokken. Een apparaatstatus zoals `RUNNING` zonder betrouwbaar `power_w` is onvoldoende om vermogen te verzinnen. De huidige wasmachine- en drogerintegraties leveren wel apparaatstatus maar geen rechtstreeks `measure_power`; hun `loads.*.power_w` is daarom voorlopig `null`. Zolang dat zo is, blijft hun energie fysiek onderdeel van `Overig`, maar de site kan bij actieve status expliciet aangeven dat een bekende actieve load nog niet watt-nauwkeurig is uitgesplitst.

Dit voorkomt twee fouten tegelijk: bekende gemeten loads worden niet dubbel in `Overig` geteld, en niet-gemeten loads worden niet met een fictieve schatting van het residu afgetrokken.

## Ruimteverwarming — hybride Quatt

Core v0.9.7 publiceert binnen schema 2.5 een first-class `quatt`-blok met onder meer:

- `power_w` — actueel elektrisch vermogen van Quatt;
- `thermal_power_w` — thermisch vermogen van beide warmtepompmodules samen;
- `cop_1` en `cop_2`;
- `working_mode_1` en `working_mode_2`;
- `thermostat_heating_on` — warmtevraag volgens de Quatt/CiC-keten;
- `cv_requested` — CiC vraagt CV-ondersteuning;
- `cv_flame` — fysieke branderstatus indien de Quatt-integratie die betrouwbaar levert;
- `role = COMFORT_BASELOAD`;
- `control_mode = OBSERVE_ONLY` en `controllable = false`;
- `ramp_reserve_w` — reserve die de Energy Manager vrijhoudt voor mogelijke Quatt-opregelruimte.

De website gebruikt deze velden conservatief. `cv_flame = null` betekent **onbekend** en wordt nooit als bewezen `CV uit` geïnterpreteerd. `cv_requested` toont dat ondersteuning gevraagd wordt, maar is op zichzelf geen bewijs dat de gasbrander daadwerkelijk brandt.

Mogelijke functionele statussen zijn onder meer `Quatt verwarmt`, `Quatt + CV · hybride`, `CV ondersteuning gevraagd`, `CV verwarmt`, `warmtevraag` en `geen warmtevraag`.

De CV-ketel blijft een **status binnen Ruimteverwarming** en wordt niet als elektrische stroom getekend. Gas wordt dus bewust niet als elektrische pijl in het energiediagram opgenomen.

De Energiemanager-balk toont Tesla, Boiler en Ruimteverwarming als functionele onderdelen. `Overig` blijft een meet-/restcategorie en wordt daarom niet als stuurbare Energiemanager-functie gepresenteerd.

## Energy budget en Quatt-reserve

Core v0.9.7 behandelt Quatt als observe-only comfortload. Het actuele Quatt-verbruik zit al in de P1/woningbalans en wordt niet nogmaals van export afgetrokken. Voor flexibele lasten wordt alleen een aparte Quatt-rampreserve meegenomen. De publieke snapshot bevat daarvoor `energy_budget`, waaronder `flex_export_budget_w`, `discretionary_import_budget_w` en `quatt_ramp_reserve_w`.

Dit beïnvloedt de besluitvorming voor flexibele lasten, maar geeft Homey **geen** recht om de Quatt aan of uit te zetten.

## Actualiteit en Homey-load

De Quatt-uitbreiding gebruikt **dezelfde bestaande `Homey.devices.getDevices()` snapshot** van de centrale Core. Er is geen tweede Quatt-poll, geen extra periodieke flow en geen browser→Homey-route toegevoegd.

| Laag | Actieve versie | Functie |
|---|---|---|
| Core | `EM v2 | 00 Core Tick | v0.9.7` | één centrale device- en Logic-snapshot per 5 minuten; State/Decision/Shadow/WW/publicatie |
| Publieke state | schema `2.5` / `EM2_CORE_PUBLISH_V0.9.7` | revision-consistente snapshot met first-class `quatt`, `loads` en `energy_budget` |
| Website | `live-energy-v2.8.40.js` + `live-energy-known-loads-v2.8.41.js` | vier parallelle verbruikstakken; `Overig` als residu na alle beschikbare individuele wattages |

De live kaart toont revision en bron-timestamp expliciet. De status `actueel/vertraagd` komt uit dezelfde freshness-regels als de EM v2 health-indicator.

Later kan dezelfde kaart zonder architectuurwijziging worden uitgebreid met live Victron ESS-waarden voor batterij laden/ontladen, SOC en eilandbedrijf.

> Laatste update: **18 augustus 2026** — `Overig` is gecorrigeerd naar residu na alle betrouwbare individueel gepubliceerde vermogens. Wasmachine/droger worden pas numeriek afgetrokken zodra voor hen betrouwbaar actueel wattage beschikbaar is; actieve status zonder wattage leidt niet tot een fictieve aftrek.
