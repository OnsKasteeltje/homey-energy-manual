# EV deadline control fix — PREP ONLY / NOT DEPLOYED

Status: **PREP ONLY — NOT DEPLOYED TO HOMEY**
Date: 2026-09-04

Observed live Homey flows:
- `EM v2 | 10 Input | EV Deadline Goal Adapter v0.1`
- `EM v2 | 00 Core Tick | v0.11h PINNED SOURCE`
- `EM v2 | 20 Power Intent | P1 v0.2.4 DUAL-SEMANTIC LOW-LOAD`
- `EM v2 | 60 Adapter | EV Power v0.1.1 TARGETED-READ SHADOW`
- `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.1 TARGETED-READ`
- `EM v2 | 60 Actuator | EV Power v0.2.2 TARGETED-READ LIVE OWNERSHIP`

## Corrected incident timeline

1. New website deadline command was written at approximately 07:19:30 Europe/Amsterdam:
   - deadline 08:00
   - current SOC 48%
   - target SOC 55%
   - goal 3.85 kWh
   - maxA 8
2. Deadline Goal Adapter computes `latestStart = deadline - goal/(maxA*690W)` = approximately 07:18:09.
3. Because the command was entered after latest-start, it is already catch-up / MUST as soon as Core sees it.
4. Charger target remained 0 A through 07:24:55.
5. At exactly 07:25:00 charger target changed to 8 A and remained 8 A afterwards.
6. Therefore the deadline execution chain works end-to-end; the earlier 07:20 FAIL conclusion was premature.

## Findings that are NOT defects

### Deadline MUST is not PV/export limited in the actual physical path

Core's `EM2_Control_EV.requestedPowerClass` is only a semantic wake signal for the current downstream design. Power Intent validates the EV mode against Core Decision and, for `TESLA_CHARGE_DEADLINE`, calculates numeric power independently:

```js
evW = Math.round((remainingKWh / hoursToDeadline) * 1000);
```

PV `flexExportBudgetW` is used for opportunity/buffer charging, not for the DEADLINE numeric target.

### `maxA` is propagated end-to-end

Deadline Goal Adapter publishes `EV Max laadstroom A`.
EV Power Adapter reads that variable directly and clamps:

```js
const maxConfig = num(maxVar?.value);
const MAX_A = Math.floor(Math.min(16, maxConfig ?? 16));
requestedA = Math.min(MAX_A, Math.floor(theoreticalA));
```

So the configured 8 A cap is already enforced by the live adapter.

## Confirmed primary issue — deadline command to Core latency

The deadline input adapter polls the website command every 1 minute.
The Core independently runs every 5 minutes.
There is no event-driven wake-up from a newly accepted deadline command into Core.

Observed race:

```text
07:19:30  website command written
~07:20    Core cycle can run before the 1-minute deadline adapter has published the new Logic values
~07:20    deadline adapter publishes new deadline after that Core cycle
07:25     next Core cycle sees catch-up/MUST
07:25     Power Intent -> Adapter -> Gate -> Actuator -> 8 A
```

This explains the measured 5.5 minute delay without requiring a downstream actuator fault.

### Operational consequence

For a normal future deadline this can delay reaction by nearly one Core period.
For a deadline already at or beyond latest-start, every minute matters. At 3.85 kWh and max 8 A the nominal required duration is ~41.8 minutes. Starting at 07:25 for an 08:00 deadline leaves only 35 minutes, so the requested target is no longer achievable within the configured current cap.

## Candidate fix A — event-driven Core wake-up on accepted EV deadline

Preferred minimal-load change: keep the 5-minute Core cadence, but add one event trigger to Core for a semantic deadline-input change.

Recommended trigger source: `EM2_EV_Goal_Input_Status` variable changed.

The deadline adapter already updates this status after publishing the validated Logic goal set. Core can therefore run immediately only when a deadline command changes/refreshes semantically, rather than polling faster.

Required guard:
- trigger only after the deadline adapter has completed publishing `EV Deadline actief`, `EV Deadline tijd`, `EV Resterend kWh`, `EV Max laadstroom A`, `EV Latest start`, and `EV Deadline status`;
- preserve existing 5-minute cron trigger;
- no direct physical device write from deadline adapter;
- Core remains the single device reader / decision owner.

Expected result for the observed test:

```text
07:19:30 command written
<= ~07:20:30 deadline adapter accepts/publishes command
immediately Core wakes from input-status change
seconds later Power Intent -> Adapter -> Gate -> Actuator
8 A applied without waiting until 07:25
```

## Candidate fix B — explicit infeasibility state

Current input validation accepts a future deadline even when `latestStart < now`. It marks catch-up, but does not explicitly say the target is now impossible at the configured `maxA`.

Add:

```js
const infeasibleAtMaxA = now > latestMs;
```

Recommended status contract:
- `DEADLINE_WAIT` when now < latestStart;
- `DEADLINE_CATCH_UP` when now >= latestStart but remaining time can still be met due rounding/tolerance;
- `DEADLINE_INFEASIBLE_AT_MAX_A` when required duration exceeds remaining wall-clock duration at configured maxA.

Do **not** reject the command purely because it is infeasible: the safest action is still immediate maximum permitted charging, while exposing that the target cannot be guaranteed.

## Freshness finding — keep under investigation, do not patch blindly

The live EV adapter and actuator both use `FRESH_MS = 120000`, while Core cadence is 5 minutes. This looked suspicious initially, but the event chain is normally re-generated immediately after a Core run, and actuator only runs when the gate changes. Therefore `120 s < 300 s` alone is **not sufficient proof** of a defect.

We do have earlier evidence of `STALE_INPUT -> 0 A`, so this remains a separate incident to reconstruct. Do not increase freshness to 420 s until the exact trigger that invoked the actuator with stale inputs is identified; extending freshness could mask a real revision/trigger fault.

## Required offline tests before Homey deployment

### T1 — new deadline wakes Core without waiting for cron
- website deadline becomes valid immediately after a Core tick
- deadline adapter publishes new goal set
- expected: Core invoked by semantic input-status event within seconds of adapter completion

### T2 — existing 5-minute cron remains valid
- no deadline changes
- expected: normal Core cadence unchanged

### T3 — deadline power path remains independent from PV
- MUST deadline, flexExportBudgetW = 0
- expected Power Intent > 0 based on remaining kWh / time
- adapter clamps to configured maxA, not PV budget

### T4 — maxA cap retained
- maxA = 8
- required target > 5.52 kW
- expected adapter requested_A = 8, never > 8

### T5 — infeasible deadline surfaced
- latestStart already in the past at command acceptance
- expected immediate Core wake-up + charging at permitted maxA
- status explicitly reports `DEADLINE_INFEASIBLE_AT_MAX_A`

### T6 — stale-input incident remains reproducible/understood
- reconstruct what changed the Gate/Actuator around the earlier 8 A -> 0 A event
- do not alter freshness until this trigger path is known

## Deployment gate

Do not deploy until:
1. the event-trigger change is represented as an exact Advanced Flow patch outside Homey;
2. offline logic tests T1–T5 pass;
3. stale-input issue is kept separate from the deadline-latency fix;
4. source hashes / exact flow definitions are recorded;
5. one controlled Homey update is prepared;
6. deployment occurs only with explicit approval;
7. post-deploy validation is read-only after the single intended change.

## Current verdict

- Deadline input: **PASS**
- Core deadline decision: **PASS**
- Deadline numeric Power Intent: **PASS**
- maxA clamp: **PASS**
- Adapter/Gate/Actuator end-to-end at 07:25: **PASS**
- Deadline responsiveness after new command: **FAIL / latency defect**
- Earlier `STALE_INPUT -> 0 A`: **OPEN SEPARATE DEFECT — root trigger not yet proven**

No physical Homey writes were performed while preparing or correcting this document.
