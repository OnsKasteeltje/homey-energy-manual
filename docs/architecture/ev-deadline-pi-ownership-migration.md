# EV deadline Pi ownership — migration preparation

Status: **PREPARATION ONLY — NO RUNTIME CUTOVER**

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

There is currently **no live Tesla SoC telemetry**. After command creation, charging progress must therefore be derived from the cumulative Easee meter.

Normal calculation:

```text
deliveredKWh = max(0, currentMeterKWh - baselineMeterKWh)
remainingKWh = max(0, goalKWh - deliveredKWh)
latestStart = deadline - remainingKWh / availableDeadlinePowerKW
```

## Fail-closed rules

Pi shadow must not invent progress.

- Missing/non-finite meter at baseline capture → baseline invalid; no deadline authority.
- Current meter missing/non-finite → retain previous valid remaining energy.
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
3. Implement Pi deadline consumer/state machine in shadow.
4. Run parity over real deadline sessions.
5. Define and validate Pi→Homey deadline execution contract.
6. Cut over deadline ownership to Pi.
7. Disable/remove the historical Homey Goal Adapter command-processing role.
8. Update canonical architecture state and retire obsolete documentation.

At every stage Homey remains the sole automatic physical Easee writer.
