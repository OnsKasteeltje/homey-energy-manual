# EV realtime phase/current control v0.1 — design and replay contract

Status: ANALYSIS / SHADOW ONLY  
Date: 2026-10-02  
Scope: Tesla opportunity charging only. No production bridge, adapter, gate or actuator change in this branch.

## 1. Problem statement

Production currently combines two concerns inside the Homey PI bridge:

1. selection of physical EV phase mode: `OFF | 1P | 3P`;
2. selection of requested charging current.

The production phase-authority path derives `phaseShadow.requestedA` directly from instantaneous reconstructed available power and then promotes that value through `buildPhaseControl()` when realtime execution is active. A second, older current-regulation calculation also exists later in the bridge (`candidateA`, one-amp up / proportional down), but it is not the authoritative output when a valid phase selector result exists.

This makes diagnosis harder and allows fast PV/cloud variation to influence both physical phase changes and current changes.

The control model must therefore separate:

- a slow physical phase state machine;
- a faster current regulator that operates inside the selected phase.

## 2. Ownership

The ownership boundary remains unchanged:

- Pi Dynamic Planner: strategic 15-minute opportunity/deadline envelope;
- Homey PI bridge: realtime opportunity execution within that envelope;
- EV Adapter/Gate: translation and validation;
- EV phase writer: sole physical writer to Easee;
- Easee/Tesla: physical execution and telemetry.

No new writer is introduced.

Deadline charging remains a separate hard-constraint path and is not changed by this proposal.

## 3. Canonical realtime signal

P1 remains authoritative.

For opportunity control:

```text
available_total_w = max(0, -p1_w + ev_actual_w)
```

where:

- Homey P1 convention is import positive, export negative;
- `ev_actual_w` is the measured EV charging load;
- adding the EV load back reconstructs the counterfactual surplus before EV consumption.

This prevents the controller from interpreting its own EV load as disappearing PV surplus.

The existing freshness/fail-closed rules remain mandatory. This design does not relax stale-input policy.

## 4. Phase selector — slow state machine

The phase selector owns only `OFF | 1P | 3P`. It does not own current steps.

Candidate thresholds remain aligned with the existing policy:

| Transition | Condition |
|---|---:|
| OFF -> 1P | rolling available >= 1500 W |
| OFF -> 3P | rolling available >= 4400 W |
| 1P -> 3P | rolling available >= 4400 W |
| 3P -> 1P | rolling available < 3600 W and >= 1500 W |
| 3P -> OFF | rolling available < 1500 W |
| 1P -> OFF | rolling available < 1100 W |

The rolling signal is the trailing 120-second **time-weighted** mean of valid `available_total_w` samples.

For a control decision to be called "sustained", the rolling window must contain enough valid history to cover at least 90 seconds. A replay with insufficient source resolution must report that limitation instead of fabricating sub-minute data.

An upward phase entry also requires the **current instantaneous** reconstructed power to sustain the physical 6 A minimum within the existing 250 W import deadband. A high rolling value alone may therefore not force a new 1P/3P entry during a fresh cloud dip.

### Dwell

The candidate uses a 300-second dwell for **upward/re-entry** transitions (`OFF -> 1P/3P` after a recent stop and `1P -> 3P`).

Sustained downward transitions (`3P -> 1P`, `3P -> OFF`, `1P -> OFF`) are allowed as soon as the 120-second rolling condition is confirmed. They are deliberately not held behind the 300-second dwell: otherwise a cloud dip directly after an upshift could leave 3P stuck at its 6 A minimum and intentionally import for several minutes.

The dwell never blocks ordinary current corrections inside 1P or 3P.

The 300-second value is a candidate validation setting, not yet a production constant.

## 5. Current regulator — fast control inside both phases

The current regulator owns `requestedA` once the phase selector has selected 1P or 3P.

Physical mapping:

```text
1P: 230 W/A
3P: 690 W/A
range: 6..16 A, additionally bounded by the Pi realtime envelope/maxA
```

The regulator never changes phase and never decides OFF. OFF is phase-selector ownership.

### Down-regulation

Down-regulation reacts quickly to real import.

Estimate the candidate grid effect using the currently requested EV target:

```text
synthetic_p1_w = requested_ev_w - available_total_w
```

If:

```text
synthetic_p1_w > 250 W
```

reduce current immediately by enough whole amps to remove the excess import above the 250 W deadband:

```text
reduction_a = ceil((synthetic_p1_w - 250) / watts_per_amp)
```

The current regulator may reduce only to the physical 6 A minimum while the selected mode remains active. If power is not sustainable at 6 A, the phase selector performs the relevant 3P->1P or 1P->OFF transition on its slower rolling signal.

### Up-regulation

Up-regulation is deliberately slower.

A +1 A step is allowed only when at least one additional amp of export headroom has been continuously available for 45 seconds:

```text
synthetic_p1_w <= -watts_per_amp
```

Then:

```text
requestedA := requestedA + 1
```

and the confirmation timer starts over.

Any loss of that headroom resets the upscale confirmation timer.

The 45-second value is a candidate validation setting.

### Same-phase changes

A current-only change in the same phase must not invoke the writer's physical phase transition sequence. It must not cause pause -> phase command -> deadtime -> resume.

A physical pause/resume transaction is reserved for a real `OFF/1P/3P` mode change or an existing safety path.

## 6. Deadline path

Deadline behavior remains unchanged:

```text
deadline force active
  -> 3P
  -> deadline requested A
  -> opportunity phase/current hysteresis does not stop the charge
```

All existing deadline max-current, connectivity, freshness and fail-closed rules remain in force.

## 7. Why this addresses the 2026-10-02 behavior

The observed midday behavior showed repeated charging pauses while the requested charging current generally remained positive.

That is consistent with physical 1P/3P transition handling rather than repeated opportunity OFF decisions.

Production currently uses:

- 120-second rolling only for 1P -> OFF;
- instantaneous available power for 1P -> 3P and 3P -> 1P;
- 120-second mode dwell.

The candidate makes all phase transitions use the same 120-second sustained signal and raises phase dwell to 300 seconds, while allowing A to continue adapting within both 1P and 3P.

Expected result:

- fewer physical 1P/3P transitions on broken-cloud days;
- fewer Easee pause/resume cycles;
- current still follows available PV;
- import correction remains faster than phase switching.

## 8. Candidate implementation

The pure implementation lives at:

`src/homey/ev/ev-phase-current-controller-v0.1.mjs`

It is deliberately control-neutral:

- no Homey API calls;
- no Logic writes;
- no device writes;
- no Easee Cloud calls;
- no adapter/gate/writer changes;
- deadline path returns `BYPASS` because deadline authority remains outside opportunity control.

The candidate persists only pure controller state supplied by its caller:

- current mode and mode-since timestamp;
- requested current;
- upscale-confirmation timestamp;
- bounded rolling available-power samples.

Unit tests live at:

`tests/ev-phase-current-controller-v0.1.test.mjs`

The tests cover 1P and 3P current regulation separately from physical phase transitions.

## 9. Validation gates before any LIVE work

This branch is analysis-only and must not be deployed to Homey.

Before a later production integration is prepared, all of the following must be true:

- Node unit tests PASS;
- repository architecture gate PASS;
- OFF/1P/3P thresholds remain aligned with the Pi policy contract;
- current-only changes keep `requiresPhysicalPhaseTransition=false`;
- proportional import down-regulation is proven in both 1P and 3P;
- +1 A upscale confirmation is proven in both 1P and 3P;
- sustained downward phase transitions cannot be trapped behind the 300 s upward dwell;
- deadline requests remain outside this opportunity controller;
- stale/invalid inputs fail closed;
- no Adapter/Gate/Writer semantics are changed on this analysis branch.

The existing 2026-10-02 five-minute Pi history is too coarse to validate a 120-second controller retrospectively. That limitation is noted, but no new observability or history subsystem is part of this focused change.
