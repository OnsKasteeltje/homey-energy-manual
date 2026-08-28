# Planner v0.4.4 LOW-LOAD code patch

Status: **PREPARED, NOT DEPLOYED**

Baseline: `energy-plan-24h-v0.4.3.js`.

## Runtime access contract

The Planner must no longer call `Homey.logic.getVariables()`.

At deployment time bind the Homey Logic IDs of exactly two variables as constants in the HomeyScript:

```js
const PLANNER_INPUT_VAR_ID='__BIND_EM2_Planner_Input_ID__';
const PLANNER_SNAPSHOT_VAR_ID='__BIND_EM2_Energy_Planner_Snapshot_ID__';
```

Read only the canonical input variable and write only the canonical snapshot variable:

```js
const inputVar=await Homey.logic.getVariable({id:PLANNER_INPUT_VAR_ID});
const input=parse(inputVar?.value);
if(!input||input.schema!=='EM2_PLANNER_INPUT_V0.1') throw new Error('PLANNER_INPUT_MISSING_OR_INVALID');

const state=input.state??null;
const ww=input.warmWater??null;
const priceCtx=input.contractPriceContext??null;
const dayHist=input.dayHistory??null;
const contract=String(input.contractType||priceCtx?.contractType||'UNKNOWN').toUpperCase();
const arr=Array.isArray(input.priceBuffer)?input.priceBuffer:null;
```

The complete v0.4.3 planning algorithm remains unchanged after replacing its input bindings with the values above.

## Single output

Replace the two v0.4.3 writes to `EM2_Energy_Plan_24h` and `EM2_Energy_Planner_Status` with one snapshot write:

```js
const status={
  status:plan.plannerStatus,
  at:plan.generatedAt,
  version:VERSION,
  contract,
  slots:MAX_SLOTS,
  baseQuality,
  pvQuality:weatherStatus,
  pvSource:'OPEN_METEO_HAUWERT',
  pvCalibrationPoints:calibrationPoints,
  pvScaleWPerWm2:round(pvScale,3),
  usableHistory,
  observedBaseBins,
  slotsWithNetForecast:plan.plan.energyBalance.slotsWithNetForecast,
  traceableBaseLoad:true,
  teslaObligation:deadlineActive&&remainingKWh>0,
  teslaOpportunitySlots:teslaOpportunitySlots.length,
  teslaAllocationPolicy,
  wwObligation:!wwGoal&&wwRemainingMin>0,
  wwAllocationPolicy:plan.plan.warmWater.allocationPolicy,
  noActuatorWrites:true
};
const snapshot={
  schema:'EM2_ENERGY_PLANNER_SNAPSHOT_V0.1',
  generatedAt:plan.generatedAt,
  sourceRevision:Number(input.sourceRevision??state?.revision)||null,
  plan,
  status
};
await Homey.logic.updateVariable({id:PLANNER_SNAPSHOT_VAR_ID,variable:{value:JSON.stringify(snapshot)}});
return true;
```

The snapshot variable must be pre-created during controlled deployment so the Planner never needs a broad variable lookup or create-by-name fallback.

## Downstream rule

`EM v2 | 46 Publish | Planner Shadow` must trigger only on `EM2_Energy_Planner_Snapshot`. It must be idempotent on `generatedAt` plus `sourceRevision`. Legacy `EM2_Energy_Plan_24h` and `EM2_Energy_Planner_Status` are compatibility outputs only and must not be trigger sources.

## Expected Homey API profile per Planner run

Planner-local Homey Logic operations after this patch:

- 1 targeted `getVariable` for canonical input;
- 1 targeted `updateVariable` for canonical output;
- 0 `getVariables` collection scans;
- 0 create-variable fallbacks;
- 0 physical device writes.

The Open-Meteo HTTP request remains unchanged and is outside Homey Logic fan-out.

## Safety and policy invariants

No planner policy changes are allowed in this patch. Preserve 96×15-minute horizon, Hauwert weather forecast, traceable base-load model, Tesla PV-first behaviour, deadline optimisation rules, WW PV-first ranking, theoretical battery pairs, `controlMode:'SHADOW'`, `readOnly:true`, and `physicalWritePerformed:false`.

## Smoke gate

Do not mark v0.4.4 deployed until one controlled chain proves: fresh canonical input → one Planner run → one canonical snapshot → exactly one Planner Shadow publication → consistent downstream Power Intent/public state → no intentional actuator action → no Homey throttling. Record explicit PASS/FAIL and return Planner to disabled after the test.
