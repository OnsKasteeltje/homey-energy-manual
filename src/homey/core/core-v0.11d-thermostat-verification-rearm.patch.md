# Core v0.11d — deployment delta from v0.11c

Status: **PREPARED OUTSIDE HOMEY / NOT DEPLOYED**

Baseline: live Core v0.11c thermostat-verification logic as captured on 2026-08-30.

## Scope

This delta fixes only the same-physical-run thermostat-verification re-arm defect. It must not alter Core cadence, device reads, Planner semantics, WW ownership, Tesla logic, Quatt behavior, 19:00 stop, Publisher cadence/fan-out, or Core's read-only/no-device-write rule.

## 1. Version metadata

Change:

```js
const PUB_VERSION='EM2_CORE_STATE_V0.11c'
```

to:

```js
const PUB_VERSION='EM2_CORE_STATE_V0.11d'
```

Rename the Advanced Flow to:

`EM v2 | 00 Core Tick | v0.11d (Thermostat Verification Rearm)`

## 2. Replace the run-wide consumed latch

Remove policy use of:

```js
prevVerifyConsumedRunKey
thermostatVerifyConsumed
thermostatVerifyConsumedRunKeyOut
```

The existing `thermostatVerifyConsumedRunKey` may temporarily remain as backward-compatible observability, but it must not gate eligibility.

Introduce previous/current stop-edge state from `prevControl.inputs`:

```js
const prevStopRequested = prevControl?.inputs?.thermostatVerifyStopRequested === true;
const thermostatVerifyRequested = discretionaryPlannerStop || discretionaryImportOrPriceStop;
const newStopEdge = thermostatVerifyRequested && !prevStopRequested;
const stopRequestCleared = !thermostatVerifyRequested && prevStopRequested;
```

Carry episode state from the previous control object:

```js
let thermostatVerifyEpisodeKeyOut = prevControl?.inputs?.thermostatVerifyEpisodeKey ?? null;
let thermostatVerifyStartedAtOut = prevControl?.inputs?.thermostatVerifyStartedAt ?? null;
let thermostatVerifyEndedAtOut = prevControl?.inputs?.thermostatVerifyEndedAt ?? null;
let thermostatVerifyEndReasonOut = prevControl?.inputs?.thermostatVerifyEndReason ?? null;
let thermostatVerifyRearmReadyOut = prevControl?.inputs?.thermostatVerifyRearmReady !== false;
```

## 3. Re-arm only on a real stop-request clear

After `thermostatVerifyRequested` is known and before a new episode can start:

```js
const continuedConfirmedHeating = boilerOn && st.heatingConfirmed === true && powerW > 1500;

if(
  stopRequestCleared &&
  continuedConfirmedHeating &&
  !goalReachedToday &&
  !prevVerifyActive
){
  thermostatVerifyRearmReadyOut = true;
}
```

Do not re-arm from elapsed time, a still-true stop request, or latched `heatingConfirmed` alone.

## 4. New episode start rule

Keep the v0.11c safety/base eligibility, but remove the physical-run-wide consumed check and require a new stop edge plus re-arm readiness:

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
  thermostatVerifyRearmReadyOut;
```

On start:

```js
thermostatVerifyStartedAtOut = new Date().toISOString();
thermostatVerifyEpisodeKeyOut = `${String(st.runStartedAt || 'NO_RUN')}|${thermostatVerifyStartedAtOut}`;
thermostatVerifyEndedAtOut = null;
thermostatVerifyEndReasonOut = null;
thermostatVerifyRearmReadyOut = false;
```

Then select the existing bounded verification output:

```js
wwAction='HOLD';
wwPriority='MAY';
wwOpportunity='THERMOSTAT_VERIFY';
recommendedRunLockMin=0;
```

## 5. Expiry and safety aborts

Retain the v0.11c 20-minute hard maximum and immediate P1/grid/import-safety abort behavior. On any episode end without goal confirmation:

```js
thermostatVerifyEndedAtOut = new Date().toISOString();
thermostatVerifyRearmReadyOut = false;
```

Set a reason such as:

```js
'MAX_20_MIN_EXPIRED'
'ABORT_P1_INVALID'
'ABORT_GRID_INVALID'
'ABORT_IMPORT_BUDGET'
```

The original discretionary OFF must then pass through. If the stop request remains continuously true, no new episode may start.

## 6. Goal confirmation

Do not change the existing thermostat evidence rule: confirmed heating followed by `<100 W` for at least 10 minutes while `boilerOn===true`.

When the daily goal latches during an active verification:

```js
thermostatVerifyEndedAtOut = new Date().toISOString();
thermostatVerifyEndReasonOut = 'GOAL_CONFIRMED';
thermostatVerifyRearmReadyOut = false;
```

Do not infer the goal from EMS intent or from verification expiry.

## 7. Physical OFF reset

When `boilerOn===false`, normalize episode state for the next physical run:

```js
thermostatVerifyEpisodeKeyOut = null;
thermostatVerifyStartedAtOut = null;
thermostatVerifyEndedAtOut = null;
thermostatVerifyEndReasonOut = null;
thermostatVerifyRearmReadyOut = true;
```

Persist `thermostatVerifyStopRequested:false` for the OFF baseline.

## 8. Observability additions

Add to `EM2_Control_WW.inputs`:

```js
thermostatVerifyStopRequested: thermostatVerifyRequested,
thermostatVerifyStopRequestedPrev: prevStopRequested,
thermostatVerifyNewStopEdge: newStopEdge,
thermostatVerifyEpisodeKey: thermostatVerifyEpisodeKeyOut,
thermostatVerifyStartedAt: thermostatVerifyStartedAtOut,
thermostatVerifyEndedAt: thermostatVerifyEndedAtOut,
thermostatVerifyEndReason: thermostatVerifyEndReasonOut,
thermostatVerifyRearmReady: thermostatVerifyRearmReadyOut
```

Retain current active/age/import-safety observability.

## 9. Deployment gate

Before any Homey mutation:

1. fetch the complete then-live v0.11c Advanced Flow;
2. save it as the rollback unit;
3. apply only this patch to the exact full script;
4. diff the complete candidate against the complete baseline;
5. require the offline regression A-J result to remain 10/10 PASS;
6. perform exactly one Advanced Flow update;
7. validate only by a natural boiler cycle, with no parallel Homey discovery/load work.

No Homey mutation is part of this preparation file.
