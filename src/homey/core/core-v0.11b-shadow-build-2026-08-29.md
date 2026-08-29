# Core v0.11b — Shadow Build Record

Status: **PROVISIONED / AGGREGATOR BUILT / NOT ACTIVE**

Date: 2026-08-29

Active baseline remains `EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads)`.

## Provisioned Logic variables

The two v0.11b snapshot variables were provisioned once from the current live Logic state:

| Variable | Type | Homey Logic ID | Owner |
|---|---|---|---|
| `EM2_Core_Input` | string / JSON | `05b27e13-9ebe-42af-8371-11c1f7148309` | v0.11b input aggregator |
| `EM2_Core_Runtime` | string / JSON | `1c96ded6-b696-4c26-b046-4157848d2e52` | future v0.11b Core |

Provisioning flow:

`TEMP | Core v0.11b Snapshot Provisioning [ONE-SHOT]`

Homey Advanced Flow ID: `32680a15-7397-4705-a2c0-9ffb928d8ed2`

The flow was enabled only long enough to run exactly once and was then disabled again. It is `broken=false`. It performs one Logic inventory read for installation-time provisioning only; this broad read is not part of normal v0.11b runtime.

No physical device writes and no active Core changes are performed by provisioning.

## Shadow aggregator

Flow:

`EM v2 | 12 Input | Core Snapshot Aggregator v0.1 SHADOW [DISABLED]`

Homey Advanced Flow ID: `758f3353-51f5-4e68-a1f4-3acf30ec5a87`

Current state: **disabled, broken=false**.

The implementation supports the following source-group tokens:

- `FULL`
- `QUOOKER`
- `CONTEXT`
- `TESLA`
- `WW_MODE`
- `WW_POSTGOAL`
- `PLANNER_PRICE`
- `DAY_HISTORY`
- `CONTRACT`
- `PBTH`
- `PUBLISHER`

For a group refresh it reads the existing `EM2_Core_Input`, reads only the stable Logic IDs for the selected group, merges the group into the snapshot, performs semantic comparison, and writes `EM2_Core_Input` only when the effective payload changed.

The `FULL` path is intended for low-frequency reconciliation only. It is currently reachable through the manual start path but is not scheduled or enabled.

## Safety state after build

- active v0.11a Core: unchanged;
- Core cadence: unchanged;
- Publisher / EV / WW flows: unchanged;
- new aggregator: disabled;
- event triggers: not wired/active yet;
- hourly reconciliation: not scheduled yet;
- `EM2_Core_Runtime`: provisioned only; no active writer yet;
- no physical device writes introduced;
- no v0.11b Core cut-over performed.

## Remaining activation gates

Before the aggregator may run alongside v0.11a:

1. wire the commit-marker event triggers to the group tokens;
2. add/prove serialization for overlapping read-modify-write events;
3. add the one-hour reconciliation trigger;
4. add a parity diagnostic comparing the snapshot with the existing v0.11a Logic view;
5. run one controlled SHADOW smoke only if Homey is not rate-limited;
6. keep v0.11a as rollback/reference throughout.

Only after snapshot parity has been demonstrated over natural cycles may the v0.11b Core read path be implemented and considered for cut-over.
