# Frontend V2 — EMS objectives, semantics and roadmap

**Status:** canonical design guidance  
**Scope:** private Pi-hosted Frontend V2  
**Principle:** the website is not merely a dashboard; it is the primary observability, validation and optimisation instrument for the EMS.

## 1. Objective

Frontend V2 must make the complete EMS feedback loop understandable and testable:

> **forecast -> plan -> execute -> measure -> evaluate -> improve**

The site therefore has three distinct questions to answer:

1. **What is happening now?** — realtime energy truth, device state and active EMS decision.
2. **What will the EMS do, and why?** — requirements, forecast, planned allocation and constraints.
3. **Was the decision good afterwards?** — planned versus actual behaviour, PV utilisation, grid impact, missed opportunity and data quality.

A value belongs on Frontend V2 when it helps operate, validate or improve the EMS. Decorative telemetry or duplicated values without a clear decision/validation purpose should not be added.

## 2. Authority and measurement semantics

### 2.1 P1 remains realtime grid authority

P1 is the canonical realtime measurement of the grid boundary:

- positive signed P1 power = net import;
- negative signed P1 power = net export;
- P1 validity is independent from PV inverter freshness;
- stale PV data must never invalidate P1, block realtime control, or make an EV/WW/heating decision depend on stale inverter telemetry.

The Live site must label this quantity **Net / P1** (import/export), not household consumption.

### 2.2 PV production has independent source quality

PV production is measured through the SolarEdge and GoodWe sources. Each source retains its own freshness/age. The aggregate PV presentation must expose a quality state rather than silently treating delayed inverter values as current measurements.

Canonical presentation quality classes:

- `MEASURED` — all required PV sources are current;
- `PARTIAL` — one or more sources are unavailable/delayed but some current production information remains;
- `STALE` — current aggregate PV production is not reliable enough for an exact realtime household-consumption reconstruction;
- `NIGHT` — zero production may be treated as expected only when the EMS has an explicit reliable night/solar-state basis; clock time alone is not sufficient to invent a measurement.

`PARTIAL` and `STALE` may support clearly labelled diagnostics/estimates in a future model, but must not be presented as exact measured PV.

### 2.3 Household consumption is derived, not P1

When P1 and aggregate PV are sufficiently valid:

```text
houseConsumptionW = pvProductionW + signedP1W
```

where signed P1 is positive for import and negative for export.

The Live **Huis** value must therefore be labelled as derived/calculated. When PV quality is insufficient, exact realtime household consumption is **unknown** and the UI must show `—` plus the reason (for example `PV-data vertraagd`). It must not substitute P1 net power and call that household consumption.

Historical household energy remains derived from cumulative counters:

```text
house_kWh = grid_import_kWh + pv_production_kWh - grid_export_kWh
```

Historical closed/validated counter intervals are the preferred basis for retrospective truth and forecast validation.

### 2.4 Device loads are independent observations

EV, WW and Quatt/space-heating measurements remain independently visible even when PV is stale. A stale PV source must not erase a known device load.

Known device loads may later be used for an **observability plausibility check** (for example derived household load cannot credibly be lower than simultaneously measured known loads). Such a check is diagnostic only and must not create a second realtime energy authority or override P1.

## 3. Page responsibilities

### Live — realtime truth and active decision

Must answer: **what is happening now and what is the EMS doing about it?**

Required direction:

- Net/P1 import-export as canonical grid-boundary truth;
- PV production plus source freshness/quality;
- derived household consumption only when its inputs are sufficiently valid;
- EV, WW, space heating and residual/other loads where semantically valid;
- current EMS decision, reason and priority/constraint context;
- freshness/quality must be visible, not hidden behind apparently exact numbers.

The active EMS decision/reason is operationally important and must not be computed in JavaScript without a visible presentation element.

### Invoer — explicit requirements and policy

Must answer: **what constraints and user intent is the EMS planning against?**

EV current SOC, target SOC, deadline and maximum current remain explicit requirements. WW source/mode and fixed-contract policy should be presented as policy/requirements, not as planner choices when they are decided outside the planner.

### Historie — measured outcome

Must answer: **what actually happened?**

Retain household energy, PV, import/export and data-quality/coverage. Extend the page with EMS-relevant outcome KPIs rather than generic telemetry, including where data permits:

- PV self-consumption percentage;
- self-sufficiency percentage;
- flex energy by resource;
- grid import/export attributable to flexible operation;
- cost/economic outcome under the active fixed-contract policy.

### Planner — intended future behaviour

Must evolve from a PV Forecast display into the joint planning view. On one common 15-minute time axis it should expose at least:

- PV forecast + confidence;
- requirements/constraints;
- expected baseline/non-flex demand when/if a validated model exists;
- EV plan;
- electric WW plan when WW mode is BOILER;
- Heating Flex/preheat plan;
- expected grid import/export or another explicit joint-allocation consequence when the planner contract can support it honestly.

No invented baseline forecast may be added merely to fill the chart. P1 remains realtime execution authority.

### PV & Flex — retrospective EMS validation

This is the primary page for answering: **did the EMS use the available PV opportunity well?**

Use the same conceptual time axis as Planner and compare:

- forecast PV;
- actual validated PV;
- planned EV/WW/heating allocation;
- actual EV/WW/heating operation;
- actual P1 import/export;
- data quality/coverage.

Target KPIs include:

- PV self-consumption %;
- PV used by flexible resources (kWh);
- avoided grid import (kWh), where causally supportable;
- unused/missed PV opportunity (kWh), only from a defined benchmark/replay method;
- planned-versus-actual execution deviations.

Do not label all export as a planner failure. A `missed opportunity` metric requires an explicit feasible benchmark that respects availability, deadlines, comfort, actuator limits and policy.

### Verwarming — comfort-preserving Heating Flex validation

Must evolve from Honeywell baseline-only observability to a common timeline containing:

- Honeywell scheduled baseline;
- actual Honeywell target;
- measured room temperature;
- Heating Flex proposed/actual advancement;
- PV Forecast/opportunity context;
- P1 import/export;
- Quatt electrical power;
- eventually learned thermal response/retention evidence.

The page must make it possible to verify that EMS shifts existing future heat demand without inventing extra comfort demand.

## 4. Cross-page design rules

- One shared main navigation source remains mandatory.
- Use the same terms for the same physical quantities on every page.
- Distinguish `MEASURED`, `DERIVED`, `FORECAST`, `PLANNED` and `ESTIMATED` values in labels/tooltips where ambiguity is possible.
- Never hide stale/partial source quality behind an exact-looking number.
- Planner and retrospective analysis should converge on compatible 15-minute timelines so intended and actual behaviour can be compared directly.
- Website observability is read-only unless an explicitly documented input/command boundary exists; presentation code must not become a new control authority.

## 5. Implementation order

1. **Correct Live semantics** — split Net/P1 from derived Huis; introduce PV quality; show unknown household consumption when PV is insufficient; restore visible EMS decision/reason.
2. **Complete Planner observability** — expose joint EV/WW/heating plan and constraints on the forecast timeline as the Planner V2 contracts become available.
3. **Complete PV & Flex validation** — add P1 and planned-versus-actual flex lanes; integrate Heating history; add well-defined EMS outcome KPIs.
4. **Complete Heating Flex observability** — baseline, actual room state, preheat, PV/P1 and Quatt on one timeline.
5. **Strengthen Historie KPIs** — self-consumption, self-sufficiency, flex energy and fixed-contract economic outcome.
6. **Only then optimise presentation polish** — visual refinement must follow semantic correctness and validation value.

## 6. Acceptance criterion

Frontend V2 is functionally complete for EMS development when an operator can select a period and reconstruct the chain:

```text
What did we know? -> What did we plan? -> Why? -> What was executed? -> What actually happened at P1/PV? -> Was the outcome feasible and good? -> What should the EMS learn/change?
```

Until that chain is visible, Frontend V2 is considered a strong observability foundation but not yet a complete EMS validation instrument.
