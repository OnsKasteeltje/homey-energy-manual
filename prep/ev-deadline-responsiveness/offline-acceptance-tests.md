# EV deadline responsiveness — offline acceptance tests

Status: **PREP ONLY / NOT DEPLOYED**

## Gate R1 — semantic/idempotent marker

Given the same accepted website command is read on consecutive 1-minute polls while it remains in the **same derived deadline-status band**:

Expected:
- goal variables remain unchanged after the first commit;
- `EM2_EV_Goal_Input_Status` remains byte-identical;
- therefore the new Core event trigger does not fire again merely because another poll occurred.

A marker mutation **is intentionally allowed and required** when the semantic deadline state changes for the same request, e.g.:
- `DEADLINE_WAIT -> DEADLINE_CATCH_UP`;
- `DEADLINE_CATCH_UP -> DEADLINE_INFEASIBLE_AT_MAX_A`;
- active -> inactive/rejected/fetch-failed.

This is useful: the 1-minute input adapter can wake Core near `latestStart` without increasing Core's normal cron cadence.

**PASS criterion:** identical command + identical derived status => byte-identical marker. A marker change requires a real input or derived-status transition, never polling time alone.

## Gate R2 — event commit order

Given a new valid request, the event-driven transaction writes:
1. `EV Deadline actief`
2. `EV Deadline tijd`
3. `EV Doel kWh`
4. `EV Resterend kWh`
5. `EV Max laadstroom A`
6. `EV Latest start`
7. `EV Deadline status`
8. `EM2_EV_Goal_Input_Status` **last**

**PASS criterion:** the new marker-triggered Core path cannot start before the complete goal set has been written.

Note: the preserved independent 5-minute cron can theoretically overlap a goal-update transaction; this patch does not claim cross-flow transactional locking. That pre-existing race is outside this minimal responsiveness change and is not worsened by the marker trigger.

## Gate R3 — event wake does not replace cron

Core flow after patch must contain all three entry paths:
- current 5-minute cron -> existing Core HomeyScript action;
- current manual Start -> existing Core HomeyScript action;
- new `EM2_EV_Goal_Input_Status changed` -> same existing Core HomeyScript action.

**PASS criterion:** no existing card/script is removed or modified for the wake-up change.

## Gate R4 — observed incident replay

Replay semantic timing:
- Core tick just before new deadline goal commit;
- deadline adapter accepts an already-late deadline on next 1-minute poll;
- marker commits last.

Old behavior: waits until next 5-minute Core tick.
New expected behavior: marker change immediately invokes Core, then existing Power Intent -> Adapter -> Gate -> Actuator chain proceeds.

**PASS criterion:** no dependence on the next 5-minute cron for first deadline reaction.

## Gate R5 — latestStart transition wake

Given an active deadline was accepted well before `latestStart` and no input fields change afterwards:
- while `now < latestStart`, marker remains stable in `DEADLINE_WAIT`;
- first poll at/after `latestStart` moves marker to `DEADLINE_CATCH_UP` and wakes Core;
- if still active more than 60 s after latestStart, marker may transition once to `DEADLINE_INFEASIBLE_AT_MAX_A` and wake Core once more.

**PASS criterion:** at most semantic transition events occur; no once-per-minute Core wake loop.

## Gate R6 — infeasibility status

Use `neededMs = goalKWh / (maxA*690/1000) * 3600000` and `latestStart = deadline-neededMs`.

Expected:
- now < latestStart => `DEADLINE_WAIT`;
- 0 <= now-latestStart <= 60000 ms => `DEADLINE_CATCH_UP`;
- now-latestStart > 60000 ms => `DEADLINE_INFEASIBLE_AT_MAX_A`.

**PASS criterion:** infeasible status is observability only; command remains active and existing downstream current cap remains unchanged.

## Gate R7 — scope protection

Diff must contain no change to:
- Power Intent EV power calculation;
- `EV Max laadstroom A` electrical clamp behavior;
- EV adapter mapping;
- Gate validation;
- Actuator `FRESH_MS`;
- physical writer behavior.

**PASS criterion:** only deadline adapter marker/status logic plus one Core trigger card are deployment candidates.

## Offline verdict (2026-09-04)

- R1 semantic/idempotent marker: **PASS after clarification**
- R2 marker-last event commit: **PASS for event path**
- R3 cron/manual paths preserved: **PASS**
- R4 observed 07:19:30 -> 07:25 incident replay: **PASS by construction**
- R5 latestStart semantic wake: **PASS and beneficial**
- R6 infeasibility observability only: **PASS**
- R7 scope protection: **PASS**

Remaining deployment precondition: convert the prepared adapter delta and Core trigger into exact full Advanced Flow payloads and compare those payloads structurally against the current live flows before any Homey update.
