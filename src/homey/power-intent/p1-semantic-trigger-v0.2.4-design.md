# Power Intent P1 v0.2.4 — semantic EV trigger design

Status: **DESIGN / NOT DEPLOYED**

Date: 2026-08-29

## Purpose

Correct the semantic-trigger regression introduced when Power Intent was decoupled from `EM2_Public_State`.

The current v0.2.3 trigger uses only `EM2_Control_WW changed`. That successfully removed freshness fan-out, but it does not cover Tesla-only changes in `EM2_Decision`. As a result, Core can legitimately move between `HOLD`, `TESLA_BUFFER_EXPORT`, and `TESLA_CHARGE_OPPORTUNITY` without waking Power Intent when warm-water control semantics remain unchanged.

This design restores EV responsiveness without reintroducing `EM2_Public_State` as a control bus and without adding recurring polling.

## Chosen design

Introduce one narrow, semantic, post-Core control signal:

`EM2_Control_EV`

Core owns this variable and writes it only after the authoritative State, Decision, and WW-control outputs for the same Core run have been calculated.

The signal is not a duplicate public-state snapshot. It contains only the minimum EV-control semantics needed to wake Power Intent.

Proposed schema:

```json
{
  "schema": "EM2_CONTROL_EV_V0.1",
  "semanticRevision": 0,
  "coreRevision": 0,
  "mode": "HOLD|BUFFER_EXPORT|OPPORTUNITY|DEADLINE",
  "requestedPowerClass": 0,
  "chargerAvailable": false,
  "deadlineActive": false,
  "safetyState": "OK|BLOCKED",
  "generatedAt": "ISO-8601"
}
```

`generatedAt` is observability only and MUST be excluded from the semantic comparison used to decide whether the Logic variable is written.

`requestedPowerClass` is a semantic bucket, not the final actuator command. During the first deployment it should reflect the control-relevant EV target class produced by Core/Decision, while final W→A translation remains exclusively owned by the existing EV Power Adapter.

## Trigger contract

Power Intent P1 v0.2.4 shall trigger on:

- `EM2_Control_EV changed`; and
- `EM2_Control_WW changed`.

Both are narrow semantic control signals. `EM2_Public_State` remains forbidden as an internal control trigger.

The two-trigger design is necessary because Power Intent still publishes both EV and WW targets. An EV-only trigger would fix Tesla responsiveness but could miss a WW-only semantic change; a WW-only trigger is the current regression.

## Coherency and settle rule

A direct `EM2_Decision changed` trigger is not selected because Core writes multiple related outputs during one run. A Decision event can therefore wake Power Intent before the corresponding State/WW outputs have reached the same revision.

`EM2_Control_EV` is written deliberately at the end of Core's semantic-control publication sequence. It acts as the EV-side commit signal for a coherent Core control revision.

Power Intent must still fail closed unless:

```text
State.coreRevision == Decision.coreRevision
and Control_WW.coreRevision == Decision.coreRevision
and Control_EV.coreRevision == Decision.coreRevision
```

If the exact existing revision field names differ in runtime, the implementation must map to the existing canonical source-revision contract rather than inventing an independent revision stream.

No arbitrary polling/retry loop is allowed. A single short settle delay may be retained only if runtime ordering proves it necessary, and must be bounded and documented.

## Idempotency change

The v0.2.3 early-return guard is currently effectively tied to the WW-derived source revision. v0.2.4 must replace this with a combined semantic input key so that EV-only changes are not suppressed.

Proposed key:

```text
inputSemanticKey =
  State.coreRevision
  + ":" + Decision.semanticSignature
  + ":" + Control_EV.semanticRevision
  + ":" + Control_WW.semanticRevision
```

The exact serialized representation is implementation detail, but the guard must satisfy:

1. identical EV+WW semantics for the same coherent Core revision -> no duplicate downstream write;
2. EV semantic change with unchanged WW -> Power Intent recomputes once;
3. WW semantic change with unchanged EV -> Power Intent recomputes once;
4. freshness/timestamp-only changes -> no Power Intent wake-up;
5. duplicate trigger delivery from both EV and WW for one coherent semantic state -> at most one new `EM2_Power_Intent` semantic output.

## Relationship to EV Surplus Smoother

The planned `EV Surplus Smoother v0.1 SHADOW` remains independent of this trigger correction.

Initial sequence:

```text
Core semantic Decision
   │
   ├─ WW semantics -> EM2_Control_WW
   └─ EV semantics -> EM2_Control_EV
                         │
                         ▼
                 Power Intent P1 v0.2.4
                         │
                         ▼
                 Adapter / Gate / Actuator
```

The smoother is first deployed SHADOW-only. After validation, its smoothed/qualified EV-surplus result may become an input to the EV semantic decision, but it must not bypass Core policy or directly command the actuator path.

## Load impact

Steady recurring API cost added by this trigger correction:

- broad `getDevices()` reads: **0/hour**;
- broad `getVariables()` reads: **0/hour**;
- recurring pollers: **0**;
- external calls: **0/hour**;
- physical writes: **0** from this change.

Incremental Logic activity:

- one `EM2_Control_EV` Logic write only when EV control semantics materially change;
- Power Intent v0.2.4 wake-up only on semantic EV or WW changes;
- duplicate EV+WW wake-ups for the same combined semantic input must be suppressed by the idempotency key.

This is preferable to triggering on every Core/Public-State heartbeat and is compatible with the Homey load-governance requirement that freshness-only fields do not cause control fan-out.

## Deployment sequence

1. Implement `EM2_Control_EV` production in Core with semantic write suppression, but no consumer yet.
2. Exact-ID read/smoke Core only; verify no extra broad reads and measure natural `EM2_Control_EV` write frequency.
3. Soak before changing Power Intent.
4. Deploy P1 v0.2.4 with dual semantic triggers and combined idempotency guard, keeping current SHADOW/read-only/deviceWrites=false contract unchanged.
5. Validate natural Tesla-only transition: `HOLD -> BUFFER_EXPORT/OPPORTUNITY` with WW unchanged causes exactly one Power Intent semantic update.
6. Validate reverse transition and a WW-only transition.
7. Confirm Adapter/Gate/Actuator contracts and LIVE ownership are unchanged.
8. Any Homey 429 fails the promotion and the most recently promoted component returns OFF/previous version according to the recovery tripwire.

## Acceptance tests

PASS requires all of the following:

- Tesla-only Decision change wakes Power Intent;
- WW-only control change still wakes Power Intent;
- no `EM2_Public_State` dependency;
- no timestamp/freshness fan-out;
- duplicate same-state EV+WW triggers produce at most one semantic Power Intent output;
- coherent source-revision checks remain fail-closed;
- no new broad reads or recurring pollers;
- no Easee physical write is introduced by the trigger correction itself;
- no 429 during soak.

## Rollback

Rollback is bounded:

- leave `EM2_Control_EV` orphaned or disable its Core write if necessary;
- restore Power Intent v0.2.3 trigger contract only as a temporary safe rollback, acknowledging that Tesla-only restart remains functionally incomplete;
- never restore `EM2_Public_State` as the control trigger merely to regain responsiveness.
