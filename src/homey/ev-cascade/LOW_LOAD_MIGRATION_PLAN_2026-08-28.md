# EV cascade LOW-LOAD migration plan — 2026-08-28

Status: **PREP ONLY — no Homey runtime promotion performed**

## Goal

Remove broad `Homey.logic.getVariables()` collection reads from the event-driven EV chain while preserving the existing schemas, revision guards, fail-closed behavior, SHADOW/LIVE ownership boundaries and observability.

Current cascade:

```text
Core
  -> EM2_Control_WW / policy outputs
      -> Power Intent
          -> EM2_Power_Intent
              -> P1 Pre-EV Gate
              -> EV Power Adapter
              -> EV Adapter Gate (+2 s)
                   -> EM2_EV_Adapter_Gate
                       -> EV Power Actuator
                       -> EV Control Status
```

The canonical load map currently estimates the upstream Power Intent / Gate / Adapter / Gate part at roughly four full Logic collection enumerations per Core revision, or about 48 full Logic enumerations/hour at a five-minute Core cadence. The migration target is **zero full Logic enumerations in this cascade**.

## Target architecture

Each stage must:

1. be event-driven on its existing authoritative upstream variable;
2. use only `Homey.logic.getVariable({id})` for explicitly required inputs;
3. update only existing output/status variables by known ID;
4. retain semantic idempotency by source revision/schema/target;
5. perform no `getDevices()` unless the existing LIVE actuator safety path explicitly requires a charger read;
6. perform no Insights calls;
7. never add an independent polling clock;
8. fail closed when any required targeted variable cannot be read or revisions do not align.

## Migration units

### A. Power Intent — target v0.2.3 LOW-LOAD

Source baseline available in GitHub: `src/homey/power-intent/p1-v0.2.1.js`.
Runtime is known to be ahead at v0.2.2 (`Public decoupled`), so **runtime capture is required before promotion**. Do not overwrite current Homey code from the older GitHub v0.2.1 baseline.

Broad read to remove:

```js
await Homey.logic.getVariables()
```

Required targeted inputs, based on current policy contract:

- `EM2_State`
- `EM2_Decision`
- `EM2_Control_WW`
- `EM2_Power_Intent` (previous output for idempotency)
- any v0.2.2-specific input discovered during runtime capture

Required targeted output:

- `EM2_Power_Intent`

`EM2_Public_State` must **not** be reintroduced if v0.2.2 has already decoupled from it.

### B. P1 Pre-EV Gate — target v0.3 LOW-LOAD

Exact runtime source is not yet captured in GitHub. Runtime capture is required before code generation.

Expected targeted inputs from current contract:

- `EM2_Power_Intent`
- `EM2_State`
- any current gate-local cache/status input actually used by runtime code

Expected targeted output:

- `EM2_P1_PreEV_Gate`

Preserve current status vocabulary and compact single-JSON runtime-health output. Do not restore removed typed mirrors/counters.

### C. EV Power Adapter — target v0.2 LOW-LOAD

Exact GitHub runtime baseline is captured at `src/homey/adapters/ev-power/ev-power-v0.1-shadow.runtime.md`.

Broad read to remove:

```js
await Homey.logic.getVariables()
```

Required targeted inputs from captured code:

- `EM2_Power_Intent`
- `EM2_State`
- `EM2_EV_Power_Adapter` (previous output/idempotency)
- `EV Max laadstroom A`

Required targeted output:

- `EM2_EV_Power_Adapter`

All electrical semantics must remain unchanged: fixed 3×230 V, floor quantization, 6 A minimum, configured maximum clamped to 16 A, freshness checks, no device/network reads, fail closed.

### D. EV Adapter Gate — target v0.3 LOW-LOAD

Exact runtime source is not yet captured in GitHub. Runtime capture is required before code generation.

Expected targeted inputs from current safety contract:

- `EM2_Power_Intent`
- `EM2_EV_Power_Adapter`
- `EM2_State`
- possibly `EM2_P1_PreEV_Gate` if current runtime uses it directly
- current gate previous output/cache if used for semantic idempotency

Expected targeted output:

- `EM2_EV_Adapter_Gate`

Preserve exact revision coherence fields consumed by the LIVE actuator: `sourceRevision`, `intentRevision`, `stateRevision`, `coreRevision` and current final PASS/FAIL vocabulary.

### E. EV Actuator / EV Control Status — review only

These are downstream of the four primary collection-read stages. The load map says they still perform one `getVariables()` per event. They are not part of the first promotion unit because the actuator is safety-critical and the current LIVE=false path is already low impact.

After A-D are stable, prepare a second migration unit for targeted reads here. Do not couple actuator refactoring to the first smoke.

## Expected load reduction

At 12 Core revisions/hour, replacing four collection enumerations with targeted reads removes approximately **48 full Logic collection enumerations/hour** from the normal EV cascade. The number of individual targeted variable reads will rise, but they are bounded and proportional to actual dependencies rather than the total Logic-variable inventory.

## Promotion sequence

Use one tightly controlled stage at a time:

1. capture current Homey runtime source and variable IDs for Power Intent;
2. generate exact v0.2.3 LOW-LOAD source in GitHub;
3. deploy Power Intent only, one natural event + targeted smoke, PASS/FAIL;
4. repeat for P1 Pre-EV Gate;
5. repeat for EV Power Adapter;
6. repeat for EV Adapter Gate;
7. observe at least several natural Core cycles with no `Too many requests`;
8. only then consider actuator/observability targeted-read migration.

If any Homey API call returns `Too many requests`, stop immediately. Do not retry in a loop.

## Runtime data still required

The following cannot be safely inferred from repository contents and must be captured from Homey before deployment:

- exact v0.2.2 Power Intent runtime code;
- exact P1 Pre-EV Gate runtime code;
- exact EV Adapter Gate runtime code;
- Logic variable IDs for every required input/output not already source-managed;
- confirmation of enabled/broken/trigger topology for each flow;
- any v0.2.2/v0.2 Gate fields added after the current GitHub baselines.

This is intentionally a GitHub-first preparation branch. No Homey runtime change is part of this commit.