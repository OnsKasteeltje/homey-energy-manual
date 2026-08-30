# Core v0.11e — exact implementation delta against live v0.11d

Status: **SOURCE PATCH PREPARED / NOT APPLIED TO HOMEY**

This patch is intentionally narrow. It changes only Tesla consumption of the already-read Planner snapshot. It does not add device reads, Logic collection scans, network calls, actuator writes or new pollers.

## 1. Version metadata

Change:

```js
const PUB_VERSION='EM2_CORE_STATE_V0.11d'
```

to:

```js
const PUB_VERSION='EM2_CORE_STATE_V0.11e'
```

Target flow name:

```text
EM v2 | 00 Core Tick | v0.11e (Planner Tesla Intent)
```

## 2. Extend existing Planner active-slot extraction

Current v0.11d block ends with:

```js
const plannerWW=String(plannerSlot?.warmWater||'HOLD').toUpperCase(),
      plannerWWReason=String(plannerSlot?.warmWaterReason||'UNKNOWN'),
      plannerWWStart=plannerSlot?.start??null,
      plannerWWEnd=plannerSlot?.end??null;
```

Replace with equivalent declarations that additionally expose Tesla intent:

```js
const plannerWW=String(plannerSlot?.warmWater||'HOLD').toUpperCase(),
      plannerWWReason=String(plannerSlot?.warmWaterReason||'UNKNOWN'),
      plannerWWStart=plannerSlot?.start??null,
      plannerWWEnd=plannerSlot?.end??null,
      plannerTesla=String(plannerSlot?.tesla||'HOLD').toUpperCase(),
      plannerTeslaStart=plannerSlot?.start??null,
      plannerTeslaEnd=plannerSlot?.end??null;
```

No extra Homey read is required.

## 3. Add realtime Planner-Tesla guard variables before Tesla decision

Immediately before the Tesla `let energyState...intent...` decision block, add:

```js
const PLANNER_TESLA_MIN_IMPORT_BUDGET_W=4140,
      plannerTeslaDeadlineSlot=plannerCompatible&&plannerTesla==='PREFERRED_BEFORE_DEADLINE',
      plannerTeslaImportGuardOk=discretionaryImportBudgetW>=PLANNER_TESLA_MIN_IMPORT_BUDGET_W,
      plannerTeslaDeadlineEligible=plannerTeslaDeadlineSlot&&deadlineActive&&remaining>0&&Number.isFinite(latestStartMs)&&Date.now()<latestStartMs&&plugged&&p1Fresh&&gridMeasurementValid;
```

The 4140 W guard is only a minimum-executable-power admission guard. It does not replace EV Adapter quantization and does not claim phase-aware 3×25 A headroom.

## 4. Extend Tesla decision precedence

Current first branch remains unchanged:

```js
if(deadlineActive&&remaining>0&&Number.isFinite(latestStartMs)&&Date.now()>=latestStartMs){
  priority='MUST';
  intent=plugged?'TESLA_CHARGE_DEADLINE':'TESLA_DEADLINE_BLOCKED_NOT_CONNECTED';
  reason=`Tesla deadline catch-up: ${remaining.toFixed(2)} kWh resterend`;
}
```

Insert the following branches **immediately after MUST catch-up and before the existing realtime opportunity branch**:

```js
else if(plannerTeslaDeadlineEligible&&plannerTeslaImportGuardOk){
  priority='SHOULD';
  intent='TESLA_CHARGE_DEADLINE';
  reason=`PLANNER_TESLA_DEADLINE_SLOT_EXECUTED | ${plannerTeslaStart}–${plannerTeslaEnd} | importbudget ${Math.round(discretionaryImportBudgetW)} W`;
}
else if(plannerTeslaDeadlineSlot&&deadlineActive&&remaining>0&&!plugged){
  priority='SHOULD';
  intent='TESLA_WAIT_NOT_CONNECTED';
  reason='PLANNER_TESLA_BLOCKED_NOT_CONNECTED | deadline-slot actief';
}
else if(plannerTeslaDeadlineSlot&&deadlineActive&&remaining>0&&(!p1Fresh||!gridMeasurementValid)){
  priority='MAY';
  intent='HOLD';
  reason='PLANNER_TESLA_BLOCKED_P1 | deadline-slot actief maar P1 niet vers/geldig';
}
else if(plannerTeslaDeadlineSlot&&deadlineActive&&remaining>0&&!plannerTeslaImportGuardOk){
  priority='MAY';
  intent='HOLD';
  reason=`PLANNER_TESLA_BLOCKED_IMPORT_BUDGET | ${Math.round(discretionaryImportBudgetW)} W < ${PLANNER_TESLA_MIN_IMPORT_BUDGET_W} W`;
}
```

Then keep the current v0.11d branch intact:

```js
else if(deadlineActive&&remaining>0&&(flexExportBudgetW>=BUDGET.teslaOpportunityW||negative||(cheap&&teslaPriceBudgetOk))){
  ... existing v0.11d code unchanged ...
}
```

This ordering is intentional:

```text
MUST latest-start catch-up
> active Planner deadline slot with realtime safety
> current realtime opportunity
> no-deadline buffer export
```

## 5. Add observability to `decision.inputs`

Add these fields without removing existing fields:

```js
plannerTesla,
plannerTeslaStart,
plannerTeslaEnd,
plannerTeslaDeadlineSlot,
plannerTeslaDeadlineEligible,
plannerTeslaImportGuardOk,
plannerGeneratedAt:plannerSnap?.generatedAt??plannerSnap?.plan?.generatedAt??null,
```

Do not change `EM2_DECISION_V0.9` schema in this patch.

## 6. Optional shadow/public observability

Where safe without schema breakage, add Planner Tesla fields to status/public metadata. This is optional for first deployment; the required evidence is already in Decision inputs/reason.

Do not change Publisher cadence.

## 7. EV semantic producer remains unchanged

This existing mapping must remain:

```js
const evMode=intent==='TESLA_CHARGE_DEADLINE'?'DEADLINE':
             intent==='TESLA_CHARGE_OPPORTUNITY'?'OPPORTUNITY':
             intent==='TESLA_BUFFER_EXPORT'?'BUFFER_EXPORT':'HOLD';
```

Therefore Planner-driven deadline charging naturally enters existing:

```text
Core Decision
-> EM2_Control_EV DEADLINE
-> Power Intent
-> EV Adapter
-> Gate
-> Actuator
```

No new consumer or side channel is introduced.

## 8. Required diff invariants

When the full candidate is generated from the live v0.11d source, the diff must show:

- version/name change only;
- active Planner slot Tesla fields;
- Planner Tesla realtime guard variables;
- four decision branches;
- observability fields;
- no changes to WW state machine;
- no changes to device IDs/reads;
- no changes to 5-minute cadence;
- no changes to EV Power Intent/Adapter/Gate/Actuator code;
- no physical writes added to Core.

Any unrelated diff blocks promotion.
