# Core v0.11d — thermostat verification re-arm smoke plan

Status: **PREPARED / NOT EXECUTED**

Date: 2026-08-30

Target: `EM v2 | 00 Core Tick | v0.11d (Thermostat Verification Rearm)` after deployment.

## Purpose

Validate that v0.11d fixes the v0.11c same-physical-run re-arm defect without reintroducing endless thermostat-verification renewal loops.

## Offline regression model

Model the WW verifier as a state machine with these inputs per Core tick:

- `boilerOn`
- `powerW`
- `heatingConfirmed`
- `goalReachedToday`
- `thermostatVerifyRequested`
- `p1Fresh`
- `gridMeasurementValid`
- `thermostatVerifyImportSafe`
- active verification age

Expected persistent fields:

- `thermostatVerifyActive`
- `thermostatVerifyStartedAt`
- `thermostatVerifyEndedAt`
- `thermostatVerifyEndReason`
- `thermostatVerifyRearmReady`
- `thermostatVerifyStopRequested`
- `thermostatVerifyEpisodeKey`

## Scenario A — first discretionary OFF starts one verification

Sequence:

1. Boiler ON, power >1500 W, heating confirmed.
2. No discretionary stop requested.
3. Stop request changes `false -> true`.

PASS:

- one `THERMOSTAT_VERIFY` episode starts;
- output is `HOLD/MAY`;
- `rearmReady=false` immediately after start;
- episode key is set once;
- start time does not move on later ticks.

## Scenario B — continuously pending OFF cannot renew

Sequence:

1. Start Scenario A.
2. Keep the same stop request continuously true for >40 minutes.
3. Keep power >1500 W so no thermostat goal evidence appears.

PASS:

- first episode expires at <=20 minutes;
- original discretionary OFF passes through after expiry;
- no second verification episode starts while the stop request remains continuously true;
- episode start time/key do not renew;
- `rearmReady=false` throughout the continuous stop condition.

## Scenario C — material opportunity return re-arms later OFF

Sequence:

1. Start and expire/abort a first verification episode.
2. Before physical OFF occurs, a valid opportunity returns so `thermostatVerifyRequested` becomes false for at least one normal Core tick.
3. Boiler remains ON, power >1500 W and heating remains confirmed.
4. Later the opportunity ends again so stop request changes `false -> true`.

PASS:

- the false tick sets `thermostatVerifyRearmReady=true`;
- the later false -> true edge starts exactly one new verification episode;
- the new episode has a new key/start time;
- this works even though `runStartedAt` is unchanged from the earlier episode.

This is the regression that v0.11c fails and v0.11d must fix.

## Scenario D — no re-arm from elapsed time alone

Sequence:

1. Complete/expire one verification.
2. Keep stop request true.
3. Wait multiple ticks.

PASS:

- `rearmReady` remains false;
- no new episode starts.

## Scenario E — no re-arm from latched heatingConfirmed alone

Sequence:

1. Complete one verification.
2. Keep stop request true.
3. Keep `heatingConfirmed=true` but do not create a false stop-request tick.

PASS:

- no re-arm occurs.

## Scenario F — thermostat cutoff still latches daily goal

Sequence:

1. Enter verification.
2. Managed switch remains ON.
3. Actual boiler power falls below 100 W.
4. Keep `<100 W` for the existing 10-minute confirmation period.

PASS:

- `lowAfterHeatingMin` accumulates only while `boilerOn=true`;
- after >=10 minutes, `goalReachedToday=true`;
- `goalLatchDate` is today;
- verification ends with `GOAL_CONFIRMED`;
- no new verification is armed after daily goal.

## Scenario G — safety aborts remain immediate

For each naturally or synthetically modeled condition below while verification is active:

- `p1Fresh=false`;
- `gridMeasurementValid=false`;
- `thermostatVerifyImportSafe=false`.

PASS:

- verification ends immediately;
- original OFF path proceeds;
- no automatic re-arm occurs while stop request stays true.

## Scenario H — MUST precedence unchanged

Model each condition independently:

- boiler mode disabled;
- local time >=19:00;
- daily goal already reached;
- catch-up/MUST path.

PASS:

- thermostat verification does not intercept the existing mandatory branch;
- physical-writer ownership remains downstream of Power Intent -> WW Adapter -> Gate -> actuator.

## Scenario I — physical OFF resets episode state

Sequence:

1. Complete any verification path.
2. Next state sample reports `boilerOn=false`.

PASS:

- episode key/start/end fields are cleared or normalized for a clean next run;
- `rearmReady=true` for the next physical ON-run;
- `stopRequested=false` baseline is restored.

## Scenario J — 2026-08-30 incident replay

Replay the observed shape conceptually:

- same physical ON-run lasts ~80 minutes;
- an earlier bounded verification is consumed;
- opportunity later returns while boiler keeps heating;
- later at 16:10 another discretionary OFF appears while power is still ~1966 W.

PASS under v0.11d:

- the intervening cleared stop request re-arms verification;
- the 16:10 new OFF edge is intercepted by a fresh bounded `THERMOSTAT_VERIFY` episode instead of being immediately passed through solely because the physical run key is unchanged.

## No-change regression checks

PASS only if unchanged:

- Core cadence = 5 minutes;
- Core remains device-write free;
- no new Homey Flow or trigger is added;
- no new broad Homey collection scan is added;
- Planner v0.4.9 semantics unchanged;
- WW Power Intent/Adapter/Gate/Actuator ownership unchanged;
- 19:00 stop unchanged;
- post-goal policy unchanged;
- Quatt remains observe-only;
- Tesla decision logic unchanged;
- Publisher cadence/fan-out unchanged.

## Deployment acceptance

Do not mark v0.11d PASS until both are demonstrated:

1. offline state-machine regression A-J passes; and
2. one natural live run demonstrates either real thermostat cutoff -> 10-minute low-power goal latch, or a later same-run discretionary OFF correctly starts a second episode only after a genuine intervening stop-request clear.
