# Core v0.11b — Logic ID Registry and Aggregator Design

Status: **IMPLEMENTATION DESIGN COMPLETE / NOT DEPLOYED**

Date: 2026-08-29

Baseline: `EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads)`.

This document completes the next implementation step for Core v0.11b: resolve the stable Logic IDs used by the deployed v0.11a runtime and define a low-wakeup snapshot architecture that does not recreate broad Logic polling or introduce a large targeted-read fan-out.

## 1. Live Logic dependency registry

The IDs below were resolved from the current Homey Logic inventory. They are installation-specific runtime IDs and therefore belong to this deployment registry, not to portable business logic.

### Quooker inputs

| Variable | Type | Homey Logic ID |
|---|---|---|
| `EM_Quooker_Last_Sample` | string | `a3b345ed-4e9a-4a44-9358-750caad10386` |
| `EM_Quooker_Active` | boolean | `e1ade1a1-cffb-499f-ac62-42fe6254dd52` |
| `EM_Quooker_Power_W` | number | `57c81ed9-4c92-4293-b017-0700a9746598` |
| `EM_Quooker_Status` | string | `9b4159f1-2856-4284-9898-bf2e8ec6d0ff` |
| `EM_Quooker_Switch_On` | boolean | `fbd409dd-1813-4d1d-b095-48c5eead2eaa` |
| `EM_Quooker_Baseline_L3_W` | number | `bc90d360-d13f-4a99-95b1-8a4cc9bbed3d` |
| `EM_Quooker_Last_Transition` | string | `9f39700e-49f8-42e4-9252-6cafa98fca30` |
| `EM_Quooker_Last_Heating_At` | string | `10e95965-b8f1-47b6-a60d-9abaff5b3eda` |
| `EM_Quooker_Last_Heating_Power_W` | number | `338fd52b-1151-49a0-9179-dc74666778e4` |
| `EM_Quooker_Transition_History` | string | `d63f7fc9-0a6e-4a08-b299-e65572f56ce7` |

### Context inputs

| Variable | Type | Homey Logic ID |
|---|---|---|
| `EM2_Context_UpdatedAt` | string | `917704c9-8038-4914-9205-c552b4f1939a` |
| `M7_PV_Top4h` | boolean | `0bb18a3a-0420-4e94-81ff-dc00b9215434` |
| `M7_Price_Negative` | boolean | `0c94479a-495a-40b4-9de9-dbd63092cecb` |
| `M7_Price_Cheap_Next4h` | boolean | `010392a1-7d56-4c70-be75-9b38cdec71be` |
| `M7_Price_Expensive_Next4h` | boolean | `e66c8f24-27fa-4bf9-8f57-f3eeaca80ca0` |

### Tesla goal inputs

| Variable | Type | Homey Logic ID |
|---|---|---|
| `EV Deadline actief` | boolean | `c35d4237-f173-4913-ae23-9434d6a98b70` |
| `EV Deadline tijd` | string | `1173209b-2853-4fe2-b21b-507cea606ce6` |
| `EV Latest start` | string | `bf00e544-7ef1-4778-b8cd-4e0812198850` |
| `EV Resterend kWh` | number | `085eb4ed-80e8-4d37-92a0-56437f40b77f` |
| `EV Deadline status` | string | `d0254ca9-5e4e-4cd5-8228-b1c25e6b9e3e` |

### Warm-water inputs

| Variable | Type | Homey Logic ID |
|---|---|---|
| `WW_Boilermodus` | boolean | `f9d885a4-fca2-4aea-a5a9-a5c05da90835` |
| `EM2_WW_PostGoal_Opportunity` | string | `1685e7b7-af04-4e0d-b4ed-78bef0d6bd42` |

`WW_STATE_V13` is referenced by v0.11a only as an optional legacy bootstrap source. A targeted lookup of the current Homey Logic inventory returned no such variable. Therefore v0.11b must preserve its *current live behavior* as `null / unavailable`; it must not recreate this legacy variable merely to satisfy an obsolete read path.

### Planner inputs

| Variable | Type | Homey Logic ID |
|---|---|---|
| `EM2_ContractPrice_Context` | string | `93e41221-6b4d-4f5f-83dc-997c9620f758` |
| `EM2_Day_History` | string | `254f15cd-b060-4b42-801d-5e4f58efa069` |
| `EM2_Contract_Type` | string | `211e5846-aada-4607-8d52-01b2ef578866` |
| `TEMP_PBTH_JSON_BUFFER` | string | `29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b` |

`TEMP_PBTH_JSON_BUFFER` remains a temporary-name production dependency. v0.11b must not rename it during the Core optimization; canonical renaming is a separate migration.

### Publisher bookkeeping inputs

| Variable | Type | Homey Logic ID |
|---|---|---|
| `EM2_Last_Publish` | string | `fc95dcad-55d5-4d21-be15-f565f0a9bac3` |
| `EM2_Last_Published_Revision` | number | `c10ea01b-3dfc-4e04-bb27-2a56dfc636cd` |
| `EM2_Last_Publisher_Version` | string | `c8422ce3-093b-4781-ae20-67d2154c0a36` |

### Core-owned previous-output variables

| Variable | Type | Homey Logic ID |
|---|---|---|
| `EM2_State` | string | `8e1efbb0-7999-494c-9429-7d274afacd79` |
| `EM2_WW_State` | string | `7ab1c09c-9b08-4c7b-94c7-0aeee7cc2c95` |
| `EM2_Control_WW` | string | `2dbe5fdb-88f6-4296-80a6-26ab035d2678` |
| `EM2_Control_EV` | string | `67451f33-20e6-46b0-9528-9c04bf6425dc` |

## 2. Stable Core output ID registry

Removing `getVariables()` also removes the current name-to-ID lookup used by `set()`. v0.11b therefore uses a static deployment registry for every Core output written during a normal tick.

| Core output | Type | Homey Logic ID |
|---|---|---|
| `EM2_Publisher_Status` | string | `4a4c6e90-67b6-44a6-9172-00eb7eb9cf72` |
| `EM2_State` | string | `8e1efbb0-7999-494c-9429-7d274afacd79` |
| `EM2_Decision` | string | `8a0827cc-c4e4-4c77-9256-6c4d1e588b9b` |
| `EM2_Shadow` | string | `05f12c2d-f48d-4d65-9b32-667888082057` |
| `EM2_WW_State` | string | `7ab1c09c-9b08-4c7b-94c7-0aeee7cc2c95` |
| `EM2_Control_WW` | string | `2dbe5fdb-88f6-4296-80a6-26ab035d2678` |
| `EM2_Control_EV` | string | `67451f33-20e6-46b0-9528-9c04bf6425dc` |
| `EM2_Planner_Input` | string | `39c7c169-34d7-4e14-a27b-520aca255032` |
| `EM2_Publish_Due` | boolean | `fb0e42b6-8199-479e-be4c-43be3eb6a0ad` |
| `EM2_Public_State` | string | `b0d68d98-efdb-41e4-be72-3bd6bdcc19eb` |

Normal Core operation must never call `createVariable()` for these outputs. Provisioning/repair is a separate migration concern.

## 3. Important design refinement: separate external snapshot from Core runtime

The dependency-map version proposed mirroring previous Core outputs inside `EM2_Core_Input`. That would give the aggregator and Core shared write ownership of the same JSON variable. Shared ownership creates a race/lost-update risk and can cause multiple wakeups after one Core tick.

v0.11b therefore uses **two compact variables**:

- `EM2_Core_Input`: aggregator-owned snapshot of external/upstream Logic inputs only;
- `EM2_Core_Runtime`: Core-owned compact previous-state snapshot required for the next Core tick.

This deliberately changes the target from one Logic read per Core tick to **two targeted Logic reads per Core tick**. Two deterministic reads are preferred over one shared-write JSON object, four previous-output reads, or 30+ per-variable reads.

`EM2_Core_Runtime` contains only the previous-state data Core actually needs:

```json
{
  "schema": "EM2_CORE_RUNTIME_V0.1",
  "generatedAt": "2026-08-29T00:00:00.000Z",
  "state": null,
  "wwState": null,
  "controlWW": null,
  "controlEV": null
}
```

Core updates this snapshot once near the end of a successful tick, with semantic-write suppression. The next tick reads it once by stable ID. The normal flow does not reread the four individual output variables.

## 4. Lowest-wakeup aggregator model

The aggregator must not wake on every individual field mutation. Existing producers commonly write several related variables in one logical publication. Triggering on every field would create exactly the kind of fan-out v0.11b is intended to remove.

### Commit-marker triggers

Use one trigger per producer group, preferably the producer's existing commit/freshness marker:

| Group | Preferred trigger / commit marker | Snapshot fields refreshed |
|---|---|---|
| Quooker | `EM_Quooker_Last_Sample` changed | all 10 Quooker fields |
| Context | `EM2_Context_UpdatedAt` changed | all 5 context fields |
| Tesla goal | `EV Deadline status` changed, plus `EV Deadline actief` for hard on/off transitions | all 5 Tesla-goal fields |
| WW mode | `WW_Boilermodus` changed | boiler mode |
| WW post-goal | `EM2_WW_PostGoal_Opportunity` changed | post-goal object |
| Planner price context | `EM2_ContractPrice_Context` changed | contract-price context |
| Day history | `EM2_Day_History` changed | day history |
| Contract type | `EM2_Contract_Type` changed | contract type |
| PBTH buffer | `TEMP_PBTH_JSON_BUFFER` changed | price buffer |
| Publisher | `EM2_Last_Publish` changed | last publish + revision + publisher version |

The aggregator action refreshes only the affected group from stable Logic IDs and performs one semantic-suppressed write of `EM2_Core_Input`.

### Why group-targeted refresh instead of full refresh

A full snapshot refresh after every trigger would still read ~29 variables per wakeup. Instead, each trigger passes a source-group token to the aggregator, which reads only that group's stable IDs, merges them into the existing canonical snapshot, and writes only when the effective group payload changed.

Expected targeted read counts per event:

- Quooker event: 10 source reads + 1 existing `EM2_Core_Input` read;
- Context event: 5 + 1;
- Tesla goal event: 5 + 1;
- most other groups: 1–3 + 1.

This is event-driven load, not 5-minute broad polling.

### Reconciliation safety net

Add one low-frequency reconciliation path, initially **once per hour**, not every Core tick. Reconciliation may refresh the full external snapshot from the 29 live source variables and should run only when Homey is not rate-limited. It exists to recover from a missed change event, not as the primary data path.

No retries are allowed after a `429 Too many requests` response.

## 5. Canonical ownership and concurrency rules

`EM2_Core_Input` has exactly one writer: the aggregator.

`EM2_Core_Runtime` has exactly one writer: Core.

Existing producers remain owners of their source variables. Neither the aggregator nor Core may reinterpret, normalize business policy, or write to a physical device.

The aggregator uses optimistic merge semantics:

1. read current `EM2_Core_Input` once;
2. read only the source group that triggered;
3. replace only that group in memory;
4. compare semantic payload excluding `generatedAt`;
5. if unchanged, return without write;
6. if changed, increment `revision`, set timestamps, and write once.

Because a single aggregator flow owns writes to `EM2_Core_Input`, concurrent group events must be serialized by a short run lease or equivalent single-run guard. Do not start parallel read-modify-write executions against the same JSON snapshot.

## 6. v0.11b Core steady-state read profile

Per normal 5-minute Core tick:

- 10 targeted device reads: unchanged from v0.11a;
- 1 targeted read: `EM2_Core_Input`;
- 1 targeted read: `EM2_Core_Runtime`;
- 0 broad `Homey.logic.getVariables()` calls;
- 0 name-discovery reads;
- 0 individual previous-output reads;
- output writes only after existing semantic suppression rules pass.

This is the implementation target to compare against the v0.11a runtime baseline.

## 7. Provisioning gate

Do **not** provision or enable the new runtime yet until the following are implemented in code/documentation:

1. create IDs for `EM2_Core_Input` and `EM2_Core_Runtime` once;
2. implement the aggregator in SHADOW, initially disabled;
3. implement group-token entry points and serialization/run lease;
4. implement one-hour reconciliation path;
5. implement parity diagnostics against the existing v0.11a broad Logic snapshot;
6. only then run alongside v0.11a without changing Core reads.

No Core cut-over occurs in this step.