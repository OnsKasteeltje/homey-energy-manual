# EV deadline responsiveness — offline acceptance tests

Status: **PREP ONLY / NOT DEPLOYED**

## Gate R1 — idempotent marker

Given the same accepted website command is read on six consecutive 1-minute polls:

Expected:
- goal variables unchanged after first commit;
- `EM2_EV_Goal_Input_Status` changes exactly once;
- therefore the new Core event trigger fires exactly once, not six times.

**PASS criterion:** marker strings for polls 2–6 are byte-identical to poll 1.

## Gate R2 — atomic commit order

Given a new valid request:

Expected write order:
1. `EV Deadline actief`
2. `EV Deadline tijd`
3. `EV Doel kWh`
4. `EV Resterend kWh`
5. `EV Max laadstroom A`
6. `EV Latest start`
7. `EV Deadline status`
8. `EM2_EV_Goal_Input_Status` **last**

**PASS criterion:** Core can never wake from the semantic marker while only part of the new goal set has been committed.

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

## Gate R5 — infeasibility status

Use `neededMs = goalKWh / (maxA*690/1000) * 3600000` and `latestStart = deadline-neededMs`.

Expected:
- now < latestStart => `DEADLINE_WAIT`;
- 0 <= now-latestStart <= 60000 ms => `DEADLINE_CATCH_UP`;
- now-latestStart > 60000 ms => `DEADLINE_INFEASIBLE_AT_MAX_A`.

**PASS criterion:** infeasible status is observability only; command remains active and existing downstream current cap remains unchanged.

## Gate R6 — scope protection

Diff must contain no change to:
- Power Intent EV power calculation;
- `EV Max laadstroom A` electrical clamp behavior;
- EV adapter mapping;
- Gate validation;
- Actuator `FRESH_MS`;
- physical writer behavior.

**PASS criterion:** only deadline adapter marker/status logic plus one Core trigger card are deployment candidates.
