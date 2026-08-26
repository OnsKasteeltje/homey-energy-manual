---
component: business-case-evidence-pipeline
title: Business Case Evidence Pipeline
status: implemented-read-only
last_verified: 2026-08-26
---

# Business Case Evidence Pipeline

## Doel

Deze component voedt `EMS Business Case Engine v2` met reproduceerbare evidence zonder een tweede EMS-controlpad te introduceren.

```text
Canonical 5-min telemetry ──────────────┐
                                       ├─► immutable day archive (400 d)
Contract/price history ─► tariff resolver ─► normalized replay samples
                                       │
24h Planner SHADOW ─┐                  │
Power Intent ───────┴─► 15-min issuance evidence ─► forecast-realistic replay
                                       │
Victron telemetry (future LIVE) ─► calibration analyzer
                                       │
                                       ▼
                         Business Case Engine v2
                      baseline / EMS / Oracle / finance
```

## 1. High-resolution energy evidence

Bestaande producer:

`EM v2 | 70 History | Day Series v0.5.4`

blijft eigenaar van canonieke 5-minutenmetingen en de bestaande 7-daagse websitehistory.

Nieuwe evidenceflow:

`EM v2 | 72 History | Immutable Day Archive v0.1`

- leest de bestaande rolling full-resolution history;
- pollt geen devices;
- archiveert iedere afgeronde dag als `docs/data/history/days/YYYY-MM-DD.json`;
- schrijft een kleine `day-index-v1.json` met maximaal 400 dagen;
- maakt geen normale in-place wijzigingen aan een eenmaal afgesloten dag;
- heeft geen control-impact.

## 2. Historische tariff evidence

`business-case-tariff-resolver-v0.1.js` gebruikt `contract-history-v01.json` als primaire prijsbron. De resolver kiest het laatste `GOOD` record dat niet later ligt dan de te waarderen energietijdstap. Een expliciete fallback is toegestaan maar blijft als fallback zichtbaar in de provenance.

De history-adapter bewaart bij iedere sample:

- import/exportprijs;
- contracttype;
- tariff source/quality;
- tariff timestamp en age.

## 3. Forecast-realistic Planner/Intent evidence

Nieuwe Homey-flow:

`EM v2 | 76 Evidence | BC Planner Intent Recorder v0.1`

Cadans: 15 minuten.

De flow leest uitsluitend bestaande Logic-state en de gepubliceerde Planner SHADOW-output. Hij bewaart issuance-time evidence in `EM2_BC_PlannerIntent_Buffer_v1` en archiveert de afgesloten dag naar `docs/data/history/ems/YYYY-MM-DD.json`.

Hierdoor kan later worden onderscheiden:

```text
Oracle/perfect information
        versus
wat Planner vooraf wist/besliste
        versus
Power Intent dat werkelijk werd gepubliceerd
        versus
realized physical result
```

Er vindt geen device polling of actuatorwrite plaats.

## 4. CAPEX evidence

`business-case-capex-v1.json` is de versioned markt-/investeringsbron. De component onderscheidt:

- reeds aanwezige/sunk hardware;
- bekende nog aan te schaffen hardware;
- nog onbekende balance-of-system;
- nog onbekende installatie/self-install cost;
- known incremental hardware subtotal;
- complete CAPEX.

`business-case-capex-v0.1.js` laat operationele replay toe vóór CAPEX compleet is maar blokkeert de overgang naar een volledige financiële case totdat een expliciete complete CAPEX beschikbaar is.

## 5. Victron calibration evidence

`business-case-victron-calibration-v0.1.js` is nu softwarematig gereed maar verzamelt nog geen fysieke telemetry zolang Victron niet geïnstalleerd/commissioned is.

Na live-integratie kan de analyzer uit tijdreeksen afleiden:

- AC charge/discharge energy;
- DC charge/discharge energy waar beschikbaar;
- afzonderlijke charge/discharge efficiency;
- round-trip efficiency bij voldoende SOC-closure;
- standby/system loss waar expliciet gemeten;
- throughput en equivalent full cycles.

`business-case-calibration-v1.json` legt quality gates en de no-auto-promotionregel vast.

## 6. Architectuurgrenzen

Harde invarianten:

- evidencecollectoren zijn read-only ten opzichte van fysieke energiecontrol;
- bewijsopslag in Logic/GitHub is geen actuatorwrite;
- collector failure beïnvloedt realtime EMS-control niet;
- forecasts worden opgeslagen op het moment dat ze beschikbaar zijn en niet achteraf uit realized data gereconstrueerd;
- missing evidence blijft missing;
- BC Engine en Oracle kunnen nooit Power Intent of safety-limits schrijven.

## 7. Evidence maturity

De component bouwt vanaf 26 augustus 2026 doorlopend high-resolution/forecast evidence op. De reeds beschikbare rolling 5-minutenhistorie is bij ingebruikname gebackfilld naar immutable dagbestanden. Historie van vóór de bestaande bronretentie kan niet worden gereconstrueerd en wordt niet gefabriceerd.
