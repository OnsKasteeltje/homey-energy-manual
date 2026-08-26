---
component: business-case-evidence-pipeline
title: Business Case Evidence Pipeline
status: implemented-read-only
last_verified: 2026-08-26
source:
  - docs/data/history/
  - docs/javascripts/business-case-history-adapter-v0.1.js
---

# Business Case Evidence Pipeline

## Purpose

This component feeds EMS Business Case Engine v2 with reproducible evidence without introducing a second EMS control path.

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

The existing canonical five-minute history remains the diagnostic source. Completed days are archived immutably, historical tariffs are resolved without future look-ahead, and Planner/Power Intent issuance is recorded every 15 minutes at the time it becomes available. Forecast evidence is therefore never reconstructed afterwards from realized data.

CAPEX evidence is versioned and distinguishes sunk hardware, known incremental hardware, unknown balance-of-system and installation/self-installation costs, and complete CAPEX. Operational replay may run before CAPEX completion, while full financial KPIs remain gated.

Victron calibration evidence is software-ready but awaits physical installation and commissioning. Evidence collectors remain read-only with respect to physical energy control; collector failure cannot affect real-time EMS control, missing evidence remains missing, and neither the BC Engine nor Oracle may write Power Intent or safety limits.

Evidence accumulation started on 26 August 2026. Available rolling five-minute history was backfilled into immutable day files; older unavailable history is not reconstructed or fabricated.
