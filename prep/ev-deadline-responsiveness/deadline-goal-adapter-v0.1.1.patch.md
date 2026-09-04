# EV Deadline Goal Adapter v0.1.1 — exact prep patch

Status: **PREP ONLY / NOT DEPLOYED**

Target flow: `445cb82c-5e1f-43c3-b2cf-f2d78fec6e16` — `EM v2 | 10 Input | EV Deadline Goal Adapter v0.1`

## Goal

Make `EM2_EV_Goal_Input_Status` a semantic commit marker instead of a 1-minute heartbeat, so Core can safely trigger from it without increasing Core cadence to once per minute. Add explicit infeasibility observability without changing charging power logic.

## 1. Add constants/helpers

```js
const LATE_TOLERANCE_MS = 60000;
const markerValue = obj => JSON.stringify({schema:'EM2_EV_GOAL_INPUT_V0.1', ...obj});
const setMarker = async obj => set('EM2_EV_Goal_Input_Status','string',markerValue(obj));
```

Important: the marker MUST NOT contain `at`, `generatedAt`, `updatedAt`, or another polling timestamp. Identical semantic input must therefore produce an identical string.

## 2. FETCH_FAILED

Replace:

```js
await set('EM2_EV_Goal_Input_Status','string',JSON.stringify({status:'FETCH_FAILED',at:new Date().toISOString()}));
```

with:

```js
await setMarker({status:'FETCH_FAILED'});
```

This changes the marker only when the semantic state transitions to/from `FETCH_FAILED`.

## 3. Inactive command

After all inactive goal variables have been committed, replace the current timestamped marker with:

```js
await setMarker({
  status:'IDLE',
  requestId
});
```

The marker remains the **last write** of the transaction.

## 4. Rejected command

After `EV Deadline actief=false` and `EV Deadline status=DEADLINE_INPUT_REJECTED` have been committed, use:

```js
await setMarker({
  status:'REJECTED',
  requestId,
  deadline,
  goalKWh:Number.isFinite(goal)?goal:null,
  maxA:Number.isFinite(maxA)?maxA:null
});
```

Again: marker last.

## 5. Valid command: status calculation

Keep existing validation and power calculation unchanged:

```js
const neededMs=(goal/(maxA*W_PER_A/1000))*3600000;
const latestMs=dlMs-neededMs;
```

Add:

```js
const latenessMs = now - latestMs;
const infeasibleAtMaxA = latenessMs > LATE_TOLERANCE_MS;
const deadlineStatus = now < latestMs
  ? 'DEADLINE_WAIT'
  : infeasibleAtMaxA
    ? 'DEADLINE_INFEASIBLE_AT_MAX_A'
    : 'DEADLINE_CATCH_UP';
```

The 60-second tolerance prevents tiny poll/scheduling jitter around `latestStart` from being classified as hard infeasibility.

## 6. Valid command: commit order

Commit all goal fields first, exactly in this logical transaction:

```js
await set('EV Deadline actief','boolean',true);
await set('EV Deadline tijd','string',new Date(dlMs).toISOString());
await set('EV Doel kWh','number',goal);
await set('EV Resterend kWh','number',goal);
await set('EV Max laadstroom A','number',maxA);
await set('EV Latest start','string',new Date(latestMs).toISOString());
await set('EV Deadline status','string',deadlineStatus);
```

Then publish the semantic commit marker **last**:

```js
await setMarker({
  status:'OK',
  requestId,
  deadlineAt:new Date(dlMs).toISOString(),
  latestStartAt:new Date(latestMs).toISOString(),
  goalKWh:goal,
  maxA,
  neededMin:Math.round(neededMs/60000),
  deadlineStatus,
  infeasibleAtMaxA,
  deviceWrites:false
});
```

## 7. Required invariants

- No device writes.
- Existing 1-minute website polling remains unchanged.
- `EM2_EV_Goal_Input_Status` changes only for semantic input/status changes.
- Re-reading the same `requestId` with identical values causes **zero marker mutation**.
- Marker is always the final write after the complete goal set.
- Core may therefore safely use marker-change as an event trigger.
- Existing `maxA` handling remains unchanged.
- Existing Power Intent / Adapter / Gate / Actuator logic remains unchanged.

## Offline acceptance vectors

| Case | Input | Expected marker mutation | Deadline status |
|---|---|---:|---|
| same valid command, next minute | identical requestId/goal/deadline/maxA | no | unchanged |
| new valid command before latestStart | new requestId | yes | `DEADLINE_WAIT` |
| new valid command <=60s after latestStart | new requestId | yes | `DEADLINE_CATCH_UP` |
| new valid command >60s after latestStart | new requestId | yes | `DEADLINE_INFEASIBLE_AT_MAX_A` |
| same inactive command, next minute | identical requestId | no | `NO_DEADLINE` |
| fetch failure persists | repeated failure | only first transition | n/a |

No Homey deployment is authorized by this file.
