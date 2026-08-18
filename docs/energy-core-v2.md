# Energy Core v2 — greenfield architectuur

## Status

**Implementatiefase:** centrale single-reader Core Tick actief in read-only SHADOW.  
**Actieve kern:** `EM v2 | 00 Core Tick | v0.9.6`.  
**Contextlaag:** `EM v2 | 30 Context | Price + PV v0.1`.  
**Fysieke v2-writes:** geen.

Energy Core v2 gebruikt één centrale fysieke snapshot per vijf minuten. State, Decision, Shadow, warmwater-state, warmwater-Control en publicatie worden atomair uit dezelfde sample en revision berekend. Prijs- en PV-forecastcontext wordt apart iedere 15 minuten bijgewerkt zonder extra device-scan.

## Harde architectuurregels

1. Per Core Tick maximaal één `getDevices()` en één `getVariables()`.
2. Downstream-berekeningen gebruiken dezelfde in-memory snapshot.
3. Websitebezoek veroorzaakt nul Homey-calls; de site leest gepubliceerde snapshots.
4. State, Decision, Shadow en Control-intent horen bij dezelfde State-revision.
5. Verouderde prijs/PV-context wordt niet als actuele waarheid gebruikt.
6. Per fysieke actuator bestaat uiteindelijk exact één automatische writer.
7. Een v2-Control-adapter krijgt pas fysieke writes na voldoende shadowvalidatie.

## Actuele keten

```text
Prijs + PV forecast cards
        │ iedere 15 min, geen device-scan
        ▼
EM v2 | 30 Context | Price + PV v0.1

Devices / meters / Easee / Quatt + Homey Logic
        │ iedere 5 min
        ▼
EM v2 | 00 Core Tick | v0.9.6
        ├── State → EM2_State · revision N
        ├── Decision → EM2_Decision · sourceRevision N
        ├── Shadow → EM2_Shadow · sourceRevision N
        ├── Warm Water State → EM2_WW_State · sourceRevision N
        ├── Warm Water Control → EM2_Control_WW · sourceRevision N
        │                         GEEN fysieke write
        └── Publish → energy-state-v2.json · schema 2.4

Parallel, zonder device-read:
EM v2 | 70 History | Day Series → energy-day-v2.json
```

## Ruimteverwarming vanaf v0.9.6

Quatt CIC is toegevoegd aan **dezelfde bestaande `getDevices()` snapshot**. Er is dus geen tweede Quatt-read of nieuwe periodieke poll. De Core publiceert in schema 2.4 een apart `heating`-blok:

```text
heating.quatt_power_w
heating.thermal_power_w
heating.cop_1
heating.cop_2
heating.working_mode_1
heating.working_mode_2
heating.thermostat_heating_on
heating.cv_requested
heating.cv_onoff_command
heating.cv_flame
```

`quatt_power_w` is het elektrische Quatt-verbruik en kan daardoor rechtstreeks als aparte woningverbruiker worden verwerkt. `thermal_power_w` en COP zijn diagnostische/thermische waarden en worden niet opgeteld bij de elektrische energiebalans.

De CV-status blijft bewust tri-state waar de bron dat vereist. `cv_flame = null` betekent **onbekend** en mag niet als `false` worden geïnterpreteerd. `cv_requested` en `cv_onoff_command` geven een verzoek/aansturing voor ketelondersteuning weer, maar zijn op zichzelf geen bewijs dat de fysieke brander actief is.

## Warmwaterstate v0.8

Warmwatercontext staat in `EM2_WW_State` (`EM2_WW_STATE_V0.8`). Het primaire dagdoel is `OP_TEMPERATUUR_ONCE_PER_DAY`. Zodra dit doel op een lokale kalenderdag is bereikt, blijft `goalReachedToday=true`; later warmwatergebruik opent het doel niet opnieuw (`sameDayReheat=false`).

Thermostaatdetectie:

```text
boiler aan + vermogen > 1500 W gedurende 15 min
    → opwarmen bevestigd

daarna boiler nog aan + vermogen < 100 W gedurende 10 min
    → OP_TEMPERATUUR bereikt
```

### Warmwatervraag is tijdsonafhankelijk

De regeling mag niet impliciet aannemen dat warmwatervraag alleen in de ochtend plaatsvindt. Warmwatergebruik kan op ieder moment van de dag optreden en wordt daarom als aparte gebeurtenis/context gezien, niet automatisch als nieuwe verwarmingsopdracht.

Voor het bereiken van het dagdoel moet na iedere relevante warmwatervraag opnieuw worden beoordeeld of er nog veilig kan worden gewacht op PV/prijs-opportunity of dat catch-up dichterbij komt. Na `goalReachedToday=true` mag latere warmwatervraag dezelfde dag geen nieuwe verplichte opwarmcyclus openen zolang `sameDayReheat=false` geldt.

Deze scenario's zijn expliciet onderdeel van de acceptatie vóór promotie van WW Control naar HYBRID:

- warmwatervraag in de ochtend vóór een opportunity;
- warmwatervraag rond middag/namiddag terwijl het dagdoel nog niet is bereikt;
- warmwatervraag kort vóór de catch-up/deadlinezone;
- warmwatervraag nadat `OP_TEMPERATUUR` die dag al is bereikt;
- meerdere warmwatervraagmomenten op dezelfde dag.

Promotie naar fysieke WW-Control is niet toegestaan zolang deze scenario's niet logisch en fail-safe in SHADOW zijn beoordeeld.

### Fallback-accounting vanaf v0.9.5

De 240-minutenfallback telt niet langer relais-aan-tijd. `boilerOnMinToday` blijft uitsluitend als diagnostische teller bestaan. De fallback gebruikt nu `heatingMinToday`: alleen intervallen waarin het boilerrelais AAN staat én het gemeten boilervermogen >1500 W is, tellen als bevestigde verwarmingsminuten.

```text
heatingNow = boilerOn && boilerPowerW > 1500 W
heatingMinToday += deltaMin alleen wanneer heatingNow
remainingFallbackMin = max(0, 240 - heatingMinToday)
```

Als `OP_TEMPERATUUR` al bereikt is, wordt `remainingFallbackMin` direct 0. De state publiceert expliciet `fallbackAccounting = CONFIRMED_HEATING_MINUTES` en `fallbackHeatingThresholdW = 1500`.

Bij migratie vanaf v0.9.4 kon de reeds verstreken verwarmingsduur van die dag niet betrouwbaar achteraf worden gereconstrueerd. Daarom startte `heatingMinToday` conservatief vanaf de v0.9.5-cut-over en bleef `heatingAccountingQuality = PARTIAL_FROM_V0.9.5_START` voor die dag zichtbaar. Dit beïnvloedt een reeds gelatcht dagdoel niet.

## Warmwater Control v0.10 — PURE SHADOW

Warm Water Control wordt atomair binnen Core Tick v0.9.6 berekend als `EM2_CONTROL_WW_V0.10`. Alle `BOILER_ON`- en `BOILER_OFF`-uitkomsten zijn nog uitsluitend Shadow-intenties; `readOnly=true`, `deviceWrites=false` en `physicalWritePerformed=false`.

### Start- en run-lockbeleid

| Situatie / startreden | Startvoorwaarde | Run-lock |
|---|---|---:|
| `CATCHUP` | deadline/fallback maakt uitstel onverantwoord | 0 min opportunity-lock |
| `EXPORT` | ≥2100 W actuele netexport | 15 min |
| `PV_FORECAST` | top-4 PV-forecastuur én ≥500 W actuele export | 15 min |
| `PRICE_NEGATIVE` | negatieve prijs én ≥30 min resterend in huidig tariefuur | 30 min |
| `PRICE_CHEAP` | huidige prijs goedkoper dan komende 4 uur én ≥30 min resterend in huidig tariefuur | 30 min |

Na afloop van een PV/prijs-run-lock mag opnieuw worden geoptimaliseerd. Bij geen geldige opportunity en meer dan circa 500 W netimport of een duidelijk ongunstige prijs kan `BOILER_OFF / SHOULD` volgen. Catch-up blijft comfort/deadline-gedreven.

De gewenste dagelijkse lijn is generiek en niet aan ochtendgebruik gebonden:

```text
warmwatervraag op enig moment vóór dagdoel
    → niet automatisch herverwarmen
    → opnieuw opportunity versus resterende tijd/catch-up beoordelen
    → start alleen wanneer opportunity of catch-up dat rechtvaardigt
    → run-lock passend bij de startreden
    → indien nodig catch-up richting 19:00 op basis van bevestigde verwarmingsminuten
    → OP_TEMPERATUUR eenmaal bereikt
    → dagdoel gelatcht; latere warmwatervraag opent geen verplichte heropwarming dezelfde dag
```

## Validatie cut-over 18 augustus 2026

De oorspronkelijke veilige cut-over activeerde v0.9.5 met confirmed-heating fallback. Daarna is v0.9.6 als beperkte state/publicatie-uitbreiding ingevoerd: v0.9.5 is uitgeschakeld, v0.9.6 actief gemaakt en handmatig eenmaal gestart.

De eerste v0.9.6-publicatie valideerde:

- `publisher_version = EM2_CORE_PUBLISH_V0.9.6`;
- `schema_version = 2.4`;
- gelijke State/Decision/Shadow-revisions;
- een nieuw `heating`-blok met actuele Quatt CIC-data;
- behoud van `control_mode = SHADOW`;
- WW State `EM2_WW_STATE_V0.8`;
- WW Control `EM2_CONTROL_WW_V0.10`;
- `readOnly = true`, `deviceWrites = false`, `physicalWritePerformed = false`.

De Quatt-uitbreiding verandert geen Decision- of fysieke Control-logica. Zij maakt bestaande Quatt-data alleen onderdeel van de centrale state en publicatie.

## Publisher en load-budget

```text
schema_version    = 2.4
publisher_version = EM2_CORE_PUBLISH_V0.9.6
control_mode      = SHADOW
```

Operationeel budget:

- 1 × `getDevices()` per 5 minuten in Core Tick, inclusief Quatt CIC;
- 1 × `getVariables()` per 5 minuten in Core Tick;
- State, Decision, Shadow, WW State en WW Control daarna in-memory;
- context iedere 15 minuten zonder device-scan;
- GitHub-write maximaal iedere 10 minuten bij relevante wijzigingen;
- 30-minuten-heartbeat;
- website: nul Homey-calls.

## Control modes

| Mode | Betekenis |
|---|---|
| `SHADOW` | **huidige mode**: v2 observeert en berekent control-intent, geen v2 device-writes |
| `HYBRID` | alleen expliciet gevalideerde actuators mogen door v2 worden gestuurd |
| `ACTIVE` | v2 is leidend voor alle gemigreerde flexloads |

De eerdere fallback-accounting op relais-aan-tijd is met v0.9.5 opgelost als blocker. Voor promotie van WW naar fysieke Control moeten zowel een volledige dagcyclus met confirmed-heating-accounting als de hierboven beschreven tijdsonafhankelijke warmwatervraagscenario's voldoende zijn gevalideerd.

> Laatste update: **18 augustus 2026 — Core Tick v0.9.6.** Quatt CIC is toegevoegd aan dezelfde single-reader snapshot en wordt via schema 2.4 als `heating` gepubliceerd. Geen extra periodieke device-read en geen nieuwe fysieke writes.
