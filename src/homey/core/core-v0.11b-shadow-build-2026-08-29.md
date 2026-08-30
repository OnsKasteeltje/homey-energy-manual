# Core v0.11b — Shadow Build Record

Status: **PROVISIONED / AGGREGATOR BUILT / QUOOKER REMOVED FROM TARGET CONTRACT**

Date: 2026-08-30

Active baseline remains `EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads)`.

## Provisioned Logic variables

| Variable | Type | Homey Logic ID | Owner |
|---|---|---|---|
| `EM2_Core_Input` | string / JSON | `05b27e13-9ebe-42af-8371-11c1f7148309` | v0.11b input aggregator |
| `EM2_Core_Runtime` | string / JSON | `1c96ded6-b696-4c26-b046-4157848d2e52` | future v0.11b Core |

Provisioning flow:

`TEMP | Core v0.11b Snapshot Provisioning [ONE-SHOT]`

Homey Advanced Flow ID: `32680a15-7397-4705-a2c0-9ffb928d8ed2`.

## Shadow aggregator

Flow:

`EM v2 | 12 Input | Core Snapshot Aggregator v0.1 SHADOW`

Homey Advanced Flow ID: `758f3353-51f5-4e68-a1f4-3acf30ec5a87`.

The implementation originally included a `QUOOKER` source-group token. As of the 2026-08-30 architecture decision, Quooker is removed from the target v0.11b contract and this token must be retired from the next aggregator revision rather than wired or validated further.

Target source-group tokens are now:

- `FULL`
- `CONTEXT`
- `TESLA`
- `WW_MODE`
- `WW_POSTGOAL`
- `PLANNER_PRICE`
- `DAY_HISTORY`
- `CONTRACT`
- `PBTH`
- `PUBLISHER`

For a group refresh the aggregator reads existing `EM2_Core_Input`, reads only the stable Logic IDs for that source group, merges the group, performs semantic comparison and writes only on effective change.

The revised FULL target excludes the ten legacy Quooker variables and therefore needs at most 19 live external source reads. `WW_STATE_V13` remains absent/null and must not be recreated.

## Safety state

- active v0.11a Core remains unchanged;
- Core cadence unchanged;
- Publisher / EV / WW control flows unchanged;
- no physical device writes introduced;
- no v0.11b Core cut-over performed;
- Quooker is no longer a v0.11b prerequisite or acceptance blocker.

## Remaining activation gates

1. revise the deployed SHADOW aggregator so `QUOOKER` and the ten Quooker FULL reads are removed;
2. retain/prove serialization for overlapping read-modify-write events;
3. retain hourly reconciliation only as a low-frequency SHADOW safety net;
4. compare parity for the remaining required input groups;
5. run controlled SHADOW validation only while Homey is healthy and globally serialized;
6. keep v0.11a as rollback/reference throughout;
7. then implement v0.11b Core with targeted reads of `EM2_Core_Input` and `EM2_Core_Runtime`.

The Quooker detector/semantic-commit validation track is cancelled as a Core cut-over dependency. Optional Quooker classification may later move to Raspberry Pi enrichment outside the Homey critical EMS runtime.
