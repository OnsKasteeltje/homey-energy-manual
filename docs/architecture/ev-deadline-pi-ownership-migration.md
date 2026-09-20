# EV deadline Pi ownership — migration preparation

Status: **AUTHORITY CUTOVER COMPLETE — PI DEADLINE OWNER, HOMEY EXECUTOR/SAFETY**

## Objective

Remove the historical first Homey deadline-processing hop while preserving Homey as the realtime executor, validation boundary and sole automatic Easee writer.

Target responsibility split:

- Homey Core owns physical observations.
- Pi owns deadline command lifecycle and derived planning state.
- Homey executor owns realtime validation, exact-minute deadline safety and physical actuation.

## Canonical telemetry prerequisite

Homey Core already reads the cumulative Easee energy counter as `state.tesla.meterKWh` and already includes it in Core semantic change detection. Schema 2.13 permits additive Tesla properties.

The prepared Core source therefore adds only:

```json
"tesla": {
  "meter_kwh": 1234.56
}
```

No additional Easee read is introduced. No schema bump is required. No Pi ingress change is required.

### Runtime safety

The Core change in this branch is source preparation only. Do **not** replace the live Homey Core from this branch without:
1. exact live-flow readback;
2. source diff proving the only functional change is `tesla.meter_kwh`;
3. architecture gate PASS;
4. explicit controlled deployment;
5. immediate Homey→Pi verification.

## Pi deadline shadow state

Before any authority cutover, Pi should consume the existing website command and canonical telemetry in shadow mode.

For each new `requestId`, persist at minimum:

- requestId
- requestedAt
- deadline
- currentSoc (command input only; not live telemetry)
- targetSoc
- calibrationKWhPerPercent
- goalKWh
- maxA
- baselineMeterKWh
- baselineCapturedAt
- baselineState
- deliveredKWh
- remainingKWh
- latestStart
- status
- updatedAt

There is currently **no live Tesla SoC telemetry**. The command SoC is input-only and must not be treated as a live measurement.

Realtime charging progress is derived from canonical Homey Core measured `tesla.power_w`, integrated over canonical telemetry timestamps with a bounded maximum interval. The canonical Homey Core intentionally runs on a 5-minute cadence. Deadline progress therefore accepts intervals up to 420 seconds: the normal 300-second cadence plus 120 seconds of transport/scheduling margin. The previous measured power is applied only to the elapsed interval up to the next canonical sample. Longer/stale gaps are never invented.

The Easee cumulative `meter_kwh` is **checkpoint/validation only**. In the observed 2026-09-20 deadline session it remained at 8024.234 kWh throughout active charging and changed to 8028.054 kWh after the session stopped. Therefore it is not a valid realtime progress source in the observed Homey/Easee configuration.

Normal realtime calculation:

```text
deliveredKWh += previousPowerW * boundedElapsedSeconds / 3_600_000
remainingKWh = max(0, goalKWh - deliveredKWh)
latestStart = deadline - remainingKWh / availableDeadlinePowerKW
```

Observed replay validation on 2026-09-20:

- Pi measured-power integration: **3.764761 kWh**
- Easee session-end meter checkpoint: **3.820000 kWh**
- difference: **-0.055239 kWh (-1.446%)**
- historical replay skipped telemetry gaps >120 s: **0** (this replay used a denser history source; production canonical control telemetry is intentionally 5-minute)

This validates measured-power integration as the operational progress source. Five-minute precision is sufficient for EV deadline planning; no additional fast Homey telemetry feed is required. The Pi execution contract uses the same 420-second canonical telemetry-age bound, so a normal 5-minute Core cycle remains valid while genuinely missed/stale cycles fail closed. The meter checkpoint is never added to the power integral and never pulls realtime progress backwards.

## Fail-closed rules

Pi shadow must not invent progress.

- Missing/non-finite meter at baseline capture → meter checkpoint unavailable; measured-power progress may continue.
- Current meter missing/non-finite → measured-power progress continues; retain the previous meter checkpoint.
- Current meter below baseline → meter reset/replacement suspected; retain previous remaining energy and raise diagnostic state.
- New requestId → immutable new baseline capture.
- Same requestId → baseline must never be silently replaced.
- Cancel/inactive command → no active deadline.
- Expired deadline must have an explicit lifecycle state; expiry must not create a new baseline.
- No live SoC may be inferred from delivered kWh.

## Validated migration evidence

Before cutover, Pi shadow was compared with the historical Homey Goal Adapter across the following fields:

| Field | Current Homey | Pi shadow |
| --- | --- | --- |
| requestId | command lifecycle | same command |
| goalKWh | Homey goal | command |
| baseline meter | Homey adapter | Pi shadow |
| deliveredKWh | derived | derived |
| remainingKWh | canonical Homey goal | Pi shadow |
| latestStart | Homey goal | Pi shadow |
| deadline | Homey goal | command |
| maxA | Homey goal | command |

Cutover evidence includes the real 2026-09-20 deadline session replay, the 17-test Pi deadline suite, systemd validation, runtime command ingress/idempotency validation, and live Pi control-contract validation.

## Live control contract

Pi is the deadline owner. `/control/current` publishes `EMS_PI_EV_DEADLINE_EXECUTION_V0.1` as the top-level `deadline` object. The contract is fail-closed, requires Pi authority and fresh canonical telemetry, and carries the authoritative deadline execution inputs needed by the Homey executor guard.

The live Homey PI Dynamic Planner Bridge v1.3.0 consumes `cmd.deadline` and no longer derives deadline execution from `coreState.goals`. Homey remains the realtime executor/safety boundary and sole automatic Easee writer.

## Cutover sequence

1. Prepare canonical `tesla.meter_kwh` source mapping in GitHub.
2. Controlled minimal Core deployment and prove meter arrival on Pi.
3. Implement Pi deadline consumer/state machine in shadow using canonical measured-power integration.
4. Run parity over real deadline sessions.
5. Define and validate Pi→Homey deadline execution contract (`EMS_PI_EV_DEADLINE_EXECUTION_V0.1`).
6. **DONE 2026-09-20:** cut over deadline ownership to Pi; live Homey bridge consumes `cmd.deadline`.
7. **DONE 2026-09-20:** historical Homey Goal Adapter v0.3 disabled (retained only for rollback; no active command-processing role).
8. **IN PROGRESS:** update canonical architecture state and retire obsolete documentation.

At every stage Homey remains the sole automatic physical Easee writer.


## Deprecation state

The historical Homey Goal Adapter deadline derivation is **disabled as of 2026-09-20**. It is retained temporarily only as a rollback artifact and is not part of the active deadline decision chain. New deadline lifecycle/progress/planning logic belongs on Pi. The live Homey bridge consumes the Pi-owned execution contract; Homey continues to own realtime execution/safety and the sole physical Easee writer.

## Command ingress preparation

The Pi must not use the Git working tree as mutable runtime command storage. During this migration phase the durable command source remains the website command committed by the Cloudflare Worker to GitHub `main`.

Prepared command path:

```text
Website
  -> Cloudflare Worker
  -> GitHub main: docs/data/tesla-deadline-command.json
  -> Pi read-only command fetcher (60 s cadence)
  -> /home/jeroen/ems/data/tesla-deadline-command.json
  -> Pi deadline derived-state builder
```

The fetcher validates schema 2, request identity, timestamp presence, SoC bounds, goal energy, calibration and current bounds before publication. A fetch or validation failure never replaces the last valid runtime command. Publication uses atomic replace. An unchanged `requestId` is not rewritten, avoiding unnecessary derived-state triggers.

Deadline strings without an explicit offset are intentionally interpreted as `Europe/Amsterdam` by the Pi deadline engine. The Cloudflare Worker currently validates that the submitted deadline is future-dated, but that validation must not be treated as the authoritative timezone conversion for execution. Pi owns the canonical deadline interpretation.

The command fetch cadence is independent of Homey telemetry. It introduces no additional Homey reads or writes. Canonical charging progress continues to use the intentional 5-minute Homey Core state cadence.

The prepared systemd topology is:

- `ems-ev-deadline-command.timer`: fetch command every 60 seconds;
- `ems-ev-deadline-command.path`: trigger derived state when the runtime command changes;
- `ems-ev-deadline-state.path`: trigger derived state when canonical energy state changes;
- `ems-ev-deadline-state.service`: one derived-state builder shared by both event sources.

The command/state units were installed, verified and activated on 2026-09-20. The command timer runs every 60 seconds; command and canonical-state path units trigger the shared derived-state builder.
