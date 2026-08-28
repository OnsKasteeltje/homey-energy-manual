# Core v0.10.17 Planner Input LOW-LOAD candidate

Status: **PREPARED, NOT DEPLOYED**

Baseline: active Homey Core v0.10.16, reconstructed by `core-v0.10.16-runtime.patch.md` and smoke-tested PASS on 2026-08-28.

## Purpose

Produce the canonical Planner input inside Core without adding any second broad Homey Logic read. Core already performs the EMS single-reader `Homey.logic.getVariables()` call; the Planner must consume a targeted Logic variable by ID instead.

## New Core-owned Logic variable

`EM2_Planner_Input`

Schema: `EM2_PLANNER_INPUT_V0.1`

Candidate payload:

```js
const rawPriceBuffer=parse(vv('TEMP_PBTH_JSON_BUFFER'));
const plannerInput={
  schema:'EM2_PLANNER_INPUT_V0.1',
  generatedAt:now.toISOString(),
  sourceRevision:Number(state?.revision)||null,
  state,
  warmWater:st,
  contractPriceContext:parse(vv('EM2_ContractPrice_Context')),
  dayHistory:parse(vv('EM2_Day_History')),
  contractType:String(vv('EM2_Contract_Type')||'UNKNOWN').toUpperCase(),
  priceBuffer:Array.isArray(rawPriceBuffer)?rawPriceBuffer:[]
};
await set('EM2_Planner_Input','string',JSON.stringify(plannerInput));
```

Use the in-memory `st` warm-water state after its v0.10.16 update rather than reparsing an older value.

## Fan-out protection

Extend the active v0.10.16 semantic set to:

```js
const SEMANTIC_JSON_VARS=new Set([
  'EM2_State',
  'EM2_Decision',
  'EM2_Shadow',
  'EM2_Control_WW',
  'EM2_Publisher_Status',
  'EM2_Planner_Input'
]);
```

The existing v0.10.16 `VOLATILE_KEYS` already suppresses `generatedAt`, timestamps and freshness-only metadata. `EM2_WW_State` and `EM2_Public_State` remain deliberately outside semantic suppression exactly as in the active v0.10.16 runtime.

## Cadence / load rule

Do not add another collection scan. The only incremental Core Homey Logic cost is the `set('EM2_Planner_Input', ...)` path. Because semantic equality suppression is applied, the variable is not rewritten when only volatile timestamps/freshness metadata changed.

No flow may trigger directly from `EM2_Planner_Input` in this phase; Planner v0.4.4 remains scheduled/manual. This prevents input-update fan-out from becoming a new event cascade.

## Provisioning

On the first controlled Core v0.10.17 run, `set()` may create `EM2_Planner_Input` by name because Core already owns the single Logic collection and can safely provision it without another lookup. Once created, capture its stable Homey Logic ID through Logic-card autocomplete and bind that ID into Planner v0.4.4.

`EM2_Energy_Planner_Snapshot` should be provisioned in the same controlled deployment path before Planner v0.4.4 is enabled, then its stable ID is also bound into the Planner.

## API contract confirmation

Athom's Homey Web API exposes `Homey.logic.getVariable({id})` and `updateVariable({id,...})`, so Planner v0.4.4 can use targeted single-variable access instead of `getVariables()`.

## Safety

- Core remains SHADOW/read-only.
- No Tesla/Easee/boiler/Victron/Quatt/Quooker/device writes are added.
- Existing v0.10.16 control calculations and ownership remain unchanged.
- Planner remains disabled until its own controlled smoke.

## Gate

Deploy Core v0.10.17 only as one reviewed Core change-set. Run one targeted Core smoke immediately afterward. Continue to Planner v0.4.4 deployment only on explicit PASS.
