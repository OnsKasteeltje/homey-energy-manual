# Core v0.11c — thermostat verification candidate

Status: **PREPARED IN GITHUB / NOT DEPLOYED TO HOMEY**

Baseline: live Homey `EM v2 | 00 Core Tick | v0.11b (Planner WW Intent)` captured on 2026-08-30.

## Objective

Prevent Core from prematurely switching the managed boiler switch OFF immediately after a confirmed heating run when a discretionary stop condition appears. This gives the boiler's internal thermostat a bounded observation window to produce actual `<100 W` evidence while the managed switch stays ON, allowing the existing daily-goal detector to latch `goalReachedToday=true` from real thermostat behavior.

The change must never infer the daily goal merely because EMS wanted to switch the boiler OFF.

## New WW-state fields

Add these fields to the daily WW state object; initialize conservatively when absent:

```js
thermostatVerifyActive:false,
thermostatVerifyStartedAt:null,
thermostatVerifyExpired:false,
thermostatVerifyReason:null
```

On an existing same-day state, normalize before use:

```js
if(typeof st.thermostatVerifyActive!=='boolean')st.thermostatVerifyActive=false;
if(typeof st.thermostatVerifyExpired!=='boolean')st.thermostatVerifyExpired=false;
if(!('thermostatVerifyStartedAt' in st))st.thermostatVerifyStartedAt=null;
if(!('thermostatVerifyReason' in st))st.thermostatVerifyReason=null;
```

## Verification timing

Add a fixed maximum observation window:

```js
const THERMOSTAT_VERIFY_MAX_MIN=20;
```

After `runMin` and current WW inputs are available:

```js
const thermostatVerifyStartedMs=Date.parse(String(st.thermostatVerifyStartedAt||''));
const thermostatVerifyAgeMin=Number.isFinite(thermostatVerifyStartedMs)
  ?Math.max(0,(Date.now()-thermostatVerifyStartedMs)/60000)
  :0;

if(st.thermostatVerifyActive&&thermostatVerifyAgeMin>=THERMOSTAT_VERIFY_MAX_MIN){
  st.thermostatVerifyActive=false;
  st.thermostatVerifyExpired=true;
  st.thermostatVerifyReason='MAX_20_MIN_EXPIRED';
}
```

A verification that expired on this calendar day must **not automatically restart** on each subsequent discretionary OFF evaluation. `thermostatVerifyExpired` remains latched until the day-state resets or a genuinely new confirmed heating cycle is established after the expired verification.

## Rearm rule

A new confirmed heating cycle may re-arm the detector only from actual heating evidence, not from policy intent:

```js
if(heatingNow&&st.heatingConfirmed&&st.thermostatVerifyExpired){
  // Re-arm only after a newly observed heating period, not merely because the switch is ON.
  const verifyEndedMs=Date.parse(String(st.thermostatVerifyStartedAt||''));
  if(Number.isFinite(verifyEndedMs)&&Date.now()-verifyEndedMs>=THERMOSTAT_VERIFY_MAX_MIN*60000){
    st.thermostatVerifyExpired=false;
    st.thermostatVerifyStartedAt=null;
    st.thermostatVerifyReason='REARMED_BY_CONFIRMED_HEATING';
  }
}
```

Implementation may use an equivalent simpler state transition, but it must preserve the invariant: no endless 20-minute renewal loop.

## Goal-latch interaction

Keep the existing thermostat evidence unchanged:

```js
if(st.heatingConfirmed&&boilerOn&&powerW<100){
  st.lowAfterHeatingMin=(Number(st.lowAfterHeatingMin)||0)+deltaMin;
  if(st.lowAfterHeatingMin>=10&&!st.goalReachedToday){
    st.goalReached=true;
    st.goalReachedToday=true;
    st.goalReachedAt=new Date().toISOString();
    st.goalLatchDate=today;
    st.thermostatVerifyActive=false;
    st.thermostatVerifyExpired=false;
    st.thermostatVerifyReason='GOAL_CONFIRMED';
  }
}else if(powerW>=100||!boilerOn){
  st.lowAfterHeatingMin=0;
}
```

Do **not** count `lowAfterHeatingMin` while `boilerOn=false`.

## Eligibility to start verification

Verification may start only when all are true:

```js
const thermostatVerifyBaseEligible=
  mode &&
  minuteOfDay<1140 &&
  !goalReachedToday &&
  boilerOn &&
  st.heatingConfirmed===true &&
  !catchupRequired &&
  !st.thermostatVerifyActive &&
  !st.thermostatVerifyExpired &&
  p1Fresh &&
  gridMeasurementValid;
```

It is **not** an independent start policy. It can only intercept an otherwise-discretionary `BOILER_OFF` decision after the normal run-lock has elapsed.

## Mandatory safety precedence

These branches remain above thermostat verification and are never intercepted:

- boiler mode not selected -> existing `MUST` OFF behavior;
- `minuteOfDay >= 1140` -> existing 19:00 `MUST` OFF behavior;
- `goalReachedToday` -> existing goal/post-goal behavior;
- catch-up `MUST` behavior;
- stale/invalid P1 or any future explicit electrical safety gate;
- import condition where keeping the boiler energized would exceed the existing discretionary import ceiling.

For verification, projected import must remain within the existing `BUDGET.maxDiscretionaryImportW` ceiling:

```js
const thermostatVerifyImportSafe=
  importW+BUDGET.boilerExpectedW<=BUDGET.maxDiscretionaryImportW;
```

## Single-decision integration

Do not write `EM2_Control_WW` before this decision is resolved. No second correction write is allowed.

Immediately before the current discretionary stop branches, compute whether the current branch would otherwise stop the boiler. The implementation should preserve branch semantics; conceptually:

```js
const discretionaryPlannerStop=
  boilerOn&&plannerStarted&&!plannerOpportunity;

const discretionaryImportOrPriceStop=
  boilerOn&&!opportunity&&(expensive||importW>500);

const discretionaryStopRequested=
  discretionaryPlannerStop||discretionaryImportOrPriceStop;

if(
  discretionaryStopRequested &&
  thermostatVerifyBaseEligible &&
  thermostatVerifyImportSafe
){
  st.thermostatVerifyActive=true;
  st.thermostatVerifyStartedAt=new Date().toISOString();
  st.thermostatVerifyExpired=false;
  st.thermostatVerifyReason=discretionaryPlannerStop
    ?'DEFER_PLANNER_SLOT_END_FOR_THERMOSTAT_EVIDENCE'
    :'DEFER_DISCRETIONARY_STOP_FOR_THERMOSTAT_EVIDENCE';
}
```

Then insert the active-verification branch **after run-lock handling and before the existing discretionary OFF branches**:

```js
else if(boilerOn&&st.thermostatVerifyActive){
  if(!p1Fresh||!gridMeasurementValid){
    st.thermostatVerifyActive=false;
    st.thermostatVerifyReason='ABORT_P1_INVALID';
    wwAction='BOILER_OFF';
    wwPriority='SHOULD';
    wwReason='Thermostaat-verificatie afgebroken: P1 niet vers/geldig';
    wwOpportunity='THERMOSTAT_VERIFY_ABORT';
  }
  else if(!thermostatVerifyImportSafe){
    st.thermostatVerifyActive=false;
    st.thermostatVerifyReason='ABORT_IMPORT_BUDGET';
    wwAction='BOILER_OFF';
    wwPriority='SHOULD';
    wwReason=`Thermostaat-verificatie afgebroken: geprojecteerde import ${Math.round(importW+BUDGET.boilerExpectedW)} W boven ${BUDGET.maxDiscretionaryImportW} W budget`;
    wwOpportunity='THERMOSTAT_VERIFY_ABORT';
  }
  else{
    wwAction='HOLD';
    wwPriority='MAY';
    wwReason=`Thermostaat-verificatie: wacht op <100 W bewijs, ${Math.round(thermostatVerifyAgeMin)}/${THERMOSTAT_VERIFY_MAX_MIN} min`;
    wwOpportunity='THERMOSTAT_VERIFY';
    recommendedRunLockMin=0;
  }
}
```

An implementation may fold the two abort conditions into earlier safety gates, but externally observable behavior must be equivalent.

## Important state-write ordering

Because the verification fields are modified during WW decision construction, ensure the final `EM2_WW_State` written for the tick contains those final verification values. The current v0.11b writes `EM2_WW_State` before the WW control branch. v0.11c must therefore either:

1. move the single `EM2_WW_State` semantic write until after the WW decision has finalized the verification fields, or
2. compute all verification state transitions before the existing WW-state write.

Do **not** add a second unconditional WW-state write. Preserve semantic suppression/fan-out discipline.

## Control observability additions

Add to `EM2_Control_WW.inputs`:

```js
thermostatVerifyActive:st.thermostatVerifyActive===true,
thermostatVerifyStartedAt:st.thermostatVerifyStartedAt??null,
thermostatVerifyAgeMin:Math.round(thermostatVerifyAgeMin*10)/10,
thermostatVerifyExpired:st.thermostatVerifyExpired===true,
thermostatVerifyReason:st.thermostatVerifyReason??null
```

Add to policy:

```js
thermostatVerificationMaxMin:20,
thermostatVerificationLowThresholdW:100,
thermostatVerificationLowConfirmMin:10,
thermostatVerificationRequiresConfirmedHeating:true
```

Add to safety:

```js
thermostatVerificationDoesNotInferGoal:true,
thermostatVerificationCannotOverrideMustOff:true,
thermostatVerificationImportGuarded:true
```

## Version metadata

Target flow name:

`EM v2 | 00 Core Tick | v0.11c (Thermostat Verification)`

Target publisher version constant in Core state:

`EM2_CORE_STATE_V0.11c`

Keep existing Core public/control schemas unchanged unless a schema change is strictly required for compatibility. New optional JSON fields do not by themselves require breaking downstream contracts.

## No-change contract

v0.11c must not change:

- Core 5-minute cadence;
- targeted device set;
- broad Logic-read situation (this WW patch does not attempt the separate Core-input aggregation migration);
- Planner v0.4.9 interpretation;
- Tesla decision semantics;
- Power Intent ownership;
- WW actuator gate/ownership;
- Publisher cadence;
- Quatt observe-only behavior;
- 19:00 hard WW stop;
- same-day goal latch semantics;
- physical-write rule: Core itself performs no physical device writes.

## Deployment gate

Do not deploy to Homey until a diff review confirms that only:

1. version/name/note metadata;
2. thermostat-verification WW state fields;
3. bounded verification decision logic;
4. associated WW observability fields

have changed relative to the live v0.11b baseline.
