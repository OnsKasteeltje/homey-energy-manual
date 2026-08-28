# Core v0.10.16 planner-input patch

Status: **PREPARED, NOT DEPLOYED**

Baseline: Core v0.10.15 semantic fan-out behaviour.

## Decision

Core is the producer of the canonical planner input because Core already performs the single broad `Homey.logic.getVariables()` read for the EMS tick. The planner must not introduce a second broad Logic scan merely to obtain its inputs.

## Canonical output

Core produces one Logic string variable:

`EM2_Planner_Input`

Schema: `EM2_PLANNER_INPUT_V0.1`

```js
const plannerInput={
  schema:'EM2_PLANNER_INPUT_V0.1',
  generatedAt:now.toISOString(),
  sourceRevision:Number(state?.revision)||null,
  state,
  warmWater:parse(vv('EM2_WW_State')),
  contractPriceContext:parse(vv('EM2_ContractPrice_Context')),
  dayHistory:parse(vv('EM2_Day_History')),
  contractType:String(vv('EM2_Contract_Type')||'UNKNOWN').toUpperCase(),
  priceBuffer:parse(vv('TEMP_PBTH_JSON_BUFFER'))
};
await set('EM2_Planner_Input','string',JSON.stringify(plannerInput));
```

Implementation note: if `TEMP_PBTH_JSON_BUFFER` is not valid JSON, normalize `priceBuffer` to `[]` before writing the snapshot.

## Fan-out protection

Add `EM2_Planner_Input` to `SEMANTIC_JSON_VARS` so Core v0.10.15 semantic suppression applies. `generatedAt` is transport metadata and must not cause a Logic update on its own. A new `EM2_Planner_Input` change event is emitted only when planner-relevant semantic content changes.

Do not create a separate Planner Input Builder flow: that would add another broad Logic read and defeat the purpose of the low-load refactor.

## Ownership

Core owns `EM2_Planner_Input`. Planner consumes it read-only. Planner Shadow Publisher does not modify it.

## Safety

This patch adds only one Logic snapshot write path and no device writes. It changes no Tesla, Easee, boiler, Victron, Quatt, Quooker, washer/dryer or other actuator ownership.

## Deployment dependency

Do not deploy this patch independently while the Planner v0.4.3 migration gate is unresolved. It is prepared as the upstream half of Planner v0.4.4 LOW-LOAD. Runtime activation requires the normal controlled smoke sequence and Planner returned to disabled afterward.
