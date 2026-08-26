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

## Purpose

The Business Case Engine makes battery and EMS choices reproducible, counterfactual and evidence-driven. It calculates on historical time steps and strictly separates the physical model, economic model, EMS strategy and evidence/calibration.

The complete component is read-only with respect to energy control (`controlImpact=false`). It has no writer route to Easee, hot water, Power Intent or Victron.

## Current architecture

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

## Evidence and calculation model

The primary calculation unit is a time step rather than an annual total. Historical tariff resolution uses the last `GOOD` tariff whose timestamp is not later than the energy sample, preventing future look-ahead. Missing evidence remains unknown and is never silently converted to zero.

The canonical five-minute producer retains rolling diagnostics while completed days are archived immutably with a 400-day retention target. Planner and Power Intent issuance evidence is recorded every 15 minutes so future analysis can distinguish perfect-information Oracle results, forecast-realistic EMS decisions and realized physical outcomes.

## Strategies

The engine supports `BASELINE_NO_BATTERY`, `BATTERY_SELF_CONSUMPTION`, and `BATTERY_EMS_REPLAY`. A separate perfect-information dynamic-programming Oracle is passed through the same replay kernel, keeping physical and economic accounting comparable.

## Physical model

Each scenario defines capacity, SOC band, charge/discharge power, separate charge/discharge efficiency, standby consumption and degradation cost per throughput kWh. Positive power means battery charging/additional AC load; negative power means discharge/AC supply.

## CAPEX and financial readiness

Versioned CAPEX evidence distinguishes already-owned hardware, hardware still to purchase, balance-of-system and installation/self-installation. The current comparison set contains 2 × Pylontech US5000, 3 × Pylontech US5000 and BYD Battery-Box Premium LVS 12.0.

Operational replay remains available while CAPEX is incomplete, but complete NPV/payback investment KPIs are gated until total CAPEX has been explicitly validated.

## Victron calibration

The calibration analyzer is software-ready for future physical telemetry. Once commissioned it can derive AC/DC charge and discharge energy, charge/discharge efficiency, round-trip efficiency with adequate SOC closure, standby/system losses, throughput and equivalent full cycles. Calibration candidates are never automatically promoted into scenario assumptions.

## Current status — 26 August 2026

| Item | Status |
|---|---|
| Replay kernel | IMPLEMENTED SHADOW/read-only |
| History adapter | IMPLEMENTED |
| Historical tariff resolver | IMPLEMENTED; FIXED/DYNAMIC history-aware |
| Perfect-information Oracle | IMPLEMENTED v0.1 |
| 400-day immutable high-resolution archive | IMPLEMENTED + initial backfill active |
| Planner/Power Intent issuance recorder | IMPLEMENTED, collecting from now |
| Pylontech 2×/3× scenarios | IMPLEMENTED assumptions + current price evidence |
| BYD model | Premium LVS 12.0 selected + current price/compatibility evidence |
| CAPEX | PARTIAL: hardware subtotal known; BOS/installation still explicitly unknown |
| Victron calibration analyzer/contract | IMPLEMENTED; physical evidence waits for installation |
| Forecast-realistic replay dataset | ACCUMULATING from recorder start |
| Investment-ready ≥90d/year evidence | NOT YET; evidence window must grow |

## Remaining maturity

The architecture and hardening routes are built. Remaining work is evidence maturity: grow high-resolution and forecast history across representative seasons, complete BOS/installation CAPEX, collect physical Victron calibration telemetry after commissioning, and then report sensitivity, forecast-versus-realized performance and EMS capture on representative windows.
