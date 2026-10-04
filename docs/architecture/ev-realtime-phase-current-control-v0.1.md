# EV realtime phase/current control v0.1 — production control contract

Status: **DEPLOYED / LIVE**  
Date: 2026-10-04  
Scope: Tesla opportunity charging. Bridge v1.5.8 is live; Adapter/Gate/Writer contracts remain unchanged.

## 1. Problem statement

Production v1.5.3 combined two concerns inside the Homey PI bridge:

1. selection of physical EV phase mode: `OFF | 1P | 3P`;
2. selection of requested charging current.

The former v1.5.3 phase-authority path derived `phaseShadow.requestedA` directly from instantaneous reconstructed available power and then promotes that value through `buildPhaseControl()` when realtime execution is active. A second, older current-regulation calculation also exists later in the bridge (`candidateA`, one-amp up / proportional down), but it is not the authoritative output when a valid phase selector result exists.

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

Deadline charging remains a separate hard-constraint path and is unchanged by v1.5.4.

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

Production v1.5.8 splits the former unified upward/re-entry dwell:

- `OFF -> 1P/3P`: **120 seconds** since the last mode change;
- `1P -> 3P`: **180 seconds** since entry into 1P.

The 120-second time-weighted signal with at least 90 seconds coverage remains mandatory before either upward transition. Instantaneous minimum-current viability is still checked separately. The shorter timers therefore do not replace the rolling anti-flap filter; they remove the additional five-minute hold that live 2026-10-04 telemetry showed could leave several kilowatts of recovered PV exporting.

Sustained downward transitions (`3P -> 1P`, `3P -> OFF`, `1P -> OFF`) remain allowed as soon as the rolling condition is confirmed and are not held behind either upward dwell. Ordinary current corrections inside 1P or 3P are not phase-dwell limited.

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

The regulator reconstructs the expected grid effect from the selected current:

```text
synthetic_p1_w = requested_ev_w - available_total_w
```

The 250 W `EVPC_IMPORT_DEADBAND_W` remains the phase-entry/minimum-viability margin. For same-phase current control, v1.5.8 aligns down-regulation with the configured import preference:

```text
current_import_limit_w = max(250 W, 300 W) = 300 W
```

If predicted import exceeds 300 W, current is reduced immediately by enough whole amps to return within that limit. This avoids a control fight in which the upscale regulator intentionally chooses a target up to +300 W import but the down-regulator would immediately undo it above +250 W.

### Up-regulation

Same-phase current uses the physical Easee offered current plus confirmed phase to reconstruct EV load and computes:

```text
desired_a = floor((available_total_w + 300 W) / watts_per_amp)
```

The target is bounded by the Pi envelope/maxA and 6..16 A device range. A further upscale is permitted only after the physical Easee target has settled to the controller's previous request. Each settled control step remains bounded to:

- maximum +3 A in 1P;
- maximum +2 A in 3P.

This preserves the v1.5.7 physical-feedback protection while allowing the controller to prefer modest import over avoidable PV export. At 3P, for example, 8→9 A becomes eligible at approximately 5910 W available power, corresponding to at most about +300 W predicted import at the discrete 690 W/A step.

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

Production v1.5.3 used:

- 120-second rolling only for 1P -> OFF;
- instantaneous available power for 1P -> 3P and 3P -> 1P;
- 120-second mode dwell.

Production v1.5.4 makes all phase transitions use the same 120-second sustained signal and uses a 300-second upward/re-entry dwell, while allowing A to continue adapting within both 1P and 3P.

Expected result:

- fewer physical 1P/3P transitions on broken-cloud days;
- fewer Easee pause/resume cycles;
- current still follows available PV;
- import correction remains faster than phase switching.

## 8. Production implementation

The pure implementation lives at:

`src/homey/ev/ev-phase-current-controller-v0.1.mjs`

It is deliberately control-neutral:

- no Homey API calls;
- no Logic writes;
- no device writes;
- no Easee Cloud calls;
- no adapter/gate/writer changes;
- an **applied deadline force** returns `BYPASS` because hard deadline authority remains outside opportunity control; an active deadline before `forceFrom` remains eligible for normal PV opportunity charging.

The reference controller persists only pure controller state supplied by its caller:

- current mode and mode-since timestamp;
- requested current;
- upscale-confirmation timestamp;
- bounded rolling available-power samples.

Unit tests live at:

`tests/ev-phase-current-controller-v0.1.test.mjs`

The tests cover 1P and 3P current regulation separately from physical phase transitions.

Bridge integration source:

`apps/homey/control/ev/pi-dynamic-planner-bridge-v1.5.8.production-tuned.js`

The HomeyScript bridge cannot import the ESM reference module directly, so the production bridge carries the controller logic inline. The bridge keeps the existing `EM2_EV_PHASE_CONTROL_V0.1` Adapter/Gate contract unchanged. The former parallel `candidateA` calculation is removed; compatibility fields `realtime.candidateA/candidateW` are now aliases of the single combined controller result only.

Structural integration tests live at:

`tests/control/ev/ev-phase-current-bridge-v1.5.8.test.mjs`

## 9. v1.5.8 production promotion

The 2026-10-04 tuning is a direct production change on the existing stable Bridge flow ID; it does not introduce a shadow controller or second writer. The reason is evidence from live minute telemetry: once a phase/current target was settled, v1.5.7 regulated close to zero grid power, while the former 300-second upward dwell left material export during fast PV recovery. The change therefore targets the identified bottleneck rather than broadening the control architecture.

Production acceptance requires:

- repository structure and architecture gates PASS;
- v1.5.8 HomeyScript compile/regression PASS;
- existing v1.5.7/controller and writer regressions remain PASS;
- exact existing Advanced Flow cards/ID preserved;
- one targeted pre-read, one write and one targeted read-back;
- `policyRevision=PI_DYNAMIC_PLANNER_BRIDGE_V1.5.8_PRODUCTION_TUNED`;
- Adapter/Gate remain valid/PASS and no second physical writer appears;
- natural post-deploy operation remains bounded by the existing Pi envelope and deadline force.

Rollback is the exact pre-deploy writable Bridge body captured before the single Homey update.

