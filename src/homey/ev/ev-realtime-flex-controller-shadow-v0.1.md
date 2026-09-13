# EV Realtime Flex Controller v0.1 — SHADOW design

Status: **DESIGN / SHADOW / NOT CONNECTED TO PRODUCTION CONTROL**

Date: 2026-09-13

## Purpose

Add a bounded, local Homey realtime control layer for Tesla PV-opportunity charging while preserving the Raspberry Pi as strategic planner and `EM2_Planner_Authority` as the single planner-authority selector.

The controller solves a gap observed in production on 2026-09-13: the Pi planner can correctly build a 15-minute strategic plan but `/control/current` only projects the current slot. If actual P1 export changes materially inside that slot, Homey currently continues executing the fixed slot target and cannot consume newly available PV until a later planner rebuild/slot decision.

This controller is **not a second planner**. It may only optimize Tesla current inside an explicit Pi-provided realtime envelope.

## Ownership model

Strategic ownership remains:

```text
Forecasts + history + live state + FIXED contract policy
        -> Pi dynamic planner
        -> /control/current
        -> Homey PI Bridge
```

Realtime execution becomes:

```text
Pi control envelope
        -> Homey EV Realtime Flex Controller
        -> EM2_Power_Intent
        -> EV Adapter
        -> EV Gate
        -> EV Actuator
        -> Easee
```

Responsibilities:

### Pi planner

- 24-hour / 15-minute strategic planning;
- WW comfort and deadline feasibility;
- Tesla deadline feasibility;
- fixed-contract policy;
- whether realtime EV opportunity modulation is permitted;
- lower/upper EV execution bounds;
- command validity / fail-closed metadata.

### Homey realtime controller

- local P1 signal conditioning;
- EV self-load correction;
- bounded 6..N A modulation;
- start/run hysteresis and anti-flapping;
- immediate fail-closed behaviour when the Pi envelope becomes invalid;
- no forecast planning, contract switching or WW rescheduling.

### Existing safety chain

EV Adapter, EV Gate and EV Actuator remain authoritative for executable mapping and physical safety. The realtime controller performs no direct Easee writes.

## Required Pi contract extension

The current `EMS_PI_CONTROL_COMMAND_V0.1` exposes an exact EV target. That target must not silently be reinterpreted as permission for Homey to override `0 A`.

Promotion therefore requires a versioned control-envelope extension. Proposed EV fields:

```json
{
  "targets": {
    "ev": {
      "target_W": 0,
      "target_A": 0,
      "reason": "NO_QUALIFIED_PV_WINDOW",
      "realtime": {
        "allowed": false,
        "mode": "OFF|PV_OPPORTUNITY|DEADLINE",
        "min_A": 0,
        "max_A": 0,
        "deadline_max_A": 8
      }
    }
  }
}
```

Semantics:

- `allowed=false` -> realtime controller output must be 0 A;
- `PV_OPPORTUNITY` -> Homey may choose only within `min_A..max_A`;
- `DEADLINE` -> planner/deadline policy remains authoritative; realtime PV optimization may not reduce charging below the deadline-required floor;
- missing, stale or invalid envelope -> fail closed;
- `max_A` may never exceed the planner/deadline safety limit or hardware safety chain;
- WW reservation/priority is already reflected by the Pi envelope and must not be independently rescheduled by Homey.

Until this extension exists, SHADOW may calculate hypothetical targets but must not alter `EM2_Power_Intent`.

## Realtime input model

Reuse the validated concept from `EV Surplus Smoother v0.1`:

```text
EV_surplus_raw_W = max(0, -P1_W + EV_actual_W)
```

Sign convention:

- negative P1 W = export;
- positive P1 W = import;
- `EV_actual_W >= 0`.

Adding EV actual power back reconstructs the counterfactual surplus before the Tesla load and prevents controller self-feedback after charging starts.

Do **not** add WW actual power back. WW is an independently planned/reserved load and remains part of actual household consumption unless a future explicit contract says otherwise.

If P1 or EV actual power is stale/degraded while the Tesla is active, fail closed or hold only according to an explicitly validated safety rule; never guess EV power.

## Signal conditioning

Initial SHADOW policy:

- input: event-driven Homey P1 `measure_power` changes;
- no broad recurring `getDevices()` / `getVariables()` scans;
- rolling window: 120 s;
- statistic: arithmetic mean;
- semantic evaluation: at most once per 120 s;
- existing EV start/stop anti-flap remains separate and unchanged.

The 120-second value is an initial validation setting inherited from the earlier smoother design, not yet a permanent production constant.

## Current calculation

For SHADOW comparison, use the smoothed counterfactual EV surplus and the current Pi envelope.

Nominal 3-phase mapping remains consistent with current EMS semantics:

```text
EV_W_PER_A = 690 W/A
```

Candidate current:

```text
candidate_A = floor(smoothed_surplus_W / 690)
```

Then clamp:

```text
requested_A = clamp(candidate_A, envelope.min_A, envelope.max_A)
```

START6/RUN6 semantics:

- if opportunity is allowed and executable surplus supports at least 6 A, candidate may start at 6 A;
- while running, controller may modulate 6..max A;
- below the validated stop boundary, existing start/stop anti-flap decides physical stop timing;
- no direct actuator write from this layer.

The exact up/down hysteresis bands must be derived from SHADOW replay before promotion. A current change should require a material boundary crossing; one-amp oscillation around a threshold must not cause repeated device writes.

## Relationship to the Pi slot target

The 15-minute Pi target remains the strategic baseline and observability reference.

During SHADOW record both:

- `piSlotTargetA` / `piSlotTargetW`;
- `realtimeCandidateA` / `realtimeCandidateW`.

A realtime candidate may only become executable after the Pi command explicitly carries `realtime.allowed=true` and bounds. This prevents Homey from turning a strategic planner `0 A` into an unauthorized charge session.

## Deadline behaviour

Deadline remains a hard constraint.

Rules:

1. before the Pi/deadline policy permits forcing, realtime controller may only use PV-opportunity envelope;
2. when deadline mode is active, Homey must honor the planner/executor deadline floor and `deadline_max_A`;
3. realtime PV logic may raise current only inside the allowed deadline envelope;
4. realtime PV logic may never lower below a deadline-required current;
5. stale/invalid deadline metadata fails closed according to the existing bridge/gate safety contract.

## Fail-closed conditions

SHADOW must flag, and production promotion must fail closed on at least:

- `EM2_Planner_Authority != PI` for the Pi-envelope path;
- `/control/current` not READY;
- command/envelope expired;
- contract not `FIXED / ENGIE_3Y_2026_2029`;
- envelope schema invalid or bounds inconsistent;
- Tesla disconnected;
- P1 stale/unavailable;
- EV actual power stale/unavailable while needed for self-load correction;
- current adapter/gate/actuator safety contract not PASS.

## SHADOW output proposal

```json
{
  "schema": "EM2_EV_REALTIME_FLEX_SHADOW_V0.1",
  "generatedAt": "ISO-8601",
  "mode": "SHADOW",
  "piSlotTargetA": 0,
  "piSlotTargetW": 0,
  "envelopeAllowed": false,
  "envelopeMinA": 0,
  "envelopeMaxA": 0,
  "p1W": 0,
  "evActualW": 0,
  "counterfactualSurplusW": 0,
  "smoothedSurplusW": 0,
  "candidateA": 0,
  "candidateW": 0,
  "quality": "GOOD|DEGRADED|STALE|BLOCKED",
  "reason": "...",
  "deviceWrites": false
}
```

## Validation scenarios

At minimum replay/observe:

1. Tesla stopped, stable export > 4140 W -> candidate starts at 6 A when envelope permits;
2. Tesla already charging -> adding EV actual W prevents false surplus collapse;
3. surplus supports 7/8/9 A -> candidate steps upward without planner rebuild;
4. short cloud dip < 2 min -> no unnecessary stop/restart;
5. sustained deficit -> safe down-regulation and eventual stop;
6. Pi envelope changes allowed -> blocked while charging -> controller obeys immediately/fail-closed;
7. WW active -> WW consumption remains in P1 and is not added back;
8. active deadline -> realtime logic never violates required floor/max;
9. stale P1 or EV power -> no guessed target;
10. Homey load budget -> no 429 and adequate operational headroom.

## Promotion criteria

Do not connect SHADOW output to `EM2_Power_Intent` until all are true:

- Pi envelope schema is implemented and versioned;
- current PI Bridge validates and projects the envelope;
- SHADOW shows improved PV capture versus fixed-slot execution;
- EV self-load correction is proven live;
- cloud/threshold behaviour does not create excess writes;
- no Homey 429 during soak;
- deadline and WW regression tests pass;
- START6/RUN6 mapping remains consistent through Adapter/Gate/Actuator;
- rollback to current exact-target behaviour is one selector/config change;
- documentation is updated to make Pi strategy / Homey bounded realtime ownership explicit.

## Non-goals

This controller must not:

- become a second 24-hour planner;
- choose WW schedule;
- choose contract mode or use dynamic prices for production;
- control Victron/battery;
- bypass `EM2_Power_Intent`, EV Adapter, EV Gate or EV Actuator;
- write Easee directly.
