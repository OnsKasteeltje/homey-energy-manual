# Energy Core v2 — greenfield architectuur

## Status

**Implementatiefase:** centrale single-reader Core Tick actief in read-only SHADOW.  
**Actieve kern:** `EM v2 | 00 Core Tick | v0.9.5`.  
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

Devices / meters / Easee + Homey Logic
        │ iedere 5 min
        ▼
EM v2 | 00 Core Tick | v0.9.5
        ├── State → EM2_State · revision N
        ├── Decision → EM2_Decision · sourceRevision N
        ├── Shadow → EM2_Shadow · sourceRevision N
        ├── Warm Water State → EM2_WW_State · sourceRevision N
        ├── Warm Water Control → EM2_Control_WW · sourceRevision N
        │                         GEEN fysieke write
        └── Publish → energy-state-v2.json

Parallel, zonder device-read:
EM v2 | 70 History | Day Series → energy-day-v2.json
```

## Warmwaterstate v0.8

Warmwatercontext staat in `EM2_WW_State` (`EM2_WW_STATE_V0.8`). Het primaire dagdoel is `OP_TEMPERATUUR_ONCE_PER_DAY`. Zodra dit doel op een lokale kalenderdag is bereikt, blijft `goalReachedToday=true`; later warmwatergebruik opent het doel niet opnieuw (`sameDayReheat=false`).

Thermostaatdetectie:

```text
boiler aan + vermogen > 1500 W gedurende 15 min
    → opwarmen bevestigd

daarna boiler nog aan + vermogen < 100 W gedurende 10 min
    → OP_TEMPERATUUR bereikt
```

### Fallback-accounting vanaf v0.9.5

De 240-minutenfallback telt niet langer relais-aan-tijd. `boilerOnMinToday` blijft uitsluitend als diagnostische teller bestaan. De fallback gebruikt nu `heatingMinToday`: alleen intervallen waarin het boilerrelais AAN staat én het gemeten boilervermogen >1500 W is, tellen als bevestigde verwarmingsminuten.

```text
heatingNow = boilerOn && boilerPowerW > 1500 W
heatingMinToday += deltaMin alleen wanneer heatingNow
remainingFallbackMin = max(0, 240 - heatingMinToday)
```

Als `OP_TEMPERATUUR` al bereikt is, wordt `remainingFallbackMin` direct 0. De state publiceert expliciet `fallbackAccounting = CONFIRMED_HEATING_MINUTES` en `fallbackHeatingThresholdW = 1500`.

Bij migratie vanaf v0.9.4 kan de reeds verstreken verwarmingsduur van die dag niet betrouwbaar achteraf worden gereconstrueerd. Daarom start `heatingMinToday` conservatief vanaf de v0.9.5-cut-over en wordt `heatingAccountingQuality = PARTIAL_FROM_V0.9.5_START` gepubliceerd. Dit beïnvloedt een reeds gelatcht dagdoel niet.

## Warmwater Control v0.10 — PURE SHADOW

Warm Water Control wordt atomair binnen Core Tick v0.9.5 berekend als `EM2_CONTROL_WW_V0.10`. Alle `BOILER_ON`- en `BOILER_OFF`-uitkomsten zijn nog uitsluitend Shadow-intenties; `readOnly=true`, `deviceWrites=false` en `physicalWritePerformed=false`.

### Start- en run-lockbeleid

| Situatie / startreden | Startvoorwaarde | Run-lock |
|---|---|---:|
| `CATCHUP` | deadline/fallback maakt uitstel onverantwoord | 0 min opportunity-lock |
| `EXPORT` | ≥2100 W actuele netexport | 15 min |
| `PV_FORECAST` | top-4 PV-forecastuur én ≥500 W actuele export | 15 min |
| `PRICE_NEGATIVE` | negatieve prijs én ≥30 min resterend in huidig tariefuur | 30 min |
| `PRICE_CHEAP` | huidige prijs goedkoper dan komende 4 uur én ≥30 min resterend in huidig tariefuur | 30 min |

Na afloop van een PV/prijs-run-lock mag opnieuw worden geoptimaliseerd. Bij geen geldige opportunity en meer dan circa 500 W netimport of een duidelijk ongunstige prijs kan `BOILER_OFF / SHOULD` volgen. Catch-up blijft comfort/deadline-gedreven.

De gewenste dagelijkse lijn is:

```text
ochtend warmwatergebruik
    → niet onmiddellijk herverwarmen
    → wachten op actuele PV-export, gunstige prijs of PV-forecastmoment
    → start alleen wanneer opportunity en prijshorizon passen
    → run-lock passend bij de startreden
    → indien nodig catch-up richting 19:00 op basis van bevestigde verwarmingsminuten
    → OP_TEMPERATUUR eenmaal bereikt
    → dagdoel gelatcht; geen heropwarming dezelfde dag
```

## Validatie cut-over 18 augustus 2026

De veilige cut-over heeft v0.9.4 eerst uitgeschakeld en daarna v0.9.5 geactiveerd. De eerste handmatige v0.9.5-run publiceerde schema 2.3 met:

- `publisher_version = EM2_CORE_PUBLISH_V0.9.5`;
- `state_revision = decision_revision = shadow_revision = 252`;
- `control_mode = SHADOW`;
- WW State `EM2_WW_STATE_V0.8`;
- WW Control `EM2_CONTROL_WW_V0.10`;
- `fallbackAccounting = CONFIRMED_HEATING_MINUTES`;
- `readOnly = true`, `deviceWrites = false`, `physicalWritePerformed = false`.

Op het validatiemoment was het dagdoel al bereikt. Daarom was `remainingFallbackMin=0` ondanks de nieuwe `heatingMinToday` die vanaf de cut-over conservatief op 0 begon. De actuele Shadow-intentie was terecht `BOILER_OFF / MUST / GOAL_REACHED`.

## Publisher en load-budget

```text
schema_version    = 2.3
publisher_version = EM2_CORE_PUBLISH_V0.9.5
control_mode      = SHADOW
```

Operationeel budget:

- 1 × `getDevices()` per 5 minuten in Core Tick;
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

De eerdere fallback-accounting op relais-aan-tijd is met v0.9.5 opgelost als blocker. Voor promotie van WW naar fysieke Control blijft een volledige dagcyclus met de nieuwe confirmed-heating-accounting nog te valideren.

> Laatste update: **18 augustus 2026 — Core Tick v0.9.5.** De 240-minutenfallback telt uitsluitend bevestigde verwarming >1500 W; relais-aan-tijd blijft diagnostiek. Opportunity-specifieke run-locks uit v0.9.4 blijven behouden. PURE SHADOW, geen fysieke writes.
