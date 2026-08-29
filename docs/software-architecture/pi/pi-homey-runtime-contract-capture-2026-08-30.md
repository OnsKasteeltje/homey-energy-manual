# Pi EMS — Homey runtime contract capture (2026-08-30)

Status: **READ-ONLY RUNTIME CAPTURE**. No flows were started, no enablement was changed, and no device capability was written during this capture.

## Purpose

This document freezes the current Homey-side runtime boundaries needed for the Raspberry Pi EMS migration. It captures the active contracts for Publisher v1.0.11, WW Power v0.2, WW Power Adapter Gate v0.2, WW Actuator v0.9, EV Power Adapter Gate v0.2.1, EV Power Actuator v0.2.2, and the Core Snapshot Aggregator v0.1 SHADOW.

## 1. Publisher v1.0.11 SCHEDULED LOW-LOAD

Flow: `EM v2 | 40 Data | Publisher v1.0.11 SCHEDULED LOW-LOAD`
Flow ID: `fe84bc17-72d4-4fbb-9a69-b3d751b0ffcd`
Runtime: enabled, not broken.

Trigger model:
- Cron every 15 minutes.
- Fixed +8 second delay before execution.
- Manual Start also reaches the publisher action.

Read set: exactly five targeted Logic variables:
- `EM2_Public_State` (`b0d68d98-efdb-41e4-be72-3bd6bdcc19eb`)
- `EM2_State` (`8e1efbb0-7999-494c-9429-7d274afacd79`)
- `GH_Status_Token` (`235cfe0f-5760-48b9-9349-a33be47d04d1`)
- `EM2_Last_Publish` (`fc95dcad-55d5-4d21-be15-f565f0a9bac3`)
- `EM2_Last_Published_Revision` (`c10ea01b-3dfc-4e04-bb27-2a56dfc636cd`)

Publication contract:
- Publisher version: `EM2_PUBLISHER_V1.0.11`.
- Target: `OnsKasteeltje/homey-energy-manual`, branch `main`, path `docs/data/energy-state-v2.json`.
- `MIN_PUBLISH_MS = 14m50s`; metadata advertises 900 s minimum cadence.
- Public State must be an object with numeric revision.
- If authoritative state has a numeric revision, it must equal Public State revision.
- GitHub token must be present.
- Payload metadata is refreshed with `generated_at`, `heartbeat_at`, `publisher_version`, `state_revision`, `publish_reason`, and `min_publish_interval_sec`.
- Publication reason is `REVISION_EVENT` when revision changed; otherwise `HEARTBEAT_EVENT`.
- GitHub Contents API performs GET SHA then PUT; 409/422 gets exactly one GET+PUT retry.
- Publication status/diagnostic variables are updated, but publication remains outside the control path.

Pi requirement:
- Reproduce this behavior as a publication-only scheduled service.
- Preserve the 15-minute cadence, jitter tolerance, revision validation, bounded conflict retry, and no control-side effects.

## 2. WW Power Adapter v0.2 TARGETED-READ SHADOW

Flow: `EM v2 | 60 Adapter | WW Power v0.2 TARGETED-READ SHADOW`
Flow ID: `472d0355-3bb9-4a42-be43-114b57822136`
Runtime: enabled, not broken.

Trigger:
- `EM2_Power_Intent` changed.
- Manual Start.

Read set: exactly two targeted Logic variables:
- `EM2_Power_Intent` (`04b57041-dd7f-41f7-a00a-f023afb1ccee`)
- `EM2_WW_Power_Adapter` (`686181b9-e135-40fe-b09d-df5928269466`)

Input validation:
- schema `EM2_POWER_INTENT_V0.2`
- `valid === true`
- `deviceWrites === false`
- numeric `sourceRevision`
- `targets.ww.target_on` must exist and be boolean or null.

Mapping:
- true → status `OK_ON`, command value true
- false → status `OK_OFF`, command value false
- null → status `OK_HOLD`, command value null
- invalid input → `INVALID_POWER_INTENT`, value null

Output:
- schema `EM2_WW_POWER_ADAPTER_V0.2`
- inputSchema `EM2_POWER_INTENT_V0.2`
- readOnly true
- controlMode `SHADOW`
- deviceWrites false
- command capability `onoff`
- command physicalWrite false
- ownership: physicalWriter `WW_ACTUATOR`, policy `ENERGY_CORE_P1`, translation `WW_POWER_ADAPTER`
- semantic no-op suppression prevents timestamp-only rewrites.

Pi requirement:
- Update the existing Pi WW replay contract from v0.1 output schema to the exact v0.2 output contract before parity claims.

## 3. WW Power Adapter Gate v0.2 TARGETED-READ

Flow: `EM v2 | 80 Validation | WW Power Adapter Gate v0.2 TARGETED-READ`
Flow ID: `39c39cc5-12bb-4494-ba45-bad47a656696`
Runtime: enabled, not broken.

Trigger:
- `EM2_WW_Power_Adapter` changed.
- Manual Start.
- 2 second settle delay.

Read set: three targeted Logic variables:
- Power Intent
- WW Adapter
- WW Gate output

PASS requires all of:
- adapter schema `EM2_WW_POWER_ADAPTER_V0.2`
- adapter input schema `EM2_POWER_INTENT_V0.2`
- adapter revision equals Power Intent revision
- Power Intent is valid, SHADOW-safe, and contains a valid boolean/null target
- adapter is valid/readOnly/SHADOW/deviceWrites=false
- adapter command is exact `onoff` translation of target
- adapter command physicalWrite=false
- status matches `OK_ON` / `OK_OFF` / `OK_HOLD`
- no collection scans and no device writes.

Output:
- schema `EM2_WW_ADAPTER_GATE_V0.2`
- finalStatus `PASS` or `FAIL`
- valid mirrors PASS
- failed command is forced to null
- semantic output suppression.

Pi requirement:
- Implement this gate as a pure deterministic validator and preserve exact revision coherence and fail-closed null command on failure.

## 4. WW Actuator v0.9 TARGETED-READ LIVE

Flow: `EM v2 | 60 Control | Warm Water Actuator v0.9 TARGETED-READ LIVE`
Flow ID: `40d45aeb-174e-4a83-9a42-71ae46065cb4`
Runtime: enabled, not broken.

Important manual Start behavior:
- Manual Start explicitly sets `EM2_WW_Hybrid_Enabled=true`, waits 1 second, then evaluates the current command.
- This is a control action and must never be invoked by Pi preparation tooling.

Event path:
- Triggered by `EM2_WW_Adapter_Gate` changes.

Read set before device access: six targeted Logic variables:
- WW hybrid kill/arm flag
- `WW_Boilermodus`
- Power Intent
- WW Adapter
- WW Gate
- actuator status.

Guards before boiler device access:
- LIVE/kill flag true
- boiler source mode true
- exact schemas for Intent/Adapter/Gate
- exact revision alignment across all three
- Gate PASS and valid
- maximum age 10 minutes across Gate and Intent
- HOLD returns without touching the device
- command must be boolean.

Device boundary:
- exact boiler device ID `8238b270-21a2-4284-aa78-6b9b58d254ab`
- reads `onoff` only after all guards
- no-op if current state already equals target
- sole physical write is `setCapabilityValue('onoff', value)`
- runtime statuses include blocked states, HOLD, NOOP_ALREADY_TARGET and WRITE_OK.

Pi requirement:
- Keep the Homey actuator as the physical writer during early migration.
- Move policy, adapter and gate first; only transfer physical ownership after Pi shadow parity and a dedicated LIVE promotion gate.

## 5. EV Power Adapter Gate v0.2.1 TARGETED-READ

Flow: `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.1 TARGETED-READ`
Flow ID: `ec5e5d34-8205-4cf0-a661-7bf744feb6e0`
Runtime: enabled, not broken.

Trigger:
- Power Intent changed.
- Manual Start.
- 2 second settle delay.

Read set: four targeted Logic variables: Intent, EV Adapter, State, prior Gate.

Key electrical contract:
- 3 phases
- 230 V
- 690 W/A
- minimum 6 A
- maximum integer A in [6,16]
- floor quantization (`FLOOR_3P230_FAIL_CLOSED`)
- target 0 → 0 A
- target below minimum executable power → 0 A
- otherwise floor(target_W / 690), clamped to max A
- adapter may never increase upstream requested power except max-current clamp case.

PASS requires exact schema/revision/safety/electrical/translation coherence. Duplicate mutation for the same source revision is detected and fails.

Pi requirement:
- Preserve this validator semantically before transferring EV gate ownership.

## 6. EV Power Actuator v0.2.2 TARGETED-READ LIVE OWNERSHIP

Flow: `EM v2 | 60 Actuator | EV Power v0.2.2 TARGETED-READ LIVE OWNERSHIP`
Flow ID: `fea23193-a03f-49dd-9780-7e72ee48747d`
Runtime: enabled, not broken.

Manual Start behavior:
- forces `EM2_EV_Actuator_Live_Enabled=false` before evaluation.
- With LIVE=false, zero charger reads/writes occur.

Event path:
- Gate-driven by `EM2_EV_Adapter_Gate` change.

Pre-device read set: six targeted Logic variables.

Freshness:
- Intent, Adapter, State, Gate must all be <=120 seconds old.

LIVE guards:
- exact schemas
- exact revision equality among Intent, Adapter, State and Gate revision fields
- adapter SHADOW safety contract valid
- target_W integer >=0
- requested_A integer and either 0 or in [6,16]
- executable_W = requested_A * 690 and may not exceed target power except max clamp
- Gate PASS.

Device boundary:
- exact Easee device ID `65ee9fda-9535-44ab-8037-809587bc8f1c`.
- Current implementation still obtains the charger through `Homey.devices.getDevices()` once LIVE guards have passed; this is a remaining broad collection read on the LIVE path.
- Physical capability is `target_charger_current`.
- no-op if already target.
- Any LIVE validation failure tries to fail closed to 0 A.

Pi requirement:
- Do not copy the broad `getDevices()` pattern.
- Pi/Homey gateway should use exact charger identity and an explicit actuator command contract.
- Keep fail-closed-to-zero semantics for genuine LIVE ownership, but separate transport failure from semantic validation failure in diagnostics.

## 7. Core Snapshot Aggregator v0.1 SHADOW

Flow: `EM v2 | 12 Input | Core Snapshot Aggregator v0.1 SHADOW`
Flow ID: `758f3353-51f5-4e68-a1f4-3acf30ec5a87`
Runtime: enabled, not broken.

Output Logic variable:
- `EM2_Core_Input` (`05b27e13-9ebe-42af-8371-11c1f7148309`)
- schema `EM2_CORE_INPUT_V0.1`
- monotonically increments local `revision` only when semantic source content changes
- `generatedAt` changes only with a semantic change.

Lease:
- Logic variable `8891c3aa-d93a-47c3-a047-acd460cdc032`
- schema `EM2_CORE_INPUT_LEASE_V0.1`
- 15 second ownership lease protects concurrent partial updates.

Event-driven source groups:
- context on `EM2_Context_UpdatedAt`
- Tesla goal on EV deadline status/active
- hot-water mode on `WW_Boilermodus`
- hot-water post-goal opportunity
- contract-price context
- day history
- contract type
- PBTH price buffer
- publication metadata.

Hourly FULL reconciliation:
- refreshes all above plus the Quooker group.
- Quooker high-frequency Last_Sample is deliberately NOT an event trigger.

Hourly parity diagnostic:
- performs `Homey.logic.getVariables()` as one broad Logic collection scan.
- compares snapshot groups against the current Logic collection.
- emits `EM2_CORE_INPUT_PARITY_V0.1`.
- This broad scan is explicitly diagnostic only, once hourly.

Current snapshot groups:
- `quooker`
- `context`
- `teslaGoal`
- `hotWater`
- `planner`
- `publication`
- `legacy`.

### Assessment as Homey→Pi interface

**Good migration bridge:** yes.

Reasons:
- one stable versioned envelope
- semantic revision
- event-driven low-frequency producer commits
- centralizes many Logic-variable reads
- no physical writes
- lease avoids torn partial updates
- provides an explicit parity diagnostic during migration.

**Not sufficient as the sole Pi EMS input:** no.

Missing from this snapshot are the realtime physical observations that Pi Core needs for independent EMS operation, including:
- P1 grid power and phase data
- SolarEdge / GoodWe realtime PV power
- Easee realtime charger state/power/current
- Equalizer state if retained as a source
- boiler realtime on/off/power
- Quatt realtime heat-pump observations
- freshness/quality envelopes per physical observation.

Quooker is also only hourly reconciled in this SHADOW stage, so the snapshot is deliberately unsuitable for high-frequency Quooker detection/control.

### Recommended Pi split

Use two distinct Homey→Pi contracts during migration:

1. **`EM2_CORE_INPUT_V0.1` as low-frequency semantic/configuration snapshot**
   - goals
   - contract/configuration
   - planner context
   - WW semantic state
   - publication bookkeeping
   - low-frequency Quooker history/reference state.

2. **Pi Central State physical observation feed**
   - exact device IDs
   - targeted capability reads only
   - one read per device per sampling interval
   - observation envelope: value, observed_at, received_at, source, quality, stale_after_s
   - fan-out only from Pi Central State; domain modules never read Homey directly.

This avoids turning `EM2_Core_Input` into an oversized high-frequency bus while still using it to eliminate repeated Homey Logic reads.

## 8. Required Pi changes identified by this capture

1. Promote the Pi WW adapter model to exact `EM2_WW_POWER_ADAPTER_V0.2` semantics.
2. Add pure Pi WW Gate v0.2 validation and replay cases.
3. Add WW Actuator v0.9 as a reference-only LIVE contract; keep physical ownership on Homey initially.
4. Freeze EV Gate v0.2.1 electrical/revision semantics in Pi replay tests.
5. Treat EV Actuator v0.2.2 Homey `getDevices()` use as an implementation detail to eliminate, not a contract to copy.
6. Add a Pi ingestion model for `EM2_CORE_INPUT_V0.1` as a semantic/configuration feed.
7. Keep physical device observations separate in Central State with freshness/quality metadata.
8. Add shadow comparison dimensions for source revision, semantic snapshot revision, physical observation age, gate result, and command output.
9. Do not transfer LIVE ownership based solely on Snapshot Aggregator parity.

## 9. Remaining gaps

- Exact current EV Power Adapter v0.1.1 source was not required for this pass because the existing Pi EV translation replay already models the captured electrical semantics, but it should still be source-frozen before full EV parity certification.
- The Snapshot Aggregator schema currently has no per-field freshness or quality metadata; Pi must not infer freshness from snapshot `generatedAt` alone.
- The hourly parity scan still uses broad `Homey.logic.getVariables()`; acceptable as temporary SHADOW diagnostic, but it should disappear after migration confidence is established.
- No LIVE behavior was exercised during this capture; runtime code was inspected only.

## Safety conclusion

The captured contracts support the existing migration strategy: **semantic/configuration aggregation can move first, then Core/Planner/Power Intent/adapters/gates, while Homey retains actuator ownership until deterministic replay and live SHADOW parity have passed.** The Core Snapshot Aggregator is useful as a low-load migration bridge, but it must complement—not replace—the Pi Central State physical observation layer.
