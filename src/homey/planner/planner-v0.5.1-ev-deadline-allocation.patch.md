# Planner v0.5.1 — EV deadline allocation patch

Status: **PREPARED / NOT DEPLOYED**

Scope is deliberately small: make the existing Tesla deadline visible as a real 15-minute power plan. No actuator writes, no frontend change, no battery change, no WW policy change.

## Root cause

Planner v0.5.0 reads `teslaDeadlineActive`, `teslaRemainingKWh`, `teslaDeadline` and `teslaLatestStart`, but it only labels ranked slots as `PREFERRED_BEFORE_DEADLINE`. `actions[].targets.evTargetW` stays `0`, so the published Planner snapshot has no Tesla power intent to render or consume.

A second gap is that Core does not currently expose `EV Max laadstroom A` in the Planner state/input, although the EV Deadline Goal Adapter already validates and stores that value.

## Patch A — Core state/input: pass max current through

Target runtime baseline: `src/homey/core/core-v0.11i.live-homey.js`.

In the `state.goals` object, add one field only:

```js
maxA: vv('EV Max laadstroom A')
```

Resulting goals shape:

```js
goals:{
  teslaDeadlineActive:vv('EV Deadline actief'),
  teslaDeadline:vv('EV Deadline tijd'),
  teslaLatestStart:vv('EV Latest start'),
  teslaRemainingKWh:vv('EV Resterend kWh'),
  teslaStatus:vv('EV Deadline status'),
  teslaMaxA:vv('EV Max laadstroom A')
}
```

Use the name `teslaMaxA` in the published state so Planner does not depend on the Homey Logic display name.

No extra Homey read is introduced: Core already obtains all Logic variables in one `Homey.logic.getVariables()` call.

## Patch B — Planner: derive EV power and required slot count

Target runtime baseline: `src/homey/planner/energy-plan-24h-v0.5.0.live-homey.js`.

Add constants next to the existing EV constants:

```js
const EV_W_PER_A=690,EV_MIN_A=6,EV_MAX_A=16;
```

Replace the current Tesla input extraction:

```js
const deadlineActive=bool(state?.goals?.teslaDeadlineActive),remainingKWh=Math.max(0,num(state?.goals?.teslaRemainingKWh)||0),deadlineAt=state?.goals?.teslaDeadline??null,latestStart=state?.goals?.teslaLatestStart??null;
```

with:

```js
const deadlineActive=bool(state?.goals?.teslaDeadlineActive),
  remainingKWh=Math.max(0,num(state?.goals?.teslaRemainingKWh)||0),
  deadlineAt=state?.goals?.teslaDeadline??null,
  latestStart=state?.goals?.teslaLatestStart??null,
  maxA=Math.max(EV_MIN_A,Math.min(EV_MAX_A,Math.round(num(state?.goals?.teslaMaxA)||EV_MAX_A))),
  maxPowerW=maxA*EV_W_PER_A,
  evSlotEnergyKWh=maxPowerW/1000*.25,
  requiredDeadlineSlots=deadlineActive&&remainingKWh>0?Math.ceil(remainingKWh/evSlotEnergyKWh-1e-12):0,
  latestStartMs=Date.parse(String(latestStart||'')),
  deadlineCatchUp=deadlineActive&&Number.isFinite(latestStartMs)&&nowMs>=latestStartMs;
```

The fallback to 16 A is only a compatibility guard for an old state snapshot. Once Core patch A is live, `teslaMaxA` is authoritative.

## Patch C — use `latestStart` and allocate only the required slots

Replace:

```js
const teslaCandidates=forecastSlots.filter(s=>before(s,dlMs));
const teslaDeadlineRanked=deadlineActive&&remainingKWh>0?rankTeslaDeadline(teslaCandidates).slice(0,Math.min(12,teslaCandidates.length)):[];
```

with:

```js
const teslaCandidates=forecastSlots.filter(s=>before(s,dlMs));
const teslaDeadlineOrdered=deadlineCatchUp
  ? [...teslaCandidates].sort((a,z)=>Date.parse(a.start)-Date.parse(z.start))
  : rankTeslaDeadline(teslaCandidates);
const teslaDeadlineRanked=deadlineActive&&remainingKWh>0
  ? teslaDeadlineOrdered.slice(0,Math.min(requiredDeadlineSlots,teslaDeadlineOrdered.length))
  : [];
const teslaAllocatedKWh=teslaDeadlineRanked.length*evSlotEnergyKWh;
const teslaUnallocatedKWh=Math.max(0,remainingKWh-teslaAllocatedKWh);
```

Semantics:

- before `latestStart`: preserve the existing PV-surplus / price ranking;
- at or after `latestStart`: switch to chronological catch-up slots, because meeting the deadline is now more important than optional optimization;
- never reserve an arbitrary fixed 12 slots; reserve exactly the count implied by remaining kWh and max current, limited by the slots that actually exist before the deadline.

## Patch D — write Tesla power into the action plan

Replace:

```js
for(const x of teslaDeadlineRanked)if(byStart[x.start])byStart[x.start].tesla='PREFERRED_BEFORE_DEADLINE';
```

with:

```js
for(const x of teslaDeadlineRanked)if(byStart[x.start]){
  byStart[x.start].tesla=deadlineCatchUp?'DEADLINE_REQUIRED':'PREFERRED_BEFORE_DEADLINE';
  byStart[x.start].targets.evTargetW=maxPowerW;
}
```

The existing opportunity branch remains unchanged. This patch only changes active-deadline behavior.

## Patch E — publish enough evidence to validate safely

Extend `inputs.tesla` with:

```js
maxA,
maxPowerW,
slotEnergyKWh:Number(evSlotEnergyKWh.toFixed(3)),
requiredDeadlineSlots,
deadlineCatchUp
```

Extend `plan.tesla` with:

```js
allocatedKWh:Number(teslaAllocatedKWh.toFixed(3)),
unallocatedKWh:Number(teslaUnallocatedKWh.toFixed(3)),
maxA,
maxPowerW,
requiredDeadlineSlots,
deadlineCatchUp
```

Extend status with:

```js
teslaMaxA:maxA,
teslaMaxPowerW:maxPowerW,
teslaRequiredSlots:requiredDeadlineSlots,
teslaAllocatedSlots:teslaDeadlineRanked.length,
teslaUnallocatedKWh:Number(teslaUnallocatedKWh.toFixed(3)),
teslaDeadlineCatchUp:deadlineCatchUp
```

## Expected result for the live test command of 2026-09-05

Input command:

```text
deadline = 10:45 local
goal/remaining = 3.3 kWh
maxA = 9 A
latestStart ≈ 10:13 local
```

Derived values:

```text
maxPowerW = 9 × 690 = 6210 W
slotEnergy = 6.210 × 0.25 = 1.5525 kWh
requiredDeadlineSlots = ceil(3.3 / 1.5525) = 3
```

When Planner runs after `latestStart`, it must enter catch-up ordering. If only the 10:15 and 10:30 quarter slots remain before 10:45, both must be marked `DEADLINE_REQUIRED` with `evTargetW=6210`, and the snapshot must explicitly report the residual planning shortfall (~0.195 kWh) instead of silently pretending the deadline is fully covered.

This is intentionally conservative: 15-minute planning resolution may expose a small residual even though the continuous-time EV adapter calculated a feasible `latestStart`. That is preferable to hiding the mismatch.

## Safety / non-goals

- SHADOW remains SHADOW.
- No Easee write is added.
- No Core physical write is added.
- No change to WW allocation except that the already-existing Tesla-priority relocation now uses the smaller, correct set of reserved deadline slots.
- No change to the Planner frontend is required; it already renders non-HOLD Tesla action slots.
- No battery dispatch changes.
- Do not deploy until the pure allocation tests in `tests/planner-v0.5.1-ev-deadline-allocation.test.mjs` pass and a fresh Planner snapshot is checked manually.
