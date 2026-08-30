# Core v0.11b — live Homey baseline capture

Date: 2026-08-30

Source: live Homey Advanced Flow read immediately before preparing v0.11c.

## Runtime identity

- Flow ID: `227f8d3b-7551-46dd-837d-1b8c69add824`
- Name: `EM v2 | 00 Core Tick | v0.11b (Planner WW Intent)`
- Folder: `24e6cfed-29f8-414d-a4fb-b54a4610fc12`
- Enabled: `true`
- Broken: `false`
- Triggerable: `true`
- Normal cadence: every 5 minutes
- Manual start card present
- Runtime script card: `33333333-0981-4981-8981-333333333333`
- Physical writes in Core: none; Core remains SHADOW/read-only.

## Relevant current WW state logic

The live v0.11b runtime currently resets thermostat-low confirmation whenever the managed boiler switch is OFF:

```js
if(heatingNow){
  st.heatingConfirmMin=(Number(st.heatingConfirmMin)||0)+deltaMin;
  if(st.heatingConfirmMin>=15)st.heatingConfirmed=true;
}else if(!st.heatingConfirmed)st.heatingConfirmMin=0;

if(st.heatingConfirmed&&boilerOn&&powerW<100){
  st.lowAfterHeatingMin=(Number(st.lowAfterHeatingMin)||0)+deltaMin;
  if(st.lowAfterHeatingMin>=10&&!st.goalReachedToday){
    st.goalReached=true;
    st.goalReachedToday=true;
    st.goalReachedAt=new Date().toISOString();
    st.goalLatchDate=today;
  }
}else if(powerW>=100||!boilerOn){
  st.lowAfterHeatingMin=0;
}
```

This is intentional thermostat semantics: goal evidence is accepted only while the managed switch remains ON.

## Relevant current run/stop logic

Current start-reason/run-lock derivation:

```js
const startReason=String(st.runStartReason||'UNKNOWN'),
  priceStarted=startReason==='PRICE_NEGATIVE'||startReason==='PRICE_CHEAP',
  plannerStarted=startReason==='PLANNER_GRID'||startReason==='PLANNER_PV_CONFIRMED',
  catchupStarted=startReason==='CATCHUP',
  postGoalRun=startReason.startsWith('POST_GOAL_'),
  postGoalRunLockMin=(startReason.includes('PRICE')||startReason.includes('CHEAP'))?30:15,
  runLockMin=postGoalRun?postGoalRunLockMin:catchupStarted?0:priceStarted?30:15,
  runLocked=boilerOn&&!catchupStarted&&runMin<runLockMin;
```

Current authoritative safety-first branches before discretionary stop logic:

```js
if(!mode){
  wwAction=boilerOn?'BOILER_OFF':'HOLD';
  wwPriority='MUST';
  wwReason='Elektrische boilermodus is niet geselecteerd';
  wwOpportunity='BLOCKED_MODE';
}
else if(minuteOfDay>=1140){
  wwAction=boilerOn?'BOILER_OFF':'HOLD';
  wwPriority='MUST';
  wwReason='Na 19:00 geen elektrische warmwater-run';
  wwOpportunity='AFTER_DEADLINE';
}
else if(goalReachedToday){
  // existing post-goal logic
}
else if(catchupRequired){
  // existing MUST catch-up logic
}
```

Current discretionary stop branches:

```js
else if(boilerOn&&runLocked){
  wwAction='HOLD';
  wwPriority='MAY';
  wwReason=`Run-lock ${startReason}: ${Math.round(runMin)}/${runLockMin} min`;
  wwOpportunity='RUN_LOCK';
  recommendedRunLockMin=runLockMin;
}
else if(boilerOn&&plannerStarted&&!plannerOpportunity){
  wwAction='BOILER_OFF';
  wwPriority='SHOULD';
  wwReason='Planner WW-slot beëindigd of realtime bevestiging vervallen na minimum run-lock';
  wwOpportunity='PLANNER_SLOT_END';
  recommendedRunLockMin=runLockMin;
}
else if(boilerOn&&!opportunity&&(expensive||importW>500)){
  wwAction='BOILER_OFF';
  wwPriority='SHOULD';
  wwReason=expensive?'Prijs nu ongunstiger dan komende 4 uur; run-lock verstreken':`Geen opportunity en ${Math.round(importW)} W netimport; Quatt ${Math.round(state.quatt.powerW)} W; run-lock verstreken`;
  wwOpportunity=expensive?'WAIT_PRICE':'WAIT_IMPORT';
  recommendedRunLockMin=runLockMin;
}
```

## Observed defect motivating v0.11c

On 2026-08-30 the boiler completed a long confirmed heating run, but the EMS switched the managed boiler switch OFF before the internal thermostat-low state could remain observable for 10 minutes. The published state therefore still showed `goalReachedToday=false` and `lowAfterHeatingMin=0`.

The fix must not infer the goal from an EMS OFF. Instead, for a narrowly bounded period after confirmed heating, discretionary OFF decisions may be deferred so the switch stays ON long enough for the internal thermostat to provide actual `<100 W` evidence.

## Deployment invariant

This capture is the live v0.11b behavioral baseline for the WW patch. v0.11c may change only the thermostat-verification state/decision path plus version/note metadata. Existing Tesla, Planner, P1 safety, mode, 19:00, catch-up, publication, Power Intent and physical-write ownership semantics must remain unchanged.
