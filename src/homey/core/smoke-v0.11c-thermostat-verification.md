# Core v0.11c — Thermostat verification smoke plan

Status: **PREPARED / NOT EXECUTED**

Date: 2026-08-30

Target: `EM v2 | 00 Core Tick | v0.11c (Planner WW + Thermostat Verify)` after deployment.

## Goal

Prove that the bounded thermostat-verification hold gives the boiler enough time to demonstrate internal thermostat cut-off without weakening any existing Core safety gate.

## Preconditions

- Homey is not rate-limited.
- Core v0.11c is enabled and `broken=false`.
- No other EMS Homey changes are performed during the smoke.
- Boiler mode is active.
- `EM2_WW_State.heatingConfirmed=true` has been reached naturally.
- Daily goal has not yet been latched.
- P1 is fresh.

## Scenario A — non-critical slot end enters verification

Expected trigger:

- boiler is ON;
- confirmed heating exists;
- Planner/opportunity run ends;
- existing Core decision would normally be non-critical `BOILER_OFF`;
- current import is <= configured discretionary import limit.

PASS evidence:

1. `EM2_Control_WW.action = HOLD`.
2. `EM2_Control_WW.opportunity = THERMOSTAT_VERIFY`.
3. `priority = SHOULD`, never `MUST`.
4. `thermostatVerifyStartedAt` is set once.
5. Timer age increases across Core ticks and does not restart.
6. Boiler switch stays ON during verification.
7. No extra Flow, trigger, device read or physical write is introduced by Core.

## Scenario B — thermostat cuts element and goal latches

During Scenario A, allow the boiler internal thermostat to cut the heating element naturally.

PASS evidence:

1. boiler switch remains ON;
2. measured boiler power falls below 100 W;
3. `lowAfterHeatingMin` accumulates only while switch remains ON;
4. after at least 10 confirmed minutes, `goalReachedToday=true`;
5. `goalLatchDate` equals the local calendar date;
6. `remainingFallbackMin=0`;
7. Core then allows the existing goal-reached OFF behavior;
8. next Planner refresh removes future mandatory `DEADLINE_REQUIRED` WW obligation for the same day, if such future blocks existed.

## Scenario C — 20-minute maximum is hard

If the internal thermostat does not cut the element during the verification window:

PASS evidence:

1. verification never exceeds 20 minutes by restarting;
2. after expiry, the original non-critical `BOILER_OFF` decision passes through;
3. boiler is observed OFF on the next state sample;
4. verification state is then cleared;
5. `goalReachedToday` remains false unless the normal low-power thermostat criterion was actually met.

## Scenario D — MUST OFF bypasses verification

Test by observation only; do not manufacture unsafe conditions merely for the smoke.

Any naturally occurring `MUST` OFF must bypass verification immediately. Examples:

- electric boiler mode disabled;
- local time reaches 19:00;
- daily goal already reached.

PASS evidence: Core outputs `BOILER_OFF` with `priority=MUST`; `THERMOSTAT_VERIFY` is not selected.

## Scenario E — stale/invalid P1 bypasses verification

Do not deliberately overload or disconnect Homey. If a naturally stale/invalid P1 sample occurs while a non-critical OFF is pending, verification must not hold the boiler ON.

PASS evidence:

- `p1Fresh=false` or `gridMeasurementValid=false` prevents thermostat verification;
- original OFF path proceeds according to existing Core safety behavior.

## Scenario F — unsafe current import bypasses verification

If current net import while the boiler is already ON exceeds `BUDGET.maxDiscretionaryImportW`, verification must not keep the run alive.

PASS evidence:

- `thermostatVerifyImportSafe=false`;
- `THERMOSTAT_VERIFY` is not selected;
- original OFF decision proceeds.

## Regression checks

PASS only if all are unchanged:

- Core cadence remains every 5 minutes;
- Core performs no physical device writes;
- Planner v0.4.9 remains the only planned WW schedule source;
- realtime P1 export remains an independent valid WW opportunity;
- 19:00 deadline remains hard;
- post-goal behavior remains SHOULD-only/never MUST reheat;
- Power Intent, WW Adapter/Gate and actuator ownership remain unchanged;
- Publisher cadence remains unchanged;
- Tesla logic is unaffected;
- no increase in Flow fan-out was added.

## Rollback

Rollback unit is the complete pre-v0.11c Core Advanced Flow definition. If any regression is observed, restore the complete previous v0.11b flow rather than editing individual cards live.

## Final acceptance

Mark v0.11c PASS only after at least one natural run demonstrates either:

- thermostat cut-off -> 10-minute low-power confirmation -> daily goal latch, **or**
- full 20-minute verification expiry -> clean non-critical OFF without timer restart,

and all safety bypass/regression checks remain intact.
