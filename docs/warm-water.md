# Warm water optimalisatie — Energy Core v2

**Status:** 🟢 actief in **PURE SHADOW**  
**Actieve kern:** `EM v2 | 00 Core Tick | v0.9.5`  
**Context:** `EM v2 | 30 Context | Price + PV v0.1`  
**Fysieke v2-boilerwrites:** **uitgeschakeld**

De warmwaterregeling is onderdeel van Energy Core v2. Core observeert de elektrische boiler, leidt de dagstatus af en berekent iedere vijf minuten de gewenste aansturing. Fysieke aan/uit-acties zijn nog niet actief.

## Dagdoel

Het primaire comfortdoel is dat de elektrische boiler eenmaal per lokale kalenderdag aantoonbaar `OP_TEMPERATUUR` bereikt. Zodra dat is gebeurd blijft `goalReachedToday=true` tot de dagwissel en volgt geen same-day reheat. De 240-minutenregel is alleen fallback wanneer `OP_TEMPERATUUR` niet betrouwbaar wordt vastgesteld.

## Detectie OP_TEMPERATUUR

```text
boiler aan + vermogen > 1500 W gedurende minimaal 15 min
    → verwarmen bevestigd

daarna boiler nog aan + vermogen < 100 W gedurende minimaal 10 min
    → interne thermostaat afgeslagen
    → OP_TEMPERATUUR bereikt
```

De actuele state is `EM2_WW_STATE_V0.8`.

## Opportunity planner

Vanaf 09:30 combineert Core actuele netexport met verse prijs- en PV-forecastcontext.

| Opportunity | Startvoorwaarde | Run-lock |
|---|---|---:|
| `EXPORT` | ≥2100 W actuele netexport | 15 min |
| `PV_FORECAST` | top-4 PV-forecast én ≥500 W export | 15 min |
| `PRICE_NEGATIVE` | negatieve prijs én ≥30 min tot volgend tariefuur | 30 min |
| `PRICE_CHEAP` | goedkoper dan komende 4 uur én ≥30 min tot volgend tariefuur | 30 min |
| `CATCHUP` | verder wachten bedreigt dagdoel/deadline | 0 min opportunity-lock |

Voor 09:30 wordt spontane herverwarming na ochtendgebruik in Shadow juist afgeraden. Een prijsstart vlak voor een uurgrens wordt voorkomen met `WAIT_PRICE_HORIZON`.

## Fallback en deadline — gewijzigd in v0.9.5

De dagelijkse regelperiode eindigt om 19:00. Vanaf Core Tick v0.9.5 wordt catch-up niet meer gebaseerd op relais-aan-tijd.

`boilerOnMinToday` blijft beschikbaar als diagnostiek, maar de fallback gebruikt `heatingMinToday`. Alleen een interval waarin het relais AAN staat én het gemeten boilervermogen >1500 W is telt mee:

```text
heatingNow = boilerOn && boilerPowerW > 1500 W
heatingMinToday += deltaMin alleen wanneer heatingNow
remainingFallbackMin = max(0, 240 - heatingMinToday)
```

Als `OP_TEMPERATUUR` al is bereikt wordt `remainingFallbackMin` direct 0. De state en Control publiceren expliciet:

```text
fallbackAccounting = CONFIRMED_HEATING_MINUTES
fallbackHeatingThresholdW = 1500
```

Hiermee is de eerdere blocker opgelost waarbij een relais dat uren AAN stond met een open interne thermostaat ten onrechte als verwarmingsduur werd geteld.

### Migratiekwaliteit op 18 augustus

De oude v0.9.4-state kende geen betrouwbare historische `heatingMinToday`. Daarom begint die teller op de cut-overdag conservatief vanaf de activatie van v0.9.5 met `heatingAccountingQuality = PARTIAL_FROM_V0.9.5_START`. Een reeds bereikt en gelatcht dagdoel blijft geldig; op het eerste v0.9.5-validatiemoment was `goalReachedToday=true` en dus `remainingFallbackMin=0`.

## Context en freshness

`EM v2 | 30 Context | Price + PV v0.1` vernieuwt iedere 15 minuten prijs- en PV-signalen zonder fysieke device-scan. Core accepteert context tot maximaal 35 minuten oud. Bij stale context worden prijs en forecast genegeerd; actuele export en harde catch-up blijven bruikbaar.

## Veiligheid

WW Control gebruikt nu schema `EM2_CONTROL_WW_V0.10` en blijft volledig Shadow:

```text
controlMode            = SHADOW
readOnly               = true
deviceWrites           = false
physicalWritePerformed = false
```

`BOILER_ON`, `BOILER_OFF` en `HOLD` zijn dus adviezen, geen fysieke acties.

## Validatie v0.9.5

De eerste handmatige run na de veilige cut-over publiceerde op 18 augustus 2026:

- `publisher_version = EM2_CORE_PUBLISH_V0.9.5`;
- schema 2.3;
- `state_revision = decision_revision = shadow_revision = 252`;
- WW State `EM2_WW_STATE_V0.8`;
- WW Control `EM2_CONTROL_WW_V0.10`;
- `fallbackAccounting = CONFIRMED_HEATING_MINUTES`;
- `deviceWrites=false` en `physicalWritePerformed=false`.

De Shadow-uitkomst was `BOILER_OFF / MUST / GOAL_REACHED`, passend bij het al behaalde dagdoel.

## Samenwerking met andere energieverbruikers

WW is één flexibele belasting binnen Energy Core v2. De centrale architectuur gaat gezamenlijk budgetteren tussen huishoudelijk basisverbruik, Tesla/Easee, elektrische boiler, Quatt als serieuze energieverbruiker en later Victron/batterij.

> **Volgende WW-validatie vóór fysieke Control:** een volledige dagcyclus observeren met de nieuwe confirmed-heating-accounting en de opportunity-planner. De fallback-accounting op relais-aan-tijd is met v0.9.5 opgelost.
