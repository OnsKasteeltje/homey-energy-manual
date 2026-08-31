# Planner v0.5 WW deadline-deferral integration candidate

Status: **PREPARED / SHADOW-ONLY / NOT DEPLOYED**

Purpose: integrate the validated v0.5 WW optimizer policy into the currently active Planner `EM v2 | 45 Planner | 24h Energy Plan v0.4.9 SHADOW LOW-LOAD` without changing Tesla, battery, price-context, publication, Core, adapters, actuators, cadence, or physical ownership.

## Runtime baseline used

A single targeted read of Advanced Flow `27617767-0a64-43a3-9bcb-e34b0dd6a5c0` was performed on 2026-08-31. No flow list, variable enumeration, device read, start action, or write was needed.

Observed live facts:

- flow name: `EM v2 | 45 Planner | 24h Energy Plan v0.4.9 SHADOW LOW-LOAD`;
- enabled and not broken;
- cadence remains every 15 minutes with the existing 45-second offset;
- Planner reads only the targeted `EM2_PLANNER_INPUT_V0.1` variable and writes only the Planner snapshot Logic variable;
- `controlMode='SHADOW'`, `physicalWritePerformed=false`;
- current WW implementation first reserves forecast slots with >=1900 W PV surplus, then fills the remaining obligation from grid-requiring slots, price-first when dynamic price context is usable;
- current implementation therefore commits fallback slots for the complete remaining WW obligation even when substantial time still remains before 19:00.

That last point is the behavior changed by v0.5.

## What changes in v0.5

Only the WW allocation policy changes.

1. Convert `remainingFallbackMin` to `wwRemainingEnergyKWh` exactly as today: `remainingFallbackMin / 60 * 1.9 kW`.
2. Reserve forecast slots with zero marginal WW grid import immediately. These slots may be non-contiguous.
3. Determine how many additional 15-minute slots are still required after those PV-covered slots.
4. Do **not** reserve grid-requiring fallback while the number of remaining feasible quarters is greater than `gridSlotsNeeded + 2`.
5. The `+2` is a 30-minute deadline safety margin at 15-minute Planner resolution.
6. Once deadline feasibility becomes tight, reserve only the minimum remaining fallback slots. Rank those by lowest marginal import first and dynamic price second.
7. Preserve `goalReachedToday` as authoritative: once true, mandatory same-day WW becomes zero.
8. Preserve `catchupRequired` / MUST semantics and the hard 19:00 local deadline.
9. Preserve Tesla deadline/MUST priority over WW SHOULD and the existing WW relocation behavior.

## Why this matches the 31-Aug analysis

The GitHub-history replay showed that early grid-assisted WW was followed by later quarters with enough measured net export to absorb the boiler. The purpose of v0.5 is not to assume hindsight PV; it is to avoid committing optional grid fallback too early so the rolling 15-minute Planner can benefit from improved later forecasts and realized remaining obligation.

This is intentionally a receding-horizon policy:

`PV-covered slots now -> wait while feasible -> minimal deadline fallback only when needed`.

## Canonical tested helper

The pure implementation is:

`src/homey/planner/planner-v0.5-ww-optimizer.js`

The test suite is:

`tests/planner-v0.5-ww-optimizer.test.js`

The helper has no Homey API calls, no network calls and no device writes. CI additionally guards against adding Homey/runtime-write/network patterns to that module.

## Runtime integration mapping

The live v0.4.9 block beginning with:

```js
const rankWWFullSurplus=...
const rankWWGrid=...
const reserveWW=...
```

is the only scheduling block that needs semantic replacement. The forecast generation, `priceUsable`, Tesla selectors, day-boundary functions, flex-load relocation, battery theoretical model, snapshot schema wrapper and single Logic snapshot write remain unchanged.

The integrated v0.5 Planner should expose these additional observability fields under `plan.plan.warmWater` and/or its daily plan:

```js
{
  requestedEnergyKWh,
  requiredSlots,
  fullPvSlotsSelected,
  gridSlotsNeeded,
  remainingFeasibleSlots,
  gridFallbackSafetySlots: 2,
  deadlineUrgent,
  gridFallbackActive,
  allocatedDemandKWh,
  unallocatedEnergyKWh
}
```

Per selected action, add numeric intent while retaining existing presentation labels for compatibility:

```js
WW_target_W: 1900,
WW_allocated_kWh: <up to 0.475>,
warmWater: 'PV_PREFERRED' | 'DEADLINE_REQUIRED' | 'MUST_CATCHUP'
```

For non-selected quarters:

```js
WW_target_W: 0
```

Power Intent is not changed in this stage; these numeric fields are SHADOW observability until separately validated.

## Acceptance gates before Homey deployment

- Unit tests green.
- Existing CI no-write guard green.
- Replay fixture demonstrates no early grid fallback while deadline slack exists.
- At the latest safe start, the remaining energy is fully schedulable before 19:00.
- `goalReachedToday=true` yields no mandatory same-day WW.
- Tesla deadline/MUST conflict behavior remains unchanged.
- Planner remains SHADOW and performs no actuator/device writes.
- No new Homey polling, triggers or Logic reads are introduced.

## Deployment rule

Do not modify the current Homey Planner until a complete v0.5 HomeyScript candidate has been generated from the exact v0.4.9 runtime and diff-reviewed. Deployment, when approved, should be one targeted Advanced Flow update only. No discovery/listing calls are required because the flow ID is already reconciled.
