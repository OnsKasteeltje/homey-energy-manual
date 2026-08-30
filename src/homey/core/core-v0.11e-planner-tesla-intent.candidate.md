# Core v0.11e — Planner Tesla intent candidate

Status: **PREPARED IN GITHUB / NOT DEPLOYED TO HOMEY**

Baseline: live Homey `EM v2 | 00 Core Tick | v0.11d (Thermostat Verification Rearm)` observed on 2026-08-30.

## Incident / gap

Planner v0.4.9 publishes Tesla deadline-preferred quarter-hour slots (`PREFERRED_BEFORE_DEADLINE`) and the Planner Shadow UI can therefore show an active Tesla plan window. Core v0.11d does not consume that Tesla planner intent. Core currently starts deadline charging only when `now >= latestStart`, or earlier when an independent realtime opportunity exists (PV export / negative price / cheap-price context).

Result: the Planner can visibly reserve a Tesla window while the realtime control chain remains `HOLD`, so the Tesla does not charge during that planned window. Warm Water does not have this gap because Core already consumes the current Planner WW slot as intent and subjects it to realtime Core safety checks.

## Architecture rule

This change must **not** wire one Homey flow directly to another or make Planner the actuator policy owner.

The required architecture is:

```text
Planner forecast / economic allocation
        |
        v
Planner Tesla intent
        |
        v
Core realtime safety arbitration
        |
        v
Decision -> Power Intent -> EV Adapter -> Gate -> Actuator
```

Planner decides *when charging is preferred* within an already valid deadline obligation. Core decides *whether charging is allowed now*. Existing downstream ownership remains unchanged.

The implementation must preserve the project rule that Homey flows are implementation artifacts, not the target software architecture. Only semantic contracts are transferred.

## Objective

Add a bounded Planner Tesla intent input to Core so that a currently active Planner deadline slot can become `TESLA_CHARGE_DEADLINE` before `latestStart`, provided all realtime safety conditions pass.

No direct device write is added to Core.

## Inputs already available

Core v0.11d already reads `EM2_Energy_Planner_Snapshot` and validates:

- `plannerFresh`;
- `plannerCompatible` against `EM2_ENERGY_PLAN_24H_V0.4.9`;
- the active quarter-hour slot by `start <= now < end`.

The same active slot must expose Tesla intent:

```js
const plannerTesla = String(plannerSlot?.tesla || 'HOLD').toUpperCase();
const plannerTeslaStart = plannerSlot?.start ?? null;
const plannerTeslaEnd = plannerSlot?.end ?? null;
```

No additional Homey collection scan or device read is required.

## Accepted Planner Tesla semantics

For v0.11e only the existing deadline semantic is control-relevant:

```text
PREFERRED_BEFORE_DEADLINE
```

`OPPORTUNITY_PV_MIN_RUN` remains advisory under the existing realtime opportunity logic for now and must not create a new price/PV control path in this change.

Unknown Planner Tesla values must fail closed to no planner-driven charge request.

## Realtime Core validation

A Planner deadline slot may request an early deadline charge only when all are true:

```js
const plannerTeslaDeadlineSlot =
  plannerCompatible &&
  plannerTesla === 'PREFERRED_BEFORE_DEADLINE';

const plannerTeslaDeadlineEligible =
  plannerTeslaDeadlineSlot &&
  deadlineActive &&
  remaining > 0 &&
  Number.isFinite(latestStartMs) &&
  Date.now() < latestStartMs &&
  plugged &&
  p1Fresh &&
  gridMeasurementValid;
```

The slot must remain subject to a realtime import guard. v0.11e should reuse the existing discretionary import budget rather than inventing phase-aware headroom:

```js
const PLANNER_TESLA_MIN_IMPORT_BUDGET_W = 4140;
const plannerTeslaImportGuardOk =
  discretionaryImportBudgetW >= PLANNER_TESLA_MIN_IMPORT_BUDGET_W;
```

This threshold corresponds to the currently accepted 3-phase 6 A minimum executable charge level (`3 × 230 V × 6 A = 4140 W`). The EV Adapter remains the component that performs exact W→A quantization and max-current clamping.

If phase-aware 3×25 A headroom is not yet modeled, v0.11e must not claim that it is.

## Decision precedence

Existing MUST deadline catch-up remains highest Tesla priority.

Target precedence:

```js
if (deadlineActive && remaining > 0 && Number.isFinite(latestStartMs) && Date.now() >= latestStartMs) {
  priority = 'MUST';
  intent = plugged ? 'TESLA_CHARGE_DEADLINE' : 'TESLA_DEADLINE_BLOCKED_NOT_CONNECTED';
  reason = `Tesla deadline catch-up: ${remaining.toFixed(2)} kWh resterend`;
}
else if (plannerTeslaDeadlineEligible && plannerTeslaImportGuardOk) {
  priority = 'SHOULD';
  intent = 'TESLA_CHARGE_DEADLINE';
  reason = `Planner Tesla deadline-slot ${plannerTeslaStart}–${plannerTeslaEnd}; realtime importbudget ${Math.round(discretionaryImportBudgetW)} W`;
}
else if (plannerTeslaDeadlineSlot && deadlineActive && remaining > 0 && !plugged) {
  priority = 'SHOULD';
  intent = 'TESLA_WAIT_NOT_CONNECTED';
  reason = 'Planner Tesla deadline-slot actief, maar Tesla/Easee niet verbonden';
}
else if (plannerTeslaDeadlineSlot && deadlineActive && remaining > 0 && (!p1Fresh || !gridMeasurementValid)) {
  priority = 'MAY';
  intent = 'HOLD';
  reason = 'Planner Tesla deadline-slot actief, maar P1 is niet vers/geldig';
}
else if (plannerTeslaDeadlineSlot && deadlineActive && remaining > 0 && !plannerTeslaImportGuardOk) {
  priority = 'MAY';
  intent = 'HOLD';
  reason = `Planner Tesla deadline-slot actief, maar realtime importbudget ${Math.round(discretionaryImportBudgetW)} W is lager dan ${PLANNER_TESLA_MIN_IMPORT_BUDGET_W} W`;
}
else if (deadlineActive && remaining > 0 && existingRealtimeOpportunity) {
  // existing opportunity semantics unchanged
}
```

Exact placement relative to the existing realtime PV/price opportunity branch may be chosen during implementation, but the following invariants are mandatory:

1. MUST catch-up always wins.
2. Planner never bypasses P1 freshness / grid validity.
3. Planner never bypasses connection state.
4. Planner never writes the charger directly.
5. Planner cannot invent a charge when there is no active deadline obligation.
6. Planner cannot increase requested power itself; it only changes the Core decision semantic to deadline charging.

## Power target remains downstream

No new requested-A logic belongs in Core.

When Core emits `TESLA_CHARGE_DEADLINE`, Power Intent v0.2.4 continues to calculate a numeric target from:

```text
remaining_kWh / hours_to_deadline
```

EV Power Adapter v0.1.1 then performs fixed 3×230 V floor quantization, minimum 6 A, configured maximum clamp and fail-closed handling.

The EV Gate and LIVE actuator contracts remain unchanged.

## Observability

Add to `decision.inputs` and/or the relevant published control state:

```js
plannerTesla,
plannerTeslaStart,
plannerTeslaEnd,
plannerTeslaDeadlineSlot,
plannerTeslaDeadlineEligible,
plannerTeslaImportGuardOk,
plannerGeneratedAt: plannerSnap?.generatedAt ?? plannerSnap?.plan?.generatedAt ?? null
```

Add a decision reason that explicitly distinguishes:

- `PLANNER_TESLA_DEADLINE_SLOT_EXECUTED`;
- `PLANNER_TESLA_BLOCKED_IMPORT_BUDGET`;
- `PLANNER_TESLA_BLOCKED_P1`;
- `PLANNER_TESLA_BLOCKED_NOT_CONNECTED`;
- normal `DEADLINE_CATCH_UP`.

A structured `decision.triggerSource` field is preferred if it can be added without breaking downstream schema consumers:

```text
LATEST_START_MUST | PLANNER_DEADLINE_SLOT | REALTIME_OPPORTUNITY | NONE
```

If schema compatibility risk exists, keep the current schema and put the source only in `inputs`/`reason` for v0.11e.

## Planner/UI contract clarification

Planner Shadow is forecast/intention, not proof of execution. The website should eventually expose both layers distinctly:

```text
Planner: preferred Tesla slot
Core: current Tesla decision
Execution: actual Easee state
```

This UI clarification is useful but is not required to deploy Core v0.11e.

## Version metadata

Target flow name:

`EM v2 | 00 Core Tick | v0.11e (Planner Tesla Intent)`

Target publisher version constant:

`EM2_CORE_STATE_V0.11e`

Keep existing state/decision/control schemas unless a schema change is explicitly reviewed.

## No-change contract

v0.11e must not change:

- 5-minute Core cadence;
- existing targeted device set;
- Planner v0.4.9 slot-generation algorithm;
- Tesla deadline input adapter;
- Power Intent numerical target formula;
- EV Adapter W→A mapping;
- EV Gate contract;
- LIVE actuator ownership;
- WW planner semantics or WW thermostat verification behavior;
- Quatt observe-only behavior;
- publisher cadence;
- 19:00 WW hard stop;
- Core physical-write rule: **Core remains read-only**.

## Homey load constraint

This feature must add **zero additional Homey device reads and zero broad Logic scans**. It reuses the Planner snapshot already read by Core.

No new poller is allowed.

## Deployment gate

Do not mutate Homey during preparation.

Before eventual deployment:

1. preserve the then-live v0.11d Core as rollback baseline;
2. implement only the Planner Tesla semantic delta;
3. diff the complete candidate against the live baseline;
4. execute all offline regression scenarios in `smoke-v0.11e-planner-tesla-intent.md`;
5. confirm existing WW thermostat-verification regression remains unchanged;
6. perform one controlled Homey Advanced Flow update;
7. validate naturally with a connected Tesla and an active deadline; no forced physical write is required for the first observation round;
8. stop immediately on Homey rate-limit/throttling; no retry storm.
