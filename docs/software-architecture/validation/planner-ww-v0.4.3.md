# Planner WW v0.4.3 validation

Status: **SHADOW**  
Validated: 2026-08-27

## Regression found in v0.4.2

The WW ranking treated a slot as PV-first only when forecast PV surplus covered the full 1.9 kW boiler load. Partial PV coverage could therefore be grouped with zero-PV slots and lose to a cheaper grid slot under DYNAMIC pricing.

## v0.4.3 invariant

For every candidate slot before the 19:00 WW deadline:

`pvCoverageW = min(1900, max(0, pvSurplusBeforeFlexW))`

`gridRequiredW = max(0, 1900 - pvCoverageW)`

Slots are ordered by descending `pvCoverageW`. Only after equal PV coverage may DYNAMIC price break the tie; FIXED uses time as the next ordering key.

Selected slots expose:

- `PV_PREFERRED` for full or partial PV coverage;
- `DEADLINE_REQUIRED` for required zero-PV completion slots;
- `MUST_CATCHUP` for catch-up;
- `warmWaterReason`;
- `warmWaterPvCoverageW`;
- `warmWaterGridRequiredW`.

The planner remains `readOnly=true`, `controlMode=SHADOW`, and performs no boiler writes. The existing WW production writer remains physical owner.

## UI interpretation

Planner Shadow frontend v109 renders PV-preferred WW segments separately from deadline-required WW segments and shows PV coverage versus grid requirement in hover details. This prevents deadline completion from being visually presented as a PV-optimal decision.
