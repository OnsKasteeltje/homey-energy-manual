# Core v0.11b — Consolidated Logic Input

Status: **DEPENDENCY MAP COMPLETE / NOT DEPLOYED**

Date: 2026-08-29

Baseline: `EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads)`.

## Purpose

Remove the remaining broad `Homey.logic.getVariables()` collection scan from Core without replacing it with dozens of per-variable reads.

v0.11b introduces one canonical, consolidated Logic snapshot for the external inputs Core consumes. Core keeps the proven v0.11a targeted device reads and all current policy/output semantics unchanged.

## Why not targeted Logic reads

Core currently consumes 34 Logic values as read dependencies when the four Core-owned previous-output values are included. Replacing one `getVariables()` call with roughly 30–35 `getVariable({id})` requests may reduce payload size but materially increase API request count and burst fan-out. Given the observed Homey throttling history, that trade-off is not acceptable without evidence.

Therefore v0.11b MUST NOT implement naive per-variable polling.

## Exact deployed v0.11a Logic dependency map

The inventory below is derived from the deployed v0.11a source and covers every `vv(...)` read plus every direct `byName.<variable>?.value` read used as an input or previous-state dependency.

### External / upstream inputs

| Source variable | `EM2_Core_Input` field | Functional owner / producer | Freshness / safety role |
|---|---|---|---|
| `EM_Quooker_Last_Sample` | `sources.quooker.lastSample` | Quooker detector / heartbeat | Authoritative Quooker freshness timestamp; 150 s gate |
| `EM_Quooker_Active` | `sources.quooker.active` | Quooker detector | Quooker inferred active state |
| `EM_Quooker_Power_W` | `sources.quooker.powerW` | Quooker detector | Measured/inferred Quooker load |
| `EM_Quooker_Status` | `sources.quooker.status` | Quooker detector | Diagnostic state |
| `EM_Quooker_Switch_On` | `sources.quooker.switchOn` | Quooker detector | Switch state |
| `EM_Quooker_Baseline_L3_W` | `sources.quooker.baselineL3W` | Quooker detector | Baseline diagnostic input |
| `EM_Quooker_Last_Transition` | `sources.quooker.lastTransition` | Quooker detector | Published history/diagnostics |
| `EM_Quooker_Last_Heating_At` | `sources.quooker.lastHeatingAt` | Quooker detector | Published history/diagnostics |
| `EM_Quooker_Last_Heating_Power_W` | `sources.quooker.lastHeatingPowerW` | Quooker detector | Published history/diagnostics |
| `EM_Quooker_Transition_History` | `sources.quooker.transitionHistory` | Quooker detector | Published history/diagnostics |
| `EM2_Context_UpdatedAt` | `sources.context.updatedAt` | Context / Price + PV producer | 35 min context freshness gate |
| `M7_PV_Top4h` | `sources.context.pvTop4h` | Price + PV context producer | WW/EV opportunity input |
| `M7_Price_Negative` | `sources.context.priceNegative` | Price + PV context producer | WW/EV price opportunity input |
| `M7_Price_Cheap_Next4h` | `sources.context.priceCheapNext4h` | Price + PV context producer | WW/EV price opportunity input |
| `M7_Price_Expensive_Next4h` | `sources.context.priceExpensiveNext4h` | Price + PV context producer | WW run-stop / opportunity input |
| `EV Deadline actief` | `sources.teslaGoal.deadlineActive` | EV deadline goal adapter / goal source | EV deadline policy input |
| `EV Deadline tijd` | `sources.teslaGoal.deadline` | EV deadline goal adapter / goal source | Published Tesla goal |
| `EV Latest start` | `sources.teslaGoal.latestStart` | EV deadline goal adapter / goal source | MUST/catch-up decision boundary |
| `EV Resterend kWh` | `sources.teslaGoal.remainingKWh` | EV deadline goal adapter / goal source | EV remaining-energy policy input |
| `EV Deadline status` | `sources.teslaGoal.status` | EV deadline goal adapter / goal source | Published Tesla goal state |
| `WW_Boilermodus` | `sources.hotWater.boilerMode` | EMS settings / user configuration | Hard WW mode gate |
| `EM2_WW_PostGoal_Opportunity` | `sources.hotWater.postGoalOpportunity` | WW Post-Goal Opportunity v0.4 | 35 min post-goal SHOULD-only gate |
| `EM2_ContractPrice_Context` | `sources.planner.contractPriceContext` | Contract Price Adapter | Planner input |
| `EM2_Day_History` | `sources.planner.dayHistory` | Day History producer | Planner input |
| `EM2_Contract_Type` | `sources.planner.contractType` | EMS settings / contract configuration | Planner input |
| `TEMP_PBTH_JSON_BUFFER` | `sources.planner.priceBuffer` | PBTH API price adapter/probe path | Planner price horizon input; retained TEMP dependency pending canonical rename |
| `WW_STATE_V13` | `sources.legacy.wwStateV13` | Legacy WW state | Bootstrap only when no current-day `EM2_WW_State` exists |
| `EM2_Last_Publish` | `sources.publication.lastPublish` | Publisher | Dirty/heartbeat timing |
| `EM2_Last_Published_Revision` | `sources.publication.lastPublishedRevision` | Publisher | Revision-pending calculation |
| `EM2_Last_Publisher_Version` | `sources.publication.lastPublisherVersion` | Publisher | Schema/version upgrade trigger |

External/upstream dependency count: **30**.

### Core-owned previous-state dependencies

These four values are not upstream business inputs, but v0.11a reads their previous values from the broad Logic collection and therefore they must also be accounted for before `getVariables()` can be removed.

| Core-owned variable | Current read purpose | v0.11b treatment |
|---|---|---|
| `EM2_State` | previous signature, `changedAt`, revision and `publishedAt` | Mirror required previous-state subset into `sources.coreRuntime.state` or equivalent canonical runtime section |
| `EM2_WW_State` | carry daily WW accounting/latch state across ticks | Mirror full current WW state into `sources.coreRuntime.wwState` |
| `EM2_Control_WW` | recover prior WW run-start reason/opportunity | Mirror required previous control object into `sources.coreRuntime.controlWW` |
| `EM2_Control_EV` | semantic signature/revision suppression | Mirror required previous EV control object into `sources.coreRuntime.controlEV` |

Core-owned previous-state dependency count: **4**.

Total deployed v0.11a Logic read dependencies: **34**.

## Important implementation finding: read elimination also affects writes

`Homey.logic.getVariables()` currently does two jobs in v0.11a:

1. it supplies the 34 values above; and
2. it builds `byName`, which the `set()` helper uses to locate the IDs and current values of Core output variables before calling `updateVariable()`.

Therefore simply replacing `getVariables()` with one read of `EM2_Core_Input` is incomplete. v0.11b also needs a stable output-ID strategy.

The preferred design is:

- keep stable Logic variable IDs for every Core output in a small static `LOGIC_IDS` map inside Core;
- call `Homey.logic.updateVariable({id,...})` directly for known outputs;
- preserve semantic-write suppression using previous values carried in `EM2_Core_Input.sources.coreRuntime` where needed;
- do **not** add a targeted read for every output on every tick;
- variable creation/provisioning is an installation/migration concern, not a normal Core-tick concern.

This prevents the read optimization from accidentally reintroducing a large targeted-read fan-out through the write helper.

## Canonical contract

Canonical variable:

`EM2_Core_Input`

Revised schema shape:

```json
{
  "schema": "EM2_CORE_INPUT_V0.1",
  "generatedAt": "2026-08-29T00:00:00.000Z",
  "revision": 1,
  "sources": {
    "quooker": {
      "active": false,
      "powerW": 0,
      "status": "UNKNOWN",
      "switchOn": false,
      "baselineL3W": null,
      "lastSample": null,
      "lastTransition": null,
      "lastHeatingAt": null,
      "lastHeatingPowerW": null,
      "transitionHistory": []
    },
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
    },
    "coreRuntime": {
      "state": null,
      "wwState": null,
      "controlWW": null,
      "controlEV": null
    }
  }
}
```

No additional source may be added merely for convenience: the contract should stay restricted to values actually consumed by Core.

## Producer model

`EM2_Core_Input` is updated by a dedicated low-load input aggregator.

Preferred behavior:

- event-driven updates when relevant source variables change;
- semantic-write suppression: do not rewrite when the effective payload is unchanged;
- maintain a monotonically increasing `revision` only on semantic change;
- record `generatedAt` and per-source timestamps where freshness matters;
- mirror the four Core-owned previous-state dependencies when Core outputs change;
- no device reads inside the aggregator;
- no physical writes;
- no retries after `429 Too many requests`.

A low-frequency reconciliation run may be retained as a safety net, but it must not recreate the old broad polling pattern at Core cadence.

## Ownership boundaries

The aggregator does **not** become the business owner of any input. It only materializes a compact snapshot.

- Quooker fields remain owned by the existing Quooker detector/heartbeat path.
- Context fields remain owned by the active Price + PV/context producer.
- Tesla-goal fields remain owned by the EV deadline goal path.
- WW mode remains configuration-owned.
- Post-goal opportunity remains owned by the WW Post-Goal Opportunity decision flow.
- Planner price/history/contract inputs remain owned by their current adapters/producers.
- Publication bookkeeping remains Publisher-owned.
- Core runtime mirrors remain Core-owned.

The aggregator MUST NOT recompute policy, reinterpret values, or perform device writes.

## Core v0.11b read/write strategy

Core keeps the v0.11a targeted device reads and replaces the broad Logic collection read with one targeted canonical-input read:

```js
const coreInput = await Homey.logic.getVariable({ id: CORE_INPUT_ID });
const input = JSON.parse(String(coreInput.value || '{}'));
```

Core outputs use stable IDs rather than a `byName` collection built from `getVariables()`:

```js
await Homey.logic.updateVariable({
  id: LOGIC_IDS.EM2_State,
  variable: { value: nextState }
});
```

Semantic suppression still happens before the update call. No physical device-write behavior changes.

## Fail-closed rules

If `EM2_Core_Input` is missing, malformed or stale:

- Core must not upgrade stale data to a valid state;
- safety-relevant opportunities must fail closed;
- P1/device freshness remains governed by the existing v0.11a device-timestamp logic;
- Quooker freshness remains based on `sources.quooker.lastSample`;
- context freshness remains based on `sources.context.updatedAt`;
- post-goal opportunity freshness remains based on its own `generatedAt`;
- no retry loop is allowed inside the same Core run;
- emit a clear diagnostic status rather than silently substituting defaults for mandatory inputs.

## No-change contract

v0.11b MUST NOT change:

- 5-minute Core cadence;
- v0.11a targeted device reads;
- state/decision schemas;
- `EM2_Control_EV` semantic producer behavior;
- WW decision semantics;
- Power Intent semantics;
- EV/WW ownership or LIVE gates;
- Publisher cadence;
- Planner semantics;
- semantic-write suppression;
- physical device-write behavior.

## Rollout plan

1. Freeze v0.11a as the active baseline.
2. **Dependency map complete:** 30 upstream/external + 4 Core-owned previous-state values identified.
3. Resolve stable Logic IDs for the canonical input and Core output variables.
4. Build `EM2_Core_Input` and the dedicated aggregator in SHADOW, initially disabled until its trigger/update model is reviewed for wake-up cost.
5. Run the aggregator alongside v0.11a without changing Core reads.
6. Compare all 34 mapped values against the existing `getVariables()`-derived values over multiple natural cycles.
7. Require semantic parity and freshness parity.
8. Create v0.11b Core using one targeted canonical-input read plus stable output IDs.
9. Perform one controlled smoke only if Homey is not rate-limited.
10. Soak with the same Core + Publisher + EV + WW set used for the v0.11a baseline.
11. Compare system CPU, CPU Clock and rate-limit behavior against v0.11a.

## Acceptance criteria

PASS requires:

- zero `Homey.logic.getVariables()` calls in Core;
- no 30–35-call targeted Logic fan-out;
- one canonical Logic-input read per Core run;
- no per-output read fan-out introduced by the write helper;
- all 34 mapped read dependencies represented with semantic/freshness parity;
- semantic parity for `EM2_State`, `EM2_Decision`, `EM2_Control_WW`, `EM2_Control_EV` and `EM2_Planner_Input`;
- no new downstream fan-out;
- no physical write regression;
- no increase in 429/rate-limit frequency;
- system CPU no worse than the v0.11a integrated baseline.

## Rollback

Rollback target is the deployed v0.11a Core unchanged. The aggregator can remain disabled or SHADOW-only after rollback.

Do not combine v0.11b cut-over with Planner, Publisher, Power Intent, Gate, EV actuator or WW actuator changes.

## Next implementation step

Resolve the stable Logic IDs for the 34 dependencies and the Core output variables, then design the lowest-wake-up aggregator trigger strategy. Only after that should `EM2_Core_Input` be provisioned on Homey.