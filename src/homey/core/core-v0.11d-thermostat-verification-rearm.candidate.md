# Core v0.11d — thermostat verification re-arm candidate

Status: **PREPARED IN GITHUB / NOT DEPLOYED TO HOMEY**

Baseline: live Homey `EM v2 | 00 Core Tick | v0.11c (Thermostat Verification)` observed on 2026-08-30.

## Incident that drives this change

A natural boiler run on 2026-08-30 remained physically ON from 14:50:03 until 16:10:03 local time. Immediately before the OFF, measured boiler power was still about 1966 W; immediately after the OFF it was 0 W. There was therefore no preceding 10-minute `<100 W while switch ON` period and no valid thermostat evidence for `goalReachedToday` at the moment of the OFF.

The v0.11c runtime uses `thermostatVerifyConsumedRunKey` to prevent renewal loops. That guard is too coarse: after one verification episode is consumed within a physical ON-run, every later discretionary OFF attempt during that same ON-run is blocked from starting a fresh bounded verification, even if a materially new opportunity interval occurred in between.

## Objective

Keep the anti-renewal safety property of v0.11c, but allow a genuinely new discretionary OFF edge later in the same physical boiler ON-run to receive one fresh bounded thermostat-verification episode.

The fix must satisfy both invariants:

1. **No continuous renewal loop:** a continuously pending discretionary OFF may never chain 20-minute verification windows indefinitely.
2. **New OFF edge may verify again:** if the previous verification ended and the discretionary OFF request later cleared for at least one normal Core tick while confirmed heating continued, a subsequent new discretionary OFF request may start one fresh verification episode.

## State-machine change

Replace the physical-run-wide consumed latch with explicit verification-episode state.

Add/normalize the following fields in `EM2_Control_WW.inputs` or equivalent local Core state carried across ticks:

```js
thermostatVerifyEpisodeKey: null,
thermostatVerifyEndedAt: null,
thermostatVerifyEndReason: null,
thermostatVerifyRearmReady: true,
thermostatVerifyStopRequestedPrev: false
```

`thermostatVerifyRearmReady` means a new verification episode may start on the **next false -> true discretionary-stop edge**. It must not be set merely because time passed.

## Discretionary stop signal

Keep the existing stop semantics:

```js
const discretionaryPlannerStop =
  boilerOn && plannerStarted && !plannerOpportunity;

const discretionaryImportOrPriceStop =
  boilerOn && !opportunity && (expensive || importW > 500);

const thermostatVerifyRequested =
  discretionaryPlannerStop || discretionaryImportOrPriceStop;
```

Track the previous tick's request state:

```js
const prevStopRequested =
  prevControl?.inputs?.thermostatVerifyStopRequested === true;

const newStopEdge =
  thermostatVerifyRequested && !prevStopRequested;
```

Persist the current value for the next tick:

```js
thermostatVerifyStopRequested: thermostatVerifyRequested
```

## Episode identity

Use an episode key that is unique per verification start and does not depend only on the physical ON-run:

```js
const thermostatVerifyEpisodeKey =
  `${String(st.runStartedAt || 'NO_RUN')}|${new Date().toISOString()}`;
```

An equivalent monotonic counter is acceptable. The key exists for observability and dedup only; it must not itself drive policy.

## Start rule

Keep all v0.11c base eligibility/safety requirements, but remove `thermostatVerifyConsumedRunKey` from eligibility.

A new verification may start only when all are true:

```js
const thermostatVerifyBaseEligible =
  mode &&
  minuteOfDay < 1140 &&
  !goalReachedToday &&
  boilerOn &&
  st.heatingConfirmed === true &&
  !catchupRequired &&
  p1Fresh &&
  gridMeasurementValid &&
  thermostatVerifyImportSafe;

const thermostatVerifyCanStart =
  thermostatVerifyBaseEligible &&
  thermostatVerifyRequested &&
  newStopEdge &&
  prevControl?.inputs?.thermostatVerifyRearmReady !== false;
```

On start:

```js
thermostatVerifyStartedAtOut = new Date().toISOString();
thermostatVerifyEpisodeKeyOut =
  `${String(st.runStartedAt || 'NO_RUN')}|${thermostatVerifyStartedAtOut}`;
thermostatVerifyRearmReadyOut = false;
thermostatVerifyEndReasonOut = null;
```

Then output:

```js
wwAction = 'HOLD';
wwPriority = 'MAY';
wwOpportunity = 'THERMOSTAT_VERIFY';
```

## Active episode

Retain the existing hard 20-minute maximum and all safety aborts.

While the episode is active and safe:

```js
wwAction = 'HOLD';
wwPriority = 'MAY';
wwOpportunity = 'THERMOSTAT_VERIFY';
```

If actual thermostat evidence completes (`<100 W` for the existing 10-minute confirmation while `boilerOn=true`), latch the daily goal exactly as today and end the episode with:

```js
thermostatVerifyEndReasonOut = 'GOAL_CONFIRMED';
thermostatVerifyRearmReadyOut = false;
```

No re-arm is needed after the daily goal is latched.

## Expiry/abort behavior

When the active episode reaches 20 minutes without goal evidence, or must abort due to P1/import safety, end it once and allow the original OFF decision to pass through.

On end:

```js
thermostatVerifyEndedAtOut = new Date().toISOString();
thermostatVerifyRearmReadyOut = false;
thermostatVerifyEndReasonOut =
  expired ? 'MAX_20_MIN_EXPIRED' : abortReason;
```

A continuously true `thermostatVerifyRequested` must therefore remain unable to restart another verification window.

## Re-arm rule — the actual fix

Re-arm only after evidence that the previous discretionary OFF request has genuinely cleared while the same physical run is still producing confirmed heating.

On a tick after a completed/aborted episode:

```js
const stopRequestCleared =
  !thermostatVerifyRequested && prevStopRequested;

const continuedConfirmedHeating =
  boilerOn &&
  st.heatingConfirmed === true &&
  powerW > 1500;

if(
  stopRequestCleared &&
  continuedConfirmedHeating &&
  !goalReachedToday
){
  thermostatVerifyRearmReadyOut = true;
}
```

This is intentionally edge-based. A later false -> true stop edge can then start exactly one fresh bounded verification episode.

Do **not** re-arm merely because:

- 20 minutes elapsed;
- the switch is still ON;
- the prior episode expired;
- `heatingConfirmed` remained latched from earlier;
- Core repeatedly evaluates the same continuously true discretionary OFF condition.

## Physical run transition

When `boilerOn=false`, clear all episode-specific state so the next physical ON-run starts clean:

```js
thermostatVerifyEpisodeKeyOut = null;
thermostatVerifyStartedAtOut = null;
thermostatVerifyEndedAtOut = null;
thermostatVerifyEndReasonOut = null;
thermostatVerifyRearmReadyOut = true;
thermostatVerifyStopRequestedOut = false;
```

## Branch precedence

No changes are allowed to mandatory precedence. The following still bypass verification immediately:

- electric boiler mode disabled;
- local time >= 19:00;
- daily goal already reached;
- catch-up/MUST path;
- stale or invalid P1;
- unsafe import guard;
- any future explicit hard electrical safety gate.

## Observability

Add to `EM2_Control_WW.inputs`:

```js
thermostatVerifyStopRequested,
thermostatVerifyStopRequestedPrev: prevStopRequested,
thermostatVerifyNewStopEdge: newStopEdge,
thermostatVerifyEpisodeKey: thermostatVerifyEpisodeKeyOut,
thermostatVerifyStartedAt: thermostatVerifyStartedAtOut,
thermostatVerifyEndedAt: thermostatVerifyEndedAtOut,
thermostatVerifyEndReason: thermostatVerifyEndReasonOut,
thermostatVerifyRearmReady: thermostatVerifyRearmReadyOut
```

Retain existing `thermostatVerifyActive`, age, import-safety and run-key observability where useful, but `thermostatVerifyConsumedRunKey` must no longer be a policy gate.

## Version metadata

Target flow name:

`EM v2 | 00 Core Tick | v0.11d (Thermostat Verification Rearm)`

Target publisher version constant:

`EM2_CORE_STATE_V0.11d`

Keep the existing Core/public/control schemas unchanged; the new fields are optional observability/state fields.

## No-change contract

v0.11d must not change:

- 5-minute Core cadence;
- targeted device set;
- Planner v0.4.9 semantics;
- Power Intent ownership;
- WW Adapter/Gate/Actuator ownership;
- publisher cadence;
- Quatt observe-only behavior;
- Tesla logic;
- 19:00 hard WW stop;
- daily goal evidence (`>1500 W confirmed heating`, then `<100 W` for 10 minutes while switch ON);
- physical-write rule: Core remains read-only and never writes a device.

## Deployment gate

Do not mutate Homey for this preparation.

Before eventual deployment:

1. capture the complete then-live Core flow as rollback baseline;
2. apply only this re-arm delta to that exact script;
3. diff full script against baseline;
4. run the offline regression scenarios in `smoke-v0.11d-thermostat-verification-rearm.md`;
5. deploy with one Advanced Flow update only after review;
6. perform a natural-cycle validation with no parallel Homey discovery/load work.
