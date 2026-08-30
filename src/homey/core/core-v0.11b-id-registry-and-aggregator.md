# Core v0.11b — Logic ID Registry and Aggregator Design

Status: **IMPLEMENTATION DESIGN REVISED / QUOOKER REMOVED FROM CRITICAL PATH**

Date: 2026-08-30

Baseline: `EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads)`.

## 1. Project decision

The ten legacy Quooker Logic variables are no longer part of the Core v0.11b input registry. Quooker detection is optional classification/enrichment and must not create recurring Homey read/write load, freshness gates or aggregator wake-ups.

P1 remains authoritative for the electrical household balance. Optional Quooker enrichment may move to Raspberry Pi later and is explicitly outside the mandatory Core contract.

## 2. Remaining external input registry

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

`WW_STATE_V13` is absent at runtime and remains `null / unavailable`; it must not be recreated.

### Planner inputs

| Variable | Type | Homey Logic ID |
|---|---|---|
| `EM2_ContractPrice_Context` | string | `93e41221-6b4d-4f5f-83dc-997c9620f758` |
| `EM2_Day_History` | string | `254f15cd-b060-4b42-801d-5e4f58efa069` |
| `EM2_Contract_Type` | string | `211e5846-aada-4607-8d52-01b2ef578866` |
| `TEMP_PBTH_JSON_BUFFER` | string | `29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b` |

### Publisher bookkeeping inputs

| Variable | Type | Homey Logic ID |
|---|---|---|
| `EM2_Last_Publish` | string | `fc95dcad-55d5-4d21-be15-f565f0a9bac3` |
| `EM2_Last_Published_Revision` | number | `c10ea01b-3dfc-4e04-bb27-2a56dfc636cd` |
| `EM2_Last_Publisher_Version` | string | `c8422ce3-093b-4781-ae20-67d2154c0a36` |

## 3. Core-owned previous-output registry

| Variable | Type | Homey Logic ID |
|---|---|---|
| `EM2_State` | string | `8e1efbb0-7999-494c-9429-7d274afacd79` |
| `EM2_WW_State` | string | `7ab1c09c-9b08-4c7b-94c7-0aeee7cc2c95` |
| `EM2_Control_WW` | string | `2dbe5fdb-88f6-4296-b170-c7c5941f2323` |
| `EM2_Control_EV` | string | `67451f33-20e6-46b0-9528-9c04bf6425dc` |

These are mirrored into the separate Core-owned `EM2_Core_Runtime` snapshot rather than being reread individually each tick.

## 4. Stable Core output ID registry

| Core output | Type | Homey Logic ID |
|---|---|---|
| `EM2_Publisher_Status` | string | `4a4c6e90-67b6-44a6-9172-00eb7eb9cf72` |
| `EM2_State` | string | `8e1efbb0-7999-494c-9429-7d274afacd79` |
| `EM2_Decision` | string | `8a0827cc-c4e4-4c77-9256-6c4d1e588b9b` |
| `EM2_Shadow` | string | `05f12c2d-f48d-4d65-9b32-667888082057` |
| `EM2_WW_State` | string | `7ab1c09c-9b08-4c7b-94c7-0aeee7cc2c95` |
| `EM2_Control_WW` | string | `2dbe5fdb-88f6-4296-b170-c7c5941f2323` |
| `EM2_Control_EV` | string | `67451f33-20e6-46b0-9528-9c04bf6425dc` |
| `EM2_Planner_Input` | string | `39c7c169-34d7-4e14-a27b-520aca255032` |
| `EM2_Publish_Due` | boolean | `fb0e42b6-8199-479e-be4c-43be3eb6a0ad` |
| `EM2_Public_State` | string | `b0d68d98-efdb-41e4-be72-3bd6bdcc19eb` |

Normal Core operation must never discover or create these variables.

## 5. Compact ownership model

- `EM2_Core_Input`: aggregator-owned snapshot of external/upstream Logic inputs only.
- `EM2_Core_Runtime`: Core-owned previous-state snapshot containing `state`, `wwState`, `controlWW` and `controlEV`.

This keeps one writer per JSON object and avoids read-modify-write races.

## 6. Lowest-wakeup aggregator model

Use one trigger per logical producer group, not one trigger per field.

| Group | Preferred trigger | Snapshot fields refreshed |
|---|---|---|
| Context | `EM2_Context_UpdatedAt` changed | all 5 context fields |
| Tesla goal | `EV Deadline status` changed plus `EV Deadline actief` | all 5 Tesla-goal fields |
| WW mode | `WW_Boilermodus` changed | boiler mode |
| WW post-goal | `EM2_WW_PostGoal_Opportunity` changed | post-goal object |
| Planner price context | `EM2_ContractPrice_Context` changed | contract-price context |
| Day history | `EM2_Day_History` changed | day history |
| Contract type | `EM2_Contract_Type` changed | contract type |
| PBTH buffer | `TEMP_PBTH_JSON_BUFFER` changed | price buffer |
| Publisher | `EM2_Last_Publish` changed | publication bookkeeping |

There is no Quooker group or Quooker trigger.

Each event path reads current `EM2_Core_Input`, reads only the relevant group using stable IDs, merges the group, compares semantic payload excluding `generatedAt`, and writes once only when effective content changed.

A short lease serializes overlapping events. There are no retry loops.

## 7. Reconciliation safety net

The hourly FULL reconciliation remains SHADOW-only during validation. After Quooker removal it needs at most **19 live external source reads** rather than 29. The absent `WW_STATE_V13` remains represented as null and is not queried/created.

The broad `Homey.logic.getVariables()` parity scan, while still retained temporarily as an hourly SHADOW diagnostic, must not exist in production Core and should be removed once migration parity is proven.

## 8. Core steady-state target

Per normal five-minute Core tick:

- 10 targeted device reads;
- 1 targeted `EM2_Core_Input` read;
- 1 targeted `EM2_Core_Runtime` read;
- 0 broad Logic scans;
- 0 discovery calls;
- 0 individual previous-output reads;
- output writes only after semantic suppression.

Quooker is not a Core cut-over blocker.
