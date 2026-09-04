# EV deadline responsiveness fix — PREP ONLY / NOT DEPLOYED

Status: **PREP ONLY — NOT DEPLOYED TO HOMEY**
Date: 2026-09-04

## Scope

This preparation is intentionally limited to two changes only:

1. **Event-driven Core wake-up after a fully published EV deadline input update.**
2. **Explicit `DEADLINE_INFEASIBLE_AT_MAX_A` status when the requested target can no longer be met within the remaining time at the configured current cap.**

Explicitly out of scope:
- no changes to EV Power Intent deadline power calculation;
- no changes to PV/export ownership;
- no changes to `maxA` propagation/clamping;
- no changes to Adapter/Gate/Actuator electrical mapping;
- no change to `FRESH_MS=120000`;
- no attempt to fix the earlier `STALE_INPUT -> 0 A` incident in this change.

## Live evidence

Observed deadline command:
- deadline 08:00 Europe/Amsterdam
- current SOC 48%
- target SOC 55%
- goal 3.85 kWh
- maxA 8
- latest-start approximately 07:18:09

Timeline:

```text
~07:19:30  deadline command written
~07:20     deadline input adapter / Core ordering race
07:25:00   Easee target changes from 0 A to 8 A
07:25+     Tesla continues charging at 3x8 A
```

Verdict from live test:
- deadline input: PASS
- Core MUST decision: PASS
- deadline Power Intent: PASS
- maxA=8 clamp: PASS
- Adapter/Gate/Actuator: PASS
- physical charging at 3x8 A: PASS
- responsiveness to a newly accepted deadline: FAIL (up to one 5-minute Core cycle latency)

## Change A — event-driven Core wake-up

Current behavior:
- Deadline Goal Adapter runs every 1 minute.
- Core runs independently every 5 minutes.
- A new deadline can therefore be fully accepted just after a Core cycle and wait nearly five minutes before Core consumes it.

Minimal change:
- retain the existing 5-minute Core cron trigger;
- add a second Core trigger on semantic change of `EM2_EV_Goal_Input_Status`;
- ensure the Deadline Goal Adapter writes `EM2_EV_Goal_Input_Status` **last**, after the complete goal set has been published.

The complete goal set is:
- `EV Deadline actief`
- `EV Deadline tijd`
- `EV Doel kWh`
- `EV Resterend kWh`
- `EV Max laadstroom A`
- `EV Latest start`
- `EV Deadline status`

`EM2_EV_Goal_Input_Status` is the commit/event marker. A Core wake-up must never be triggered halfway through updating the goal set.

### Required Advanced Flow change

Core currently has:
- 5-minute cron -> existing Core HomeyScript action
- manual Start -> existing Core HomeyScript action

Candidate addition:

```text
Logic variable changed: EM2_EV_Goal_Input_Status
    -> existing Core HomeyScript action
```

No new HomeyScript and no extra device reader are required. This preserves Core as the single-reader decision owner and adds only event responsiveness.

### Idempotency requirement

`EM2_EV_Goal_Input_Status` should only change for a new semantic deadline command/state, not because a timestamp is refreshed every minute. The event payload should contain stable command identity such as `requestId` plus semantic fields. The adapter should avoid rewriting an equivalent status value.

This prevents a new Core execution every minute when nothing meaningful changed.

## Change B — explicit infeasibility status

At configured maximum current:

```js
const maxPowerW = maxA * 690;
const requiredMs = (remainingKWh / (maxPowerW / 1000)) * 3600000;
const remainingWallClockMs = deadlineMs - Date.now();
const infeasibleAtMaxA = active && remainingKWh > 0 && remainingWallClockMs >= 0 && requiredMs > remainingWallClockMs;
```

Status rules:

```text
inactive / no remaining goal         -> existing inactive/completed status
active, feasible, now < latestStart  -> DEADLINE_WAIT
active, feasible, now >= latestStart -> DEADLINE_CATCH_UP
active, infeasible at configured cap -> DEADLINE_INFEASIBLE_AT_MAX_A
```

Important: `DEADLINE_INFEASIBLE_AT_MAX_A` is **observability**, not a block. Core should still choose `MUST / TESLA_CHARGE_DEADLINE` and the existing Power Intent/Adapter path should charge at the configured maximum allowed current.

## Offline acceptance tests

### T1 — event wake-up
A deadline is accepted immediately after a Core cron cycle.

Expected:
- adapter completes all goal writes;
- commit marker `EM2_EV_Goal_Input_Status` changes once;
- Core runs from that change without waiting for the next 5-minute cron.

### T2 — no partial-state wake-up
During publication of the individual goal Logic variables, Core must not be triggered by this new path.

Expected:
- only final commit-marker update wakes Core;
- Core observes one coherent goal set.

### T3 — idempotency / Homey load
Same website command is polled again one minute later.

Expected:
- semantic commit marker unchanged;
- no additional event-driven Core run;
- normal 5-minute cron remains unchanged.

### T4 — deadline path regression
MUST deadline with flexExportBudgetW=0 and maxA=8.

Expected:
- numeric deadline Power Intent remains >0;
- EV adapter clamps to 8 A;
- no changes to existing Power Intent/Adapter/Gate/Actuator code required.

### T5 — infeasible status
Deadline has insufficient remaining wall-clock time for remaining kWh at maxA.

Expected:
- `DEADLINE_INFEASIBLE_AT_MAX_A`;
- immediate Core wake-up;
- Core still emits `MUST / TESLA_CHARGE_DEADLINE`;
- physical path remains capped at configured maxA.

### T6 — stale-input separation
No freshness constants or stale fail-closed logic change as part of this patch.

Expected:
- diff contains no Adapter/Gate/Actuator freshness modification.

## Deployment gate

Do not deploy until:
1. exact Advanced Flow trigger addition is prepared from the current live Core definition;
2. exact Deadline Goal Adapter status/idempotency patch is prepared from the current live definition;
3. T1-T6 are reviewed offline;
4. PR remains draft until the Homey patch is fully reproducible;
5. only then perform one controlled Homey update with explicit approval;
6. post-deploy observation is read-only.

## Current verdict

**Keep:** event-driven deadline wake-up.

**Keep:** explicit infeasibility reporting.

**Drop from this update:** PV/deadline power changes, maxA changes, 120s->420s freshness change, stale-input remediation.

No physical Homey writes were performed while preparing this narrowed scope.
