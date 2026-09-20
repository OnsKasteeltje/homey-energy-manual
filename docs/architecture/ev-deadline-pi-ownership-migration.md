# EV deadline Pi ownership — migration preparation

Status: **MIGRATION IN PROGRESS — PI SHADOW, NO AUTHORITY CUTOVER**

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

## Shadow parity

While the current Homey Goal Adapter remains authoritative, Pi shadow must compare at least:

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

Cutover is blocked until real charging sessions demonstrate acceptable parity and lifecycle/failure cases have been tested.

## Future control contract

When Pi becomes deadline owner, Homey must not continue deriving an independent deadline state. The Pi→Homey control envelope must carry the authoritative deadline execution inputs needed by the executor guard, rather than making the guard depend on duplicated Homey Logic goals.

The exact control-envelope change is deliberately **not** part of this preparation commit.

## Cutover sequence

1. Prepare canonical `tesla.meter_kwh` source mapping in GitHub.
2. Controlled minimal Core deployment and prove meter arrival on Pi.
3. Implement Pi deadline consumer/state machine in shadow using canonical measured-power integration.
4. Run parity over real deadline sessions.
5. Define and validate Pi→Homey deadline execution contract (`EMS_PI_EV_DEADLINE_EXECUTION_V0.1`).
6. Cut over deadline ownership to Pi.
7. Disable/remove the historical Homey Goal Adapter command-processing role.
8. Update canonical architecture state and retire obsolete documentation.

At every stage Homey remains the sole automatic physical Easee writer.


## Deprecation state

The historical Homey Goal Adapter deadline derivation is **deprecated** as the target architecture. It remains temporarily present only because the current Homey exact-minute executor guard still consumes its Logic outputs. It must not be extended with new progress logic. Removal/disablement is blocked until the Pi→Homey control envelope carries the authoritative deadline execution fields and that path has been validated.
