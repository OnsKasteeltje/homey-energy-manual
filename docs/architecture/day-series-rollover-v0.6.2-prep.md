# Day Series rollover v0.6.2 — PREP ONLY / NOT DEPLOYED

Status: **prepared in GitHub only**. No Homey flow has been changed by this branch.

## Confirmed failure being addressed

The current `EM v2 | 70 History | Day Series v0.6.1 TARGETED LOCAL SAMPLER` resets the local day buffer when `date_local` changes. Unlike the older v0.5.x implementation, v0.6.1 does not persist the completed full-resolution day into `docs/data/energy-day-series-7d.json` before that reset. The rolling file therefore stopped after 2026-08-27 while live-day publication could continue independently.

## Candidate architecture

```text
EM2_State
   ↓ every 5 min
Day Series v0.6.2 local sampler
   ├─ normal run: same 2 targeted Logic reads as v0.6.1
   └─ calendar rollover only:
        copy completed local buffer → EM2_Day_Rollover_Queue_v1
        then start new local-day buffer

EM2_Day_Rollover_Queue_v1
   ↓ every 60 min / manual start
Rolling 7d Archive v0.2 LOW-LOAD
   ↓ idempotent merge by date
energy-day-series-7d.json
   ↓ after successful GitHub write
remove archived day from local queue
```

The existing `EM v2 | 76 Publish | Day Series v0.1.1 TARGETED LOW-FREQUENCY` remains unchanged and continues publishing the current live buffer to `docs/data/energy-day-v2.json` every 30 minutes.

The existing `EM v2 | 72 History | Immutable Day Archive v0.1` remains **disabled during this cutover**. It consumes `energy-day-series-7d.json`; it does not produce it.

## Safety properties

- No device reads or actuator writes are introduced.
- Normal 5-minute sampler runs retain exactly two targeted Logic reads.
- The broad Logic collection read occurs only in the once-per-day rollover branch to locate/create the handoff queue.
- Completed-day data is written to local Homey Logic before the live buffer is reset.
- The handoff is idempotent by `date_local`.
- The local queue holds at most two unarchived completed days. A third unresolved rollover fails closed with `DAY_ROLLOVER_QUEUE_FULL` instead of silently overwriting evidence.
- The rolling publisher only removes queue entries after a successful or already-idempotent representation in the rolling file.
- The rolling file retains the latest six completed days, matching the established UI contract of today + six prior available days.

## Candidate files

- `src/homey/history/day-series-v0.6.2-local-rollover.homeyscript.js`
- `src/homey/history/day-series-rolling-7d-publisher-v0.2.homeyscript.js`

## Proposed Homey cutover — do not execute yet

1. Capture/read the current v0.6.1 sampler immediately before change.
2. Replace only its HomeyScript source with the reviewed v0.6.2 candidate; keep the existing flow ID and 5-minute schedule.
3. Smoke-run the sampler once during the same calendar day. Expected: current-day `sample_count` continues, no queue creation is required, no GitHub call occurs.
4. Create a new Advanced Flow `EM v2 | 72 History | Rolling 7d Archive v0.2 LOW-LOAD`, scheduled every 60 minutes + manual start, with the candidate archive script.
5. Keep the new archive flow disabled until a synthetic/non-destructive rollover test has passed.
6. Validate queue handoff with a test copy of the buffer or controlled date fixture outside the production buffer. Never force the production date backwards/forwards.
7. Enable the archive flow only after readback confirms its exact source and schedule.
8. At the first natural midnight rollover, verify in order: old day appears in queue → new live buffer starts → rolling publisher writes old day → queue clears → selector exposes the completed date.

## Acceptance criteria

- `energy-day-v2.json` remains current and continues to grow during the day.
- At natural rollover, the previous day is not lost even if GitHub is temporarily unavailable.
- `energy-day-series-7d.json` gains exactly one completed day and never contains today.
- Duplicate runs do not duplicate a date.
- After >6 completed days, only the six newest completed dates remain.
- No device reads/writes are added.
- No second realtime battery/EV/WW control path is introduced.

## Historical gap 2026-08-28 through 2026-08-31

This change prevents future loss. It does **not** fabricate the missing full-resolution days 2026-08-28 through 2026-08-31. Those dates may only be reconstructed if an authoritative source containing the original samples is found. Otherwise they remain explicitly unavailable.
