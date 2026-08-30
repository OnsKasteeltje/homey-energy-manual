# Core v0.11b — Consolidated Logic Input

Status: **DEPENDENCY MAP REVISED / QUOOKER REMOVED FROM CRITICAL PATH / NOT DEPLOYED**

Date: 2026-08-30

Baseline: `EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads)`.

## Purpose

Remove the remaining broad `Homey.logic.getVariables()` collection scan from Core without replacing it with dozens of per-variable reads.

v0.11b introduces a compact canonical snapshot for the external Logic inputs that are genuinely required for EMS control. The proven v0.11a targeted device reads and current policy/output semantics remain unchanged.

## Architectural refinement — Quooker removed

The ten legacy `EM_Quooker_*` inputs are removed from the v0.11b critical input contract. Quooker detection is classification/visualization enrichment, not a control prerequisite. P1 already includes the electrical load, so EV/WW/Power Intent/Gate decisions remain electrically correct without a dedicated Quooker source.

There is therefore:

- no `sources.quooker` section in the v0.11b canonical input;
- no Quooker freshness gate;
- no `EM_Quooker_Commit` dependency;
- no Quooker aggregator trigger;
- no Quooker parity requirement for v0.11b cut-over.

Optional Quooker enrichment may move to the Raspberry Pi later and must remain outside the mandatory Core freshness path.

## Revised dependency count

The previous map contained 30 external/upstream dependencies, including 10 Quooker variables. Removing those leaves **20 external/upstream dependencies** in the documented v0.11a compatibility map. `WW_STATE_V13` remains absent at runtime and must stay `null / unavailable`; it must not be recreated.

The four Core-owned previous-state dependencies remain:

- `EM2_State`
- `EM2_WW_State`
- `EM2_Control_WW`
- `EM2_Control_EV`

Total documented Logic read dependencies to account for during migration: **24** rather than 34.

## Remaining external/upstream inputs

### Context

- `EM2_Context_UpdatedAt` -> `sources.context.updatedAt`
- `M7_PV_Top4h` -> `sources.context.pvTop4h`
- `M7_Price_Negative` -> `sources.context.priceNegative`
- `M7_Price_Cheap_Next4h` -> `sources.context.priceCheapNext4h`
- `M7_Price_Expensive_Next4h` -> `sources.context.priceExpensiveNext4h`

### Tesla goal

- `EV Deadline actief` -> `sources.teslaGoal.deadlineActive`
- `EV Deadline tijd` -> `sources.teslaGoal.deadline`
- `EV Latest start` -> `sources.teslaGoal.latestStart`
- `EV Resterend kWh` -> `sources.teslaGoal.remainingKWh`
- `EV Deadline status` -> `sources.teslaGoal.status`

### Warm water

- `WW_Boilermodus` -> `sources.hotWater.boilerMode`
- `EM2_WW_PostGoal_Opportunity` -> `sources.hotWater.postGoalOpportunity`

### Planner

- `EM2_ContractPrice_Context` -> `sources.planner.contractPriceContext`
- `EM2_Day_History` -> `sources.planner.dayHistory`
- `EM2_Contract_Type` -> `sources.planner.contractType`
- `TEMP_PBTH_JSON_BUFFER` -> `sources.planner.priceBuffer`

### Publication

- `EM2_Last_Publish` -> `sources.publication.lastPublish`
- `EM2_Last_Published_Revision` -> `sources.publication.lastPublishedRevision`
- `EM2_Last_Publisher_Version` -> `sources.publication.lastPublisherVersion`

### Legacy

- `WW_STATE_V13` -> optional bootstrap only; currently absent and represented as `null`.

## Canonical contract

Canonical variable: `EM2_Core_Input`.

```json
{
  "schema": "EM2_CORE_INPUT_V0.1",
  "generatedAt": "2026-08-30T00:00:00.000Z",
  "revision": 1,
  "sources": {
    "context": {
      "updatedAt": null,
      "pvTop4h": false,
      "priceNegative": false,
      "priceCheapNext4h": false,
      "priceExpensiveNext4h": false
    },
    "teslaGoal": {
      "deadlineActive": false,
      "deadline": null,
      "latestStart": null,
      "remainingKWh": 0,
      "status": null
    },
    "hotWater": {
      "boilerMode": false,
      "postGoalOpportunity": null
    },
    "planner": {
      "contractPriceContext": null,
      "dayHistory": null,
      "contractType": "UNKNOWN",
      "priceBuffer": []
    },
    "publication": {
      "lastPublish": null,
      "lastPublishedRevision": null,
      "lastPublisherVersion": null
    },
    "legacy": {
      "wwStateV13": null
    }
  }
}
```

`EM2_Core_Runtime` remains a separate Core-owned snapshot containing `state`, `wwState`, `controlWW` and `controlEV`. This avoids shared writer ownership between Core and the aggregator.

## Core v0.11b steady-state target

Per normal five-minute Core tick:

- 10 targeted device reads, unchanged from v0.11a;
- 1 targeted read of `EM2_Core_Input`;
- 1 targeted read of `EM2_Core_Runtime`;
- 0 broad `Homey.logic.getVariables()` calls;
- 0 name-discovery reads;
- 0 individual previous-output reads;
- known output IDs written directly with semantic suppression.

## Fail-closed rules

If `EM2_Core_Input` is missing, malformed or stale, Core must fail closed for safety-relevant opportunities and emit a clear diagnostic. P1/device freshness remains governed by existing v0.11a device logic. Context and post-goal freshness remain explicitly validated. There is no Quooker freshness condition.

## No-change contract

v0.11b must not change Core cadence, targeted device reads, state/decision schemas, Power Intent semantics, EV/WW ownership, LIVE gates, Publisher cadence, Planner semantics, semantic-write suppression or physical device-write behavior.

## Revised rollout plan

1. Keep v0.11a as active rollback baseline.
2. Maintain stable IDs for `EM2_Core_Input`, `EM2_Core_Runtime` and Core outputs.
3. Run the Snapshot Aggregator in SHADOW for the remaining required source groups only.
4. Remove Quooker from FULL reconciliation and parity expectations.
5. Compare the remaining mapped inputs over natural cycles.
6. Implement v0.11b Core with two targeted Logic reads and stable output IDs.
7. Smoke only when Homey is not rate-limited.
8. Soak against the same Core + Publisher + EV + WW baseline and compare CPU/429 behavior.

## Acceptance criteria

PASS requires zero `getVariables()` calls in production Core, no targeted Logic fan-out, two deterministic compact Logic reads per Core tick, semantic/freshness parity for all remaining required inputs, no downstream fan-out or physical-write regression, no increase in 429 frequency, and system CPU no worse than the v0.11a integrated baseline.

Quooker is explicitly **not** an acceptance blocker for Core v0.11b.
