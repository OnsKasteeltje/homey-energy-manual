# EV deadline responsiveness fix — PREP ONLY / NOT DEPLOYED

Status: **PREP ONLY — NOT DEPLOYED TO HOMEY**
Date: 2026-09-04

## Confirmed live behavior

- Website deadline accepted around 07:19:30 Europe/Amsterdam.
- Deadline was already beyond `latestStart` when accepted.
- Charger target stayed 0 A until 07:24:55.
- Charger target changed to 8 A at exactly 07:25:00 and remained there.
- Therefore the deadline power path itself is healthy end-to-end.

## Narrow deployment candidate

Only two changes remain in scope:

1. Make `EM2_EV_Goal_Input_Status` a semantic/idempotent final commit marker in the Deadline Goal Adapter.
2. Add one Core trigger on `EM2_EV_Goal_Input_Status changed`, while preserving the existing 5-minute cron and manual Start.

Also add observability status `DEADLINE_INFEASIBLE_AT_MAX_A` when the deadline can no longer be met at configured maximum current, with a 60 s tolerance around latestStart.

## Important semantic behavior

The marker is not a heartbeat and contains no polling timestamp.

It stays byte-identical while:
- requestId is unchanged;
- command values are unchanged;
- derived deadline status is unchanged.

The same request is intentionally allowed to mutate on real derived-status transitions:
- `DEADLINE_WAIT -> DEADLINE_CATCH_UP`;
- `DEADLINE_CATCH_UP -> DEADLINE_INFEASIBLE_AT_MAX_A`.

Those transitions are beneficial: they wake Core near latestStart without raising normal Core cadence to once per minute.

## Offline gate result

All narrow-scope offline gates pass after correcting the idempotency definition:

- R1 semantic/idempotent marker: PASS
- R2 marker-last event commit: PASS for event path
- R3 existing cron/manual paths preserved: PASS
- R4 observed incident replay: PASS
- R5 latestStart semantic wake: PASS
- R6 infeasibility observability only: PASS
- R7 scope protection: PASS

The preserved independent 5-minute cron can theoretically overlap a goal-update transaction; that pre-existing cross-flow race is not worsened by this patch and is outside this minimal responsiveness change.

## Explicitly out of scope

No change to:
- Power Intent EV calculation;
- maxA electrical clamp;
- EV Adapter mapping;
- EV Gate validation;
- Actuator behavior;
- `FRESH_MS`;
- physical writer logic;
- earlier `STALE_INPUT -> 0 A` root-cause investigation.

## Remaining deployment precondition

Before Homey update:
1. render exact full Advanced Flow payloads for the Deadline Goal Adapter and Core;
2. structurally compare them against the current live flows;
3. verify only the intended adapter script delta and one Core trigger card differ;
4. keep PR draft until explicit deployment approval.

No physical Homey writes were performed during preparation or offline validation.
