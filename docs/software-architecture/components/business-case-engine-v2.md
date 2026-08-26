---
component: business-case-engine-v2
title: EMS Business Case Engine v2
status: shadow
architecture_status: implemented-read-only
last_verified: 2026-08-26
sources:
  - docs/javascripts/business-case-engine-v2.js
  - docs/javascripts/business-case-oracle-v0.1.js
  - docs/javascripts/business-case-history-adapter-v0.1.js
  - docs/javascripts/business-case-tariff-resolver-v0.1.js
  - docs/javascripts/business-case-capex-v0.1.js
  - docs/javascripts/business-case-victron-calibration-v0.1.js
  - docs/data/business-case-scenarios-v2.json
  - docs/data/business-case-capex-v1.json
  - docs/data/business-case-calibration-v1.json
  - docs/data/history/day-index-v1.json
---

# EMS Business Case Engine v2

## 1. Doel

De Business Case Engine maakt batterij-/EMS-keuzes reproduceerbaar, counterfactual en evidence-driven. De component rekent op historische tijdstappen en scheidt strikt physical model, economic model, EMS strategy en evidence/calibration.

De volledige component is **read-only** ten opzichte van energiecontrol: `controlImpact=false`. Er bestaat geen writerroute naar Easee, boiler, Power Intent of Victron. Logic/GitHub-writes door evidencecollectoren dienen uitsluitend persistence.

## 2. Actuele architectuur

```text
Canonical 5-min telemetry
        │
        ├── rolling 7d diagnostics
        └── immutable day archive / 400 d
                    │
Contract history ─► tariff resolver
                    │
                    ▼
             History adapter
                    │
             normalized samples
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
 no battery   self-consumption  EMS replay
                                  ▲
Planner + Power Intent issuance ──┘
        │
        └── forecast-realistic evidence

Perfect-information Oracle ─► canonical EMS replay
                    │
                    ▼
        economic/energy decomposition
                    │
            CAPEX completeness gate
                    │
          NPV/payback only if complete
                    │
Victron runtime ─► calibration analyzer
```

Zie ook `business-case-evidence-pipeline.md` en de Business Case Evidence Hardening Guidelines.

## 3. Tijdstap en tariff evidence

De primaire rekeneenheid is een tijdstap, niet een jaartotaal. `business-case-history-adapter-v0.1.js` normaliseert P1/validity en bewaart tariff provenance.

`business-case-tariff-resolver-v0.1.js` gebruikt de historische contractreeks als primaire bron. Per sample wordt alleen het laatste `GOOD` tarief met `tariffAt <= sample.ts` gebruikt. Er is dus geen future look-ahead. Een expliciete fallback blijft als `EXPLICIT_FALLBACK` herkenbaar.

Per tijdstap blijven minimaal traceerbaar:

- P1/netvermogen + measurement validity;
- import- en exportprijs;
- contracttype;
- tariff source, quality, timestamp en age;
- intervalduur;
- optioneel EMS battery target.

`NULL_IS_UNKNOWN_NEVER_ZERO` blijft bindend.

## 4. High-resolution evidence

De bestaande `EM v2 | 70 History | Day Series v0.5.4` blijft de canonieke 5-minutenproducer en houdt de bestaande rolling 7-daagse diagnostische history intact.

`EM v2 | 72 History | Immutable Day Archive v0.1` archiveert afgesloten dagen afzonderlijk onder:

```text
docs/data/history/days/YYYY-MM-DD.json
```

De index `day-index-v1.json` heeft een retentietarget van 400 dagen. Bij ingebruikname zijn de reeds beschikbare afgeronde dagen uit de rolling bron gebackfilld. Oudere niet-bewaarde 5-minutendata wordt niet gereconstrueerd.

## 5. Strategieën en Oracle

De engine ondersteunt:

- `BASELINE_NO_BATTERY`;
- `BATTERY_SELF_CONSUMPTION`;
- `BATTERY_EMS_REPLAY`.

`business-case-oracle-v0.1.js` is een afzonderlijke perfect-information dynamic-programming optimizer. Oracle-acties worden terug door dezelfde replaykernel gevoerd zodat fysieke/economische accounting identiek blijft.

De BC onderscheidt expliciet:

```text
Oracle / perfect information
Forecast-realistic EMS
Realized EMS
```

en kan de EMS capture ratio berekenen zodra vergelijkbare datasets beschikbaar zijn.

## 6. Forecast-realistic evidence

`EM v2 | 76 Evidence | BC Planner Intent Recorder v0.1` draait iedere 15 minuten en leest uitsluitend bestaande Logic-state en Planner SHADOW-publicatie.

Hij bewaart issuance-time evidence, waaronder:

- plan generation/schema;
- toen geldend plan-slot;
- forecast PV/prijscontext;
- geplande EV/WW/batterijtargets en reason;
- Power Intent schema/revision/validity;
- EV/WW/batterij-intents en writeAllowed.

De actuele dag staat restart-persistent in `EM2_BC_PlannerIntent_Buffer_v1`; na dagwisseling wordt hij immutable onder `docs/data/history/ems/YYYY-MM-DD.json` opgeslagen. Forecasts worden daarmee niet achteraf uit realized data gereconstrueerd.

## 7. Physical model

Ieder scenario bevat capaciteit, SOC-band, laad-/ontlaadvermogen, afzonderlijke charge/discharge efficiency, standby en degradation cost per throughput-kWh.

Tekenconventie:

```text
+W = batterij laden / extra AC-load
 0 = idle
-W = batterij ontladen / AC-supply
```

De engine publiceert charge/discharge, throughput, equivalent full cycles, conversion loss, standby, curtailed energy en terminal SOC.

## 8. CAPEX en financial readiness

`business-case-capex-v1.json` bewaart actuele componentprijzen als versioned evidence en onderscheidt reeds aanwezige hardware, nog aan te schaffen hardware, balance-of-system en installatie/self-install.

De huidige vergelijkingsset bevat:

- 2 × Pylontech US5000;
- 3 × Pylontech US5000;
- BYD Battery-Box Premium LVS 12.0.

`knownIncrementalHardwareEuro` mag worden gebruikt voor transparantie, maar `completeCapexEuro` blijft `null` zolang BOS/installatie niet expliciet compleet zijn. Operationele replay werkt dan wel; `financialCase()`/investerings-KPI's worden pas als compleet beschouwd met gevalideerde totale CAPEX.

## 9. Victron calibration

`business-case-victron-calibration-v0.1.js` is softwarematig gereed voor toekomstige fysieke telemetry. Met AC/DC battery power, SOC en expliciete system-loss telemetry kan hij afleiden:

- AC/DC charge/discharge energy;
- charge/discharge efficiency;
- round-trip efficiency bij voldoende SOC-closure;
- standby/system loss;
- throughput en equivalent full cycles.

`business-case-calibration-v1.json` legt coverage/throughput-quality gates vast. Een `GOOD` calibration kan alleen een candidate opleveren; promotie naar scenario-aannames gebeurt nooit automatisch.

Fysieke calibration evidence kan pas ontstaan na Victron-installatie en commissioning.

## 10. Economics en reproduceerbaarheid

Iedere euro blijft herleidbaar via baseline energy cost, scenario energy cost, gross saving, degradation en net operational saving. NPV/payback voegen daarna CAPEX/onderhoud/residual value/discounting toe.

Iedere publiceerbare BC vermeldt minimaal:

- engine/schema revision;
- evidence window en coverage;
- tariff provenance;
- scenario/config revision;
- operational KPI's en losses;
- CAPEX completeness;
- Oracle/forecast/realized status;
- relevante sensitivity/uncertainty.

## 11. Huidige status — 26 augustus 2026

| Onderdeel | Status |
|---|---|
| Replay kernel | IMPLEMENTED SHADOW/read-only |
| History adapter | IMPLEMENTED |
| Historical tariff resolver | IMPLEMENTED; FIXED/DYNAMIC history-aware |
| Perfect-information Oracle | IMPLEMENTED v0.1 |
| 400d immutable high-resolution archive | IMPLEMENTED + initial backfill active |
| Planner/Power Intent issuance recorder | IMPLEMENTED, collecting from now |
| Pylontech 2×/3× scenario | IMPLEMENTED assumptions + current price evidence |
| BYD model | Premium LVS 12.0 selected + current price/compatibility evidence |
| CAPEX | PARTIAL: hardware subtotal known; BOS/install still explicit unknown |
| Victron calibration analyzer/contract | IMPLEMENTED; physical evidence waits for installation |
| Forecast-realistic replay dataset | ACCUMULATING from recorder start |
| Investment-ready ≥90d/year evidence | NOT YET; evidence window must grow |

## 12. Resterende maturity, geen ontbrekende architectuur

De vijf hardeningroutes zijn nu gebouwd. Wat nog tijd/evidence vereist is bewust geen softwarebelofte:

1. high-resolution/forecast history laten aangroeien tot representatieve seizoensdekking;
2. BOS en installatie/self-install kosten expliciet afronden tot complete CAPEX;
3. na Victron commissioning echte calibration telemetry verzamelen;
4. daarna sensitivity + forecast-vs-realized + EMS capture op representatieve windows rapporteren.
