# Core v0.11b — SHADOW Aggregator Runtime Record

Date: 2026-08-29

Status: **SHADOW ACTIVE / NO CORE CUT-OVER**

Baseline production Core remains `EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads)` unchanged.

## Homey runtime

Aggregator flow:

- Name: `EM v2 | 12 Input | Core Snapshot Aggregator v0.1 SHADOW`
- Flow ID: `758f3353-51f5-4e68-a1f4-3acf30ec5a87`
- Enabled: yes
- Broken: no at deployment response
- Physical device writes: none
- Production Core reads/writes changed: no

Canonical SHADOW variables:

- `EM2_Core_Input` — `05b27e13-9ebe-42af-8371-11c1f7148309`
- `EM2_Core_Runtime` — `1c96ded6-b696-4c26-b046-4157848d2e52`
- `EM2_Core_Input_Lease` — `8891c3aa-d93a-47c3-a047-acd460cdc032`
- `EM2_Core_Input_Parity` — `4c73123a-575a-4ec8-ab28-05256f88cff6`

Provisioning flow `32680a15-7397-4705-a2c0-9ffb928d8ed2` was executed once for missing support variables and returned to disabled state.

## Concurrency model

Every aggregator update uses a short optimistic lease:

1. read current lease;
2. skip when an unexpired owner exists;
3. claim a 15-second lease;
4. reread and verify ownership;
5. perform targeted read/merge/write;
6. clear the lease only when the same owner still owns it.

There are no retry loops. A skipped collision is recovered by a later source event or hourly reconciliation.

## Event-driven groups enabled

The following low-frequency commit/freshness markers update only their own source group:

- `EM2_Context_UpdatedAt` → Context (5 targeted source reads)
- `EV Deadline status` and `EV Deadline actief` → Tesla goal (5 targeted source reads)
- `WW_Boilermodus` → WW mode
- `EM2_WW_PostGoal_Opportunity` → WW post-goal
- `EM2_ContractPrice_Context` → Planner price context
- `EM2_Day_History` → Day History
- `EM2_Contract_Type` → Contract type
- `TEMP_PBTH_JSON_BUFFER` → PBTH price buffer
- `EM2_Last_Publish` → Publisher bookkeeping (3 targeted source reads)

All event paths use semantic-write suppression for `EM2_Core_Input`.

## Quooker exception

`EM_Quooker_Last_Sample` is deliberately **not** wired as an event trigger in this SHADOW stage. It is driven by the P1 heartbeat and may change far more frequently than the other producer commit markers. Wiring it directly would risk introducing a high-frequency fan-out of ten targeted Logic reads and could negate the load reduction that v0.11b is intended to achieve.

For this stage, the Quooker group is refreshed by the hourly FULL reconciliation only. This means full parity can transiently report the Quooker group as different/stale. Production Core v0.11a remains authoritative, so this has no control impact.

A producer-side coalesced Quooker semantic snapshot or another bounded-wakeup strategy is required before Core cut-over.

## Hourly reconciliation and parity

The aggregator contains an `every 60 minutes` path:

1. acquire the same lease;
2. FULL-refresh the 29 live external source variables using targeted reads;
3. semantic-write `EM2_Core_Input` only if its source payload changed;
4. run one broad `Homey.logic.getVariables()` parity scan;
5. write a compact diagnostic to `EM2_Core_Input_Parity` with `checkedAt`, `ok`, snapshot revision and mismatching source groups.

The broad collection scan therefore exists only in the hourly SHADOW parity diagnostic, not in production Core and not at Core's 5-minute cadence.

The Start path uses the same FULL → parity chain. One controlled Start was issued immediately after deployment; Homey accepted the start request. The connector does not expose the HomeyScript return payload, so that acceptance alone is not treated as proof that parity was PASS.

## Safety / rollout boundary

No production Core cut-over occurred. No Publisher, Power Intent, Gate, EV actuator or WW actuator flow was modified by this deployment. No physical device write is performed by the aggregator.

Before v0.11b Core cut-over, require:

- natural-cycle SHADOW observation;
- a bounded solution for the high-frequency Quooker freshness input;
- parity/freshness evidence for all required Core dependencies;
- confirmation that Homey CPU and 429 behavior are no worse than the v0.11a integrated baseline;
- Core v0.11b implementation using stable output IDs plus targeted reads of `EM2_Core_Input` and `EM2_Core_Runtime`.
