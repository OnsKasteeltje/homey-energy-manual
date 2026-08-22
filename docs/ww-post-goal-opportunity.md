# Warm water — post-goal opportunity

**Status:** IMPLEMENTED / PURE SHADOW  
**Homey-flow:** `EM v2 | 50 Decision | WW Post-Goal Opportunity v0.2 SHADOW`  
**Fysieke boilerwrite:** nee

## Besluit

`goalReachedToday=true` betekent dat het dagelijkse comfortdoel is gehaald. Daardoor vervalt voor de rest van die lokale kalenderdag de **verplichte** heropwarming (`MUST`). Het dagdoel/latch blijft staan en wordt niet gewist.

`goalReachedToday` blokkeert echter niet langer het concept van een **economische post-goal opportunity**. Wanneer er waarschijnlijk opnieuw thermische ruimte is en energie aantoonbaar aantrekkelijk is, mag de decision-laag `OPPORTUNITY_AVAILABLE / SHOULD` adviseren. Een post-goal opportunity wordt nooit `MUST`.

## Thermische ruimte — v0.2 model

Zolang geen continue boilertemperatuur beschikbaar is, gebruikt de SHADOW-evaluator een conservatief eerste-orde model:

- configureerbaar standbyverlies: `EM2_WW_StandbyLoss_KWhDay = 1.9 kWh/24h`;
- minimale tijd na `OP_TEMPERATUUR`: `EM2_WW_PostGoal_MinDelay_Min = 60 min`;
- minimale berekende standby-headroom: `EM2_WW_PostGoal_MinHeadroom_KWh = 0.25 kWh`;
- geschatte standby-headroom = verstreken uren sinds `goalReachedAt` × 1,9 / 24.

Daarnaast wordt huishoudelijke context gebruikt zonder een niet-gemeten hoeveelheid warmwaterverbruik te verzinnen:

- `goalReachedAt < 18:00` lokaal → `eveningDrawLikelihood = HIGH` vanwege waarschijnlijk koken/afwassen en mogelijk douchen;
- 18:00–21:00 → `MEDIUM`;
- vanaf 21:00 → `LOW`.

Bij `HIGH` geldt na de minimale 60 minuten dat thermische ruimte waarschijnlijk is, ook wanneer alleen het berekende standbyverlies nog kleiner dan 0,25 kWh is. Dit is expliciet een prior/contextmodel en geen gemeten boilertemperatuur.

## Economische gate

Een post-goal opportunity vereist naast thermische ruimte een toegestane elektrische boilerbron en een economisch signaal.

Prijscontext is bruikbaar wanneer de uniforme contractcontext `GOOD` en maximaal 35 minuten oud is. De configureerbare minimale prijswinst is:

`EM2_WW_PostGoal_EconomicThreshold_EurKWh = 0.05 EUR/kWh`.

Een prijsopportunity bestaat bij:

1. negatieve actuele importprijs; of
2. `cheapNow=true` én `avgNext4h - importPriceNow >= 0.05 EUR/kWh`.

Daarnaast kan werkelijk P1-gebaseerd PV-overschot een opportunity vormen wanneer het centrale `flexExportBudgetW >= 1900 W` is. Dit gebruikt het gedeelde Core-budget en geen losse extra P1/device-polling.

De bronkeuzelaag blijft vóór de timinglaag staan. Een boiler-opportunity is alleen toegestaan wanneer `WW Source Advice` geldig is en:

- `advice = BOILER`; of
- `advice = KEEP_CURRENT` terwijl de huidige productiebron `BOILER` is.

`advice = CV` blokkeert de elektrische post-goal opportunity.

## Output

De evaluator publiceert iedere 15 minuten en kan handmatig worden gestart:

- `EM2_WW_PostGoal_Opportunity` — volledige JSON decision/context;
- `EM2_WW_PostGoal_Opportunity_Value` — `HOLD` of `OPPORTUNITY_AVAILABLE`;
- `EM2_WW_PostGoal_Opportunity_Reason` — verklarende reason-code;
- `EM2_WW_PostGoal_Opportunity_Eligible` — boolean;
- `EM2_WW_PostGoal_Opportunity_UpdatedAt` — timestamp.

Belangrijke reason-codes zijn onder andere `TOO_SOON_AFTER_GOAL`, `NO_THERMAL_ROOM`, `SOURCE_ADVICE_CV`, `NEGATIVE_PRICE`, `CHEAP_NOW_EVENING_DRAW_LIKELY`, `CHEAP_NOW_STANDBY_HEADROOM`, `PV_SURPLUS_EVENING_DRAW_LIKELY` en `ECONOMICS_NOT_ATTRACTIVE`.

## Safety en lifecycle

De flow gebruikt uitsluitend Homey Logic (`getVariables`/Logic state) en doet **geen device reads en geen actuatorwrites**. De output bevat expliciet:

- `goalReachedBlocksMustOnly=true`;
- `doesNotClearGoalLatch=true`;
- `neverMustAfterGoal=true`;
- `physicalWritePerformed=false`;
- `oneWriterArchitecturePreserved=true`.

De bestaande Core v0.10.11 bevat nog de oude harde same-day-reheat blokkade in `EM2_Control_WW`. Daarom is de v0.2 evaluator een parallelle **SHADOW-validatielaag**, geen fysieke cut-over. Na voldoende praktijkvalidatie moet deze policy in een nieuwe Core/WW-controlversie worden geïntegreerd en daarna via de ene officiële boiler-writer door de normale SHADOW → CONTROL TEST → CONTROL lifecycle gaan.

## Smoke test

De flow is na creatie en na de v0.2-aanscherping handmatig gestart. Homey accepteerde beide runs; de flow staat `enabled=true`, `broken=false`. Een ingebouwde self-check faalt wanneer een post-goal decision ooit `MUST` wordt of wanneer de safety-output een fysieke write rapporteert.
