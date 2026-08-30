# Core v0.11b — SHADOW Aggregator Runtime Record

Date: 2026-08-30

Status: **SHADOW ACTIVE / QUOOKER REMOVED FROM CUT-OVER CONTRACT / NO CORE CUT-OVER**

Baseline production Core remains `EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads)` unchanged.

## Homey runtime

Aggregator flow:

- Name: `EM v2 | 12 Input | Core Snapshot Aggregator v0.1 SHADOW`
- Flow ID: `758f3353-51f5-4e68-a1f4-3acf30ec5a87`
- Physical device writes: none
- Production Core reads/writes changed: no

Canonical SHADOW variables:

- `EM2_Core_Input` — `05b27e13-9ebe-42af-8371-11c1f7148309`
- `EM2_Core_Runtime` — `1c96ded6-b696-4c26-b046-4157848d2e52`
- `EM2_Core_Input_Lease` — `8891c3aa-d93a-47c3-a047-acd460cdc032`
- `EM2_Core_Input_Parity` — `4c73123a-575a-4ec8-ab28-05256f88cff6`

## Architectural decision 2026-08-30

Quooker detection is removed from the Homey EMS critical path. The previous SHADOW exception around high-frequency Quooker freshness is no longer a problem to solve for Core v0.11b.

The Snapshot Aggregator design now excludes:

- the Quooker source group;
- `EM_Quooker_Last_Sample` as a trigger;
- `EM_Quooker_Commit` as a trigger;
- all ten legacy Quooker source reads from FULL reconciliation;
- Quooker freshness/parity as a Core cut-over criterion.

P1 already contains the Quooker electrical load as household consumption. Optional classification can later be implemented as Raspberry Pi enrichment outside the mandatory Core freshness path.

## Event-driven groups retained

- `EM2_Context_UpdatedAt` -> Context
- `EV Deadline status` and `EV Deadline actief` -> Tesla goal
- `WW_Boilermodus` -> WW mode
- `EM2_WW_PostGoal_Opportunity` -> WW post-goal
- `EM2_ContractPrice_Context` -> Planner price context
- `EM2_Day_History` -> Day History
- `EM2_Contract_Type` -> Contract type
- `TEMP_PBTH_JSON_BUFFER` -> PBTH price buffer
- `EM2_Last_Publish` -> Publisher bookkeeping

All event paths retain the 15-second optimistic lease and semantic-write suppression.

## Hourly reconciliation and parity

During SHADOW validation the hourly FULL path may remain as a safety net, but the revised target contains at most **19 live external source reads** rather than 29 because the ten Quooker reads are removed. `WW_STATE_V13` remains absent/null.

The hourly broad `Homey.logic.getVariables()` parity diagnostic is temporary validation infrastructure only. Production Core must contain zero broad Logic scans.

## Revised cut-over gate

Before v0.11b Core cut-over require:

- natural-cycle SHADOW observation for the remaining required groups;
- parity/freshness evidence for remaining required Core dependencies;
- confirmation that CPU and 429 behavior are no worse than the v0.11a integrated baseline;
- Core v0.11b implementation using stable output IDs plus targeted reads of `EM2_Core_Input` and `EM2_Core_Runtime`.

A bounded Quooker freshness solution, Quooker semantic-commit validation and Quooker parity are no longer prerequisites.
