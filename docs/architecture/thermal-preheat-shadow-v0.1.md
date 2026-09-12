# PV thermal preheat — shadow architecture v0.1

Status: **PREPARED / PURE_SHADOW / NOT DEPLOYED / NO HONEYWELL WRITES / NO OPENTHERM CONTROL**  
Date: 2026-09-12

## Purpose

Prepare the EMS to learn whether otherwise-exported PV can be used to preheat rooms with the Quatt before the normal Honeywell Multizone comfort schedule raises the room target.

This preparation deliberately does **not** implement control. It defines ownership, telemetry, modelling boundaries, safety invariants and the future planner interface so data collection and shadow analysis can be added without creating a second history platform or increasing Homey load unnecessarily.

## Non-negotiable ownership boundaries

1. **Honeywell Multizone is comfort authority.** It owns zones, normal schedules, room targets and the normal heat-demand semantics.
2. **The OpenTherm connection between Honeywell and Quatt is untouched.** The EMS must not intercept, rewrite, spoof or otherwise control OpenTherm messages.
3. **Quatt remains the heat-production executor.** The EMS observes direct Quatt data where available; it does not introduce an alternative heat-control path.
4. **The Pi is the optimizer/model host.** Thermal opportunity calculation belongs beside the existing Pi planner and uses the same canonical history and forecasts.
5. **Homey remains the guarded execution layer.** No new broad Homey polling is part of this preparation.
6. Any future Honeywell setpoint adjustment requires a separately validated, supported Honeywell interface and an explicit later authorization/cutover. This v0.1 contains no such writer.

## Observed operating behaviour to model

Empirical household behaviour is that a small/gradual increase of a room target relative to current room temperature can result in Quatt-only heating, while a larger temperature difference can cause the gas boiler to assist immediately.

The EMS must therefore learn an operating envelope rather than encode one fixed delta-temperature threshold.

Primary quantity to learn:

`P(CV_ASSIST | zone, target_minus_room_temp, outside_temp, recent_heat_state, time_since_demand, ...)`

A future opportunity is acceptable only when the predicted CV-assist risk is below a validated threshold. The threshold is intentionally not defined in this preparation.

## Resource priority

Thermal preheat is a residual-flex consumer. The intended allocation order is:

`house/base demand -> WW -> Tesla -> thermal preheat -> grid export`

Thermal preheat may consume only PV surplus that remains after higher-priority flexible loads have been satisfied or are unavailable.

This is an allocation rule, not a new independent realtime optimizer.

## Proposed modules

### 1. thermal-observer

Read-only normalizer. Produces a coherent thermal observation from canonical telemetry.

Responsibilities:
- normalize room temperature and target per zone;
- retain source/freshness/quality metadata;
- associate direct Quatt power/status and CV-assist evidence;
- associate outdoor temperature and net P1 import/export;
- associate planner claims for WW and EV;
- never write a setpoint or device capability.

### 2. thermal-model

Read-only model fitted from historical observations.

First useful outputs:
- room heating/cooling rate by zone;
- thermal inertia / loss approximation;
- expected room temperature at the next Honeywell comfort transition;
- Quatt-only probability / CV-assist probability for candidate target deltas;
- confidence and sample support.

A first-order thermal model is sufficient as a baseline:

`dT_room/dt = a*(T_out - T_room) + b*P_Quatt + c*Q_solar_internal`

The implementation may later use a richer model if replay evidence justifies it, but the output contract should remain deterministic and explainable.

### 3. thermal-opportunity-planner

PURE_SHADOW candidate generator. It evaluates whether residual PV surplus could be shifted into building thermal mass before an already-scheduled Honeywell comfort increase.

Hard candidate constraints:
- next Honeywell scheduled target is known and fresh;
- candidate target never exceeds that next scheduled target;
- residual PV surplus is positive after WW/EV claims;
- Quatt data is fresh enough to support the model;
- no observed CV assist is active;
- required inputs are not stale/estimated beyond configured tolerances;
- output has `executeAllowed=false` in shadow phases.

### 4. future thermal-intent-adapter

**Not part of v0.1 implementation.**

If shadow validation later succeeds, a separate adapter may translate an approved thermal intent into a small, time-limited Honeywell setpoint adjustment through a supported Honeywell interface. It must be independently guarded and revocable.

It may never write or manipulate OpenTherm.

## Canonical history: extend, do not duplicate

The Pi already has a canonical SQLite history at `/home/jeroen/ems/data/ems-history.sqlite` with a generic `devices` / `metrics` / `measurements` structure. Existing `import_em2_day_history.py` imports Homey day-history samples into that store and records quality plus source resolution.

Thermal data should use the same store and conventions. Do **not** introduce a second thermal history database as the primary source.

The companion machine-readable preparation contract is:

`src/pi/ems-runtime/datastore/thermal-telemetry-contract-v0.1.json`

It defines candidate devices, metrics, quality requirements and event semantics without changing the live schema.

## Minimum telemetry needed for learning

Per zone:
- current room temperature;
- current Honeywell target;
- next scheduled target;
- timestamp of next scheduled target;
- zone heat-demand/active state if available without broad polling.

Heat production:
- direct Quatt electrical power where available;
- Quatt active/status indication;
- CV/gas-boiler assist indication;
- preferably a direct signal rather than inference where available.

EMS context:
- P1 net import/export;
- aggregate PV production and/or constituent inverter production;
- outdoor temperature;
- WW state/power and current planner claim;
- Tesla connected/charging/power and current planner claim;
- planner revision / model revision for any generated shadow recommendation.

Every measurement used for fitting must retain source, timestamp, resolution and quality. Missing fields remain missing; they must not silently be converted to zero.

## Events

Continuous measurements alone are insufficient for causal analysis around heat-demand transitions. The canonical telemetry layer should also preserve, or derive reproducibly, events such as:

- `ROOM_SETPOINT_CHANGED`
- `HONEYWELL_SCHEDULE_TRANSITION`
- `QUATT_STARTED`
- `QUATT_STOPPED`
- `CV_ASSIST_STARTED`
- `CV_ASSIST_STOPPED`
- `PV_SURPLUS_STARTED`
- `PV_SURPLUS_ENDED`
- `ROOM_TARGET_REACHED`

An event store may be an additive table/file inside the canonical history subsystem, but it must not become a second competing telemetry platform. Event derivation rules and revisions must be versioned.

## Suggested sampling and retention

Thermal dynamics are slow compared with P1. For model input a 60-second normalized thermal sample is likely sufficient, while native faster measurements may remain available where already collected.

This is a target, not an instruction to poll Homey every minute. Prefer Pi-local/direct sources or existing compact publications. When a source only exists at lower frequency, store the true source resolution and quality rather than fabricating 60-second observations.

Retain enough high-resolution history to cover multiple weather regimes. A practical initial target is at least one heating season. Aggregation may be added for long-term reporting, but raw model features around setpoint/Quatt/CV transitions must not be discarded prematurely.

## Shadow recommendation contract

A future shadow output should be self-contained and explicitly non-executable, for example:

```json
{
  "schema": "EMS_THERMAL_PREHEAT_SHADOW_V0.1",
  "generatedAt": "2026-11-03T13:30:00+01:00",
  "mode": "PURE_SHADOW",
  "executeAllowed": false,
  "zone": "living_room",
  "currentRoomTemp_C": 18.1,
  "currentTarget_C": 17.5,
  "nextScheduledTarget_C": 20.0,
  "nextScheduledTargetAt": "2026-11-03T17:00:00+01:00",
  "candidateTarget_C": 18.4,
  "residualPvSurplus_W": 1600,
  "quattOnlyProbability": 0.97,
  "cvAssistProbability": 0.02,
  "reason": "RESIDUAL_PV_BEFORE_EXISTING_COMFORT_TRANSITION",
  "modelRevision": "untrained-v0",
  "inputRevision": "..."
}
```

The example values are illustrative only and are not production thresholds.

## Fail-closed rules for future phases

A thermal opportunity must resolve to no action when any of the following applies:
- Honeywell schedule/target is unknown or stale;
- candidate target would exceed the next scheduled Honeywell comfort target;
- CV assist is active or its status is unknown when the policy requires confirmation;
- residual PV is no longer available;
- WW or EV has a higher-priority claim on the same surplus;
- Quatt/room/outdoor inputs are stale beyond accepted limits;
- planner/model output is expired;
- authority/writer ownership is ambiguous.

Loss of telemetry must never create a heating command.

## Rollout phases

### T0 — telemetry gap analysis
No control. Confirm which required fields already exist in canonical Pi history and which source adapters are still needed.

### T1 — passive collection
Persist thermal observations/events only. No recommendation and no setpoint write.

### T2 — model learning
Fit/replay per-zone thermal response and Quatt-only/CV-assist envelope. No recommendation write to Homey.

### T3 — PURE_SHADOW opportunity replay
Generate recommendations with `executeAllowed=false`; compare predicted room trajectory, actual evening heat demand, PV export avoided in counterfactual replay, and false-positive CV-assist risk.

### T4 — guarded shadow publication
Optionally publish compact read-only status/evidence for observability. Do not reintroduce broad Homey polling.

### T5 — future controlled execution
Out of scope until explicitly authorized. Requires a supported Honeywell write interface, independent safety gate, rollback, idempotency, TTL, small bounded steps, and verified non-interference with Honeywell schedules. OpenTherm remains untouched.

## Validation criteria before any execution discussion

At minimum:
- sufficient samples per zone and outside-temperature band;
- repeatable Quatt-only envelope estimates;
- explicit false-positive rate for predicted Quatt-only operation;
- replay shows positive PV self-consumption gain after thermal losses;
- no hidden increase in gas/CV use in shadow counterfactuals;
- comfort at normal Honeywell schedule transition is not degraded;
- all recommendations are explainable from stored inputs and model revision;
- zero physical writes during T0–T4.

## Homey-load rule

This preparation intentionally makes no Homey API changes. Future collection should prefer already-published state, existing targeted Insights collection, or direct Pi/device sources. Any new Homey read must be targeted and justified; do not add `getDevices()` / `getVariables()` broad polling loops for thermal modelling.

## Relationship to Pi source-of-truth rule

`src/pi/README.md` states that accepted planner logic is changed/tested first in the active Pi runtime and only then synchronized to GitHub. Therefore this repository change is architecture/data-contract preparation only. It does not introduce active planner logic ahead of the Pi runtime and must not be interpreted as deployment authorization.
