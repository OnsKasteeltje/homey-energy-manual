# Planner v0.5 — Power Intent efficiency preparation

Status: design/preparation only. No Homey runtime changes and no physical device writes.

## Goal

Prepare the next Planner iteration so that the Planner owns the optimization of energy and power allocation, while Power Intent remains a thin canonical representation of the requested device power.

Desired chain:

`forecast + prices + current goals -> Planner optimizer -> EV_target_W / WW_target_W / Battery_target_W -> Power Intent -> adapters -> device output`

## Architecture principles

1. **Planner owns policy and optimization.** Power Intent must not become a second optimizer.
2. **Power Intent is explicit per 15-minute slot.** Each flexible asset receives a numeric target in watts.
3. **Adapters remain device translators.** They convert target power to an executable command and apply safety/fail-closed rules; they do not choose the economically optimal time.
4. **Warm-water planning is energy-budget based.** Remaining WW demand should be modeled in kWh rather than only runtime minutes.
5. **PV-first marginal allocation.** The relevant quantity is residual surplus after structural/base load and already allocated flexible loads.
6. **Deadlines are hard constraints.** Opportunity optimization may not endanger Tesla or WW deadlines.
7. **Phase-aware headroom is a Planner constraint.** Boiler is modeled as an L2 single-phase load; Tesla/Easee is three-phase. Total-grid headroom alone is insufficient.
8. **SHADOW first.** v0.5 preparation must remain control-neutral until the existing Planner/Power Intent validation gates are passed.

## Proposed slot schema additions

Each Planner slot should expose at least:

```json
{
  "availableSurplusW": 0,
  "flexAllocatedW": 0,
  "targets": {
    "evTargetW": 0,
    "wwTargetW": 0,
    "batteryTargetW": 0
  },
  "phaseHeadroomW": {
    "l1": null,
    "l2": null,
    "l3": null
  },
  "score": {
    "marginalImportW": 0,
    "deadlinePenalty": 0,
    "pricePenalty": 0,
    "phasePenalty": 0
  }
}
```

Compatibility note: existing action labels (`tesla`, `warmWater`, `battery`) may remain temporarily as derived presentation fields while the numeric targets become the canonical planner output.

## Core allocation model

For each 15-minute slot:

```text
availableSurplusW = max(
  0,
  pvForecastW
  - baseLoadForecastW
  - alreadyAllocatedFlexibleLoadW
)
```

The Planner should minimize marginal grid import for flexible demand:

```text
marginalImportW = max(0, requestedFlexibleW - availableSurplusW)
```

Price is evaluated only for energy that remains imported after PV allocation. This preserves the project principle that opportunistic charging/heating is PV-first, while price optimization is mainly relevant when a deadline forces grid energy.

## Warm-water model

Current modeled boiler power remains approximately 1900 W until measured otherwise.

Replace runtime-first planning with an explicit energy budget:

```text
wwRemainingEnergyKWh
wwDeadlineLocal = 19:00
wwModeledPowerW = 1900
slotEnergyKWh = wwModeledPowerW * 0.25 / 1000
requiredSlots = ceil(wwRemainingEnergyKWh / slotEnergyKWh)
```

The optimizer may select non-contiguous slots. It should prefer slots with highest residual PV surplus and then lowest marginal import cost, subject to the deadline and minimum practical switching constraints.

`goalReachedToday=true` remains authoritative: when confirmed, today's remaining WW energy becomes zero and no further mandatory WW target is planned that day.

## Multi-block WW optimization

Candidate WW slots before the deadline should be ranked by:

1. hard feasibility / deadline;
2. PV surplus cover of the 1900 W boiler load;
3. marginal grid import caused by WW;
4. imported-energy price;
5. anti-fragmentation tie-breaker.

The optimizer should not implicitly form one contiguous window. Non-contiguous 15-minute blocks are valid when they reduce grid import or cost.

A small anti-fragmentation penalty can be used to avoid excessive switching without reintroducing a contiguous-window requirement.

## Asset conflict resolution

The Planner must allocate competing flexible loads centrally. Recommended order:

- reserve energy required to satisfy hard deadlines;
- exploit PV surplus for flexible demand;
- allocate remaining forced/imported energy to the cheapest feasible slots;
- avoid simultaneous peaks when spreading does not harm deadlines or PV utilization;
- enforce phase headroom before accepting a slot allocation.

Adapters must not resolve conflicts between EV and WW independently.

## Phase-aware 3x25 A constraint

Current documentation identifies the boiler as approximately 1.9–2.0 kW / ~8.5 A on L2 and Tesla/Easee as three-phase. v0.5 should therefore add per-phase forecast/constraint hooks:

```text
headroomL1W
headroomL2W
headroomL3W
```

Until trustworthy per-phase forecast/headroom inputs are available, these fields must remain explicit `null` / `NOT_MODELED_PHASE_AWARE` and may not be treated as safe headroom.

When implemented, an allocation is feasible only if all affected phases retain configured safety headroom.

## Power Intent contract

Planner output should become the only upstream policy source for flexible-device target power:

```text
EV_target_W      <- plan.targets.evTargetW
WW_target_W      <- plan.targets.wwTargetW
Battery_target_W <- plan.targets.batteryTargetW
```

Power Intent should add metadata such as source revision, slot timestamp, reason, freshness and mode, but should not alter the target for economic optimization.

Adapters may clamp or reject a target only for device/safety constraints. Any clamp/rejection must be observable so planned target, Power Intent and adapter output can be compared.

## Observability required before LIVE promotion

For every slot publish:

- forecast PV;
- forecast base load;
- residual `availableSurplusW`;
- selected targets per asset;
- reason/score components;
- actual Power Intent target;
- eventual adapter requested output;
- realized PV, P1 import/export and device power when available.

This enables `Plan -> Power Intent -> adapter output -> realized result` validation without physical writes during SHADOW.

## Acceptance tests

1. **WW multi-block:** a synthetic day with separated high-PV intervals selects separated WW slots when these reduce marginal import.
2. **No artificial contiguity:** a lower-value slot between two high-value slots remains HOLD if the energy requirement can be met by the better slots.
3. **Deadline guarantee:** insufficient PV still schedules enough WW/EV energy before deadline using the least-cost feasible imported slots.
4. **PV-first:** a higher-priced slot with full PV cover may beat a cheaper slot that would require grid import.
5. **Asset conflict:** EV and WW competing for the same surplus are centrally allocated without double-counting the same PV surplus.
6. **Phase safety:** an otherwise attractive WW slot is rejected if L2 headroom is insufficient.
7. **Goal reached:** `goalReachedToday=true` yields zero mandatory same-day WW energy and `WW_target_W=0` unless an explicit future-day plan is represented separately.
8. **Contract purity:** Power Intent equals the Planner target unless an adapter safety clamp/rejection is explicitly reported.
9. **SHADOW invariant:** no code in this preparation path performs physical writes.

## Implementation sequence

### Stage A — schema/observability only

Add numeric target fields and score traces to Planner output while retaining current action strings for UI compatibility. Do not alter runtime control.

### Stage B — WW energy budget + multi-block scorer

Add `wwRemainingEnergyKWh`, derive slot requirement, rank slots by residual surplus / marginal import / price, and validate against synthetic fixtures.

### Stage C — central flex allocation

Prevent EV/WW/battery from double-allocating the same forecast surplus. Add explicit ordering/conflict traces.

### Stage D — phase-aware feasibility

Introduce per-phase headroom inputs and constraints only after their data quality is demonstrably reliable.

### Stage E — Power Intent comparison

Expose Plan vs Power Intent vs adapter output side by side on the site and validate equality/clamps in SHADOW before any LIVE promotion.

## Non-goals for v0.5 preparation

- no competing battery optimizer; Victron DESS remains the primary battery optimizer;
- no physical device writes;
- no additional high-frequency Homey polling;
- no assumption that absent/stale headroom data is zero-risk;
- no migration of economic policy into adapters.
