# Core v0.11c — Thermostat verification patch

Status: **PREPARED IN GITHUB / NOT DEPLOYED TO HOMEY**

Date: 2026-08-30

Target Homey flow: `EM v2 | 00 Core Tick | v0.11b (Planner WW Intent)`  
Flow ID: `227f8d3b-7551-46dd-837d-1b8c69add824`

## Purpose

Prevent Core from switching the electric boiler off immediately after a normal Planner/opportunity run when confirmed heating has occurred but the internal boiler thermostat has not yet had enough time to prove that the tank reached temperature.

The current daily goal latch remains authoritative and unchanged in principle:

- heating must first be confirmed while the boiler switch is ON and power is >1500 W;
- the goal is reached only after the boiler switch remains ON while power is <100 W for at least 10 minutes;
- Core must never infer `goalReachedToday=true` merely because a scheduled slot completed.

v0.11c adds only a bounded **thermostat verification hold** before selected non-critical `BOILER_OFF` decisions.

## Safety contract

The verification hold is allowed only when all of the following are true:

1. `goalReachedToday !== true`;
2. boiler switch is currently ON;
3. heating has already been confirmed (`st.heatingConfirmed === true`);
4. current local time is inside the normal WW operating window (`09:30 <= time < 19:00`);
5. P1 is fresh and the grid measurement is valid;
6. current import while the boiler is already ON is not above `BUDGET.maxDiscretionaryImportW`;
7. the original Core decision would otherwise be a **non-critical** `BOILER_OFF`;
8. verification has not exceeded 20 minutes.

The hold must never override:

- `MUST` OFF because electric boiler mode is not selected;
- `MUST` OFF at/after 19:00;
- `MUST` OFF after the daily goal is already latched;
- stale/invalid P1;
- unsafe current grid import;
- any future explicit electrical safety or phase-headroom gate.

## State additions

Persist two optional fields in `EM2_WW_State`:

```js
thermostatVerifyStartedAt: null,
thermostatVerifyReason: null
```

Do not create a new Logic variable and do not add a new Flow, trigger, cadence or device read.

When the boiler turns OFF, when the daily goal is latched, or when verification is no longer applicable, clear both fields.

## Constants

Add next to the existing Core constants:

```js
const THERMOSTAT_VERIFY_MAX_MS = 20 * 60 * 1000;
```

## Derived verification state

After the existing WW state accounting and before the WW decision tree, derive:

```js
const thermostatVerifyStartedMs = Date.parse(String(st.thermostatVerifyStartedAt || ''));
const thermostatVerifyElapsedMs = Number.isFinite(thermostatVerifyStartedMs)
  ? Math.max(0, Date.now() - thermostatVerifyStartedMs)
  : 0;
const thermostatVerifyActive = Number.isFinite(thermostatVerifyStartedMs)
  && thermostatVerifyElapsedMs < THERMOSTAT_VERIFY_MAX_MS;
const thermostatVerifyImportSafe = importW <= BUDGET.maxDiscretionaryImportW;
const thermostatVerifyBaseEligible =
  !goalReachedToday &&
  boilerOn &&
  st.heatingConfirmed === true &&
  minuteOfDay >= 570 &&
  minuteOfDay < 1140 &&
  p1Fresh &&
  gridMeasurementValid &&
  thermostatVerifyImportSafe;
```

The import check deliberately uses the **current measured import** because the boiler is already ON. Do not add `boilerExpectedW` again while deciding whether an existing run may be held.

## Decision integration rule

Do not publish `EM2_Control_WW` and then correct it. The verification logic must run **inside the single WW decision calculation, before the one existing `EM2_Control_WW` write**.

After the existing WW decision tree has produced `wwAction`, `wwPriority`, `wwReason` and `wwOpportunity`, but before building `wwc`, apply this narrow post-decision arbiter:

```js
const thermostatVerifyCandidate =
  wwAction === 'BOILER_OFF' &&
  wwPriority !== 'MUST' &&
  thermostatVerifyBaseEligible;

if (thermostatVerifyCandidate) {
  if (!thermostatVerifyActive) {
    st.thermostatVerifyStartedAt = new Date().toISOString();
    st.thermostatVerifyReason = `${wwOpportunity}:${wwReason}`;
  }

  const verifyStartMs = Date.parse(String(st.thermostatVerifyStartedAt || ''));
  const verifyElapsedMs = Number.isFinite(verifyStartMs)
    ? Math.max(0, Date.now() - verifyStartMs)
    : THERMOSTAT_VERIFY_MAX_MS;

  if (verifyElapsedMs < THERMOSTAT_VERIFY_MAX_MS) {
    wwAction = 'HOLD';
    wwPriority = 'SHOULD';
    wwReason = `Thermostaat-verificatie: boiler ON houden tot intern afschakelen is bevestigd; ${Math.round(verifyElapsedMs / 60000)}/20 min`;
    wwOpportunity = 'THERMOSTAT_VERIFY';
    recommendedRunLockMin = 0;
  }
}
```

### Important implementation correction

The snippet above starts the timer whenever there is no *active* timer. That must **not** allow an expired 20-minute window to restart indefinitely. Therefore the actual deployed implementation must distinguish `neverStarted` from `expired`.

Use this deployment-safe form instead:

```js
const thermostatVerifyStartedMs = Date.parse(String(st.thermostatVerifyStartedAt || ''));
const thermostatVerifyNeverStarted = !Number.isFinite(thermostatVerifyStartedMs);
const thermostatVerifyElapsedMs = thermostatVerifyNeverStarted
  ? 0
  : Math.max(0, Date.now() - thermostatVerifyStartedMs);
const thermostatVerifyWithinWindow = thermostatVerifyNeverStarted
  || thermostatVerifyElapsedMs < THERMOSTAT_VERIFY_MAX_MS;

const thermostatVerifyCandidate =
  wwAction === 'BOILER_OFF' &&
  wwPriority !== 'MUST' &&
  thermostatVerifyBaseEligible &&
  thermostatVerifyWithinWindow;

if (thermostatVerifyCandidate) {
  if (thermostatVerifyNeverStarted) {
    st.thermostatVerifyStartedAt = new Date().toISOString();
    st.thermostatVerifyReason = `${wwOpportunity}:${wwReason}`;
  }

  const verifyStartMs = Date.parse(String(st.thermostatVerifyStartedAt || ''));
  const verifyElapsedMs = Number.isFinite(verifyStartMs)
    ? Math.max(0, Date.now() - verifyStartMs)
    : THERMOSTAT_VERIFY_MAX_MS;

  if (verifyElapsedMs < THERMOSTAT_VERIFY_MAX_MS) {
    wwAction = 'HOLD';
    wwPriority = 'SHOULD';
    wwReason = `Thermostaat-verificatie: boiler ON houden tot intern afschakelen is bevestigd; ${Math.round(verifyElapsedMs / 60000)}/20 min`;
    wwOpportunity = 'THERMOSTAT_VERIFY';
    recommendedRunLockMin = 0;
  }
}
```

Once the timer is >=20 minutes, the original non-critical `BOILER_OFF` decision must pass through. The expired timer is cleared only after the boiler is actually observed OFF, so it cannot restart while the switch is still ON.

## Timer reset rules

Apply before persisting `EM2_WW_State` for the next tick:

```js
if (!boilerOn || goalReachedToday) {
  st.thermostatVerifyStartedAt = null;
  st.thermostatVerifyReason = null;
}
```

Do **not** clear an expired verification timer while the boiler remains ON; otherwise the next five-minute tick could start a fresh 20-minute window.

If a safety-critical branch produces `wwPriority === 'MUST'`, verification is bypassed. The existing physical OFF path then proceeds normally; the state fields clear on the following tick when `boilerOn === false` is observed.

## Goal-detection interaction

The existing thermostat latch logic remains unchanged:

```js
if (st.heatingConfirmed && boilerOn && powerW < 100) {
  st.lowAfterHeatingMin = (Number(st.lowAfterHeatingMin) || 0) + deltaMin;
  if (st.lowAfterHeatingMin >= 10 && !st.goalReachedToday) {
    st.goalReached = true;
    st.goalReachedToday = true;
    st.goalReachedAt = new Date().toISOString();
    st.goalLatchDate = today;
  }
} else if (powerW >= 100 || !boilerOn) {
  st.lowAfterHeatingMin = 0;
}
```

When the internal thermostat opens and power falls below 100 W while the switch remains ON, the existing 10-minute confirmation can therefore complete during the new bounded verification window.

## Observability additions

Add to `EM2_Control_WW.inputs`:

```js
thermostatVerifyStartedAt: st.thermostatVerifyStartedAt ?? null,
thermostatVerifyReason: st.thermostatVerifyReason ?? null,
thermostatVerifyElapsedMin: Number.isFinite(Date.parse(String(st.thermostatVerifyStartedAt || '')))
  ? Math.round(Math.max(0, Date.now() - Date.parse(String(st.thermostatVerifyStartedAt))) / 6000) / 10
  : 0,
thermostatVerifyMaxMin: 20
```

Add to `EM2_Control_WW.policy`:

```js
thermostatVerification: 'MAX_20_MIN_AFTER_CONFIRMED_HEATING_BEFORE_NONCRITICAL_OFF'
```

Add to `EM2_Control_WW.safety`:

```js
thermostatVerificationCannotOverrideMustOff: true,
thermostatVerificationRequiresFreshP1: true,
thermostatVerificationImportLimitW: BUDGET.maxDiscretionaryImportW
```

No new publication trigger is required. Existing Publisher data will expose the control object on its normal cadence.

## Versioning proposal

Only when deployed to Homey:

- Flow name: `EM v2 | 00 Core Tick | v0.11c (Planner WW + Thermostat Verify)`
- Core publisher version: `EM2_CORE_STATE_V0.11c`
- Keep `EM2_CONTROL_WW_V0.11` schema unless downstream consumers require a schema bump; these are additive fields and no existing command semantics change.

## No-change contract

v0.11c must not change:

- five-minute Core cadence;
- device read set;
- Planner v0.4.9 WW slot semantics;
- 19:00 hard WW deadline;
- boiler mode gate;
- catch-up semantics;
- post-goal SHOULD-only semantics;
- Power Intent ownership;
- Gate or actuator ownership;
- LIVE state;
- Publisher cadence;
- Tesla behavior;
- Quatt observe-only behavior;
- physical writes from Core (must remain zero).

## Deployment rule

Do not reconstruct Core from this patch. Fetch/capture the complete live v0.11b script, apply only the reviewed v0.11c delta, compare the full script, and then update the existing Advanced Flow once. This follows the Core repository change rule and avoids an intermediate control publication or partial runtime.
