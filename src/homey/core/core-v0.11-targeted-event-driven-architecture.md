# Core v0.11 — Targeted / Event-Driven Read Architecture

Status: **DESIGN / NOT DEPLOYED**

Date: 2026-08-29

Baseline: active Homey Core v0.10.17. This document is a structural load-reduction design only; it does not authorize a Homey deployment.

## Problem statement

The current Core is deliberately the EMS single broad reader, but it still performs one full Homey device enumeration and one full Logic-variable enumeration every 5 minutes:

```js
const [devices,vars]=await Promise.all([
  Homey.devices.getDevices(),
  Homey.logic.getVariables()
]);
```

The 2026-08-29 canonical Homey API/Load Map identifies this Core read as the primary proven structural broad-read baseline. Most other recurring broad-read flows are currently OFF or have already been converted to targeted reads.

The objective of v0.11 is therefore to remove broad collection reads from Core without moving safety-critical runtime control out of Homey.

## Architecture decision

Homey remains the realtime control plane.

Target architecture:

```text
relevant device / Logic change
          |
          v
 canonical input/state update
          |
          v
       Core logic
          |
          +--> semantic State / Decision / Control outputs
          |
          +--> Power Intent -> Adapter -> Gate -> Actuator

periodic reconciliation tick (fallback only)
          |
          +--> targeted reads of known dependencies
```

Polling becomes reconciliation/self-healing rather than the primary information-gathering mechanism.

## Current device dependency inventory

The Core source already contains stable IDs for the device dependencies below, so collection enumeration is not required merely to discover them.

| Dependency | Current Core key | Stable ID known in source | Use |
|---|---|---:|---|
| P1 meter | `p1` | yes | grid power, phase power/current, freshness |
| Easee charger | `ev` | yes | EV power/current/state/meter |
| Easee Equalizer | `eq` | yes | power and phase currents |
| Hot-water boiler | `boiler` | yes | power and on/off state |
| Quatt | `quatt` | yes | electrical/thermal power, COP, heating/CV state |
| SolarEdge inverter | `se` | yes | PV power + timestamp |
| GoodWe 4.2 kW | `gw42` | yes | PV power + timestamp |
| GoodWe 2.0 kW | `gw20` | yes | PV power + timestamp |
| AEG washer | `washer` | yes | direct connection/appliance/cycle/time-to-end status |
| AEG dryer | `dryer` | yes | direct connection/appliance/cycle/time-to-end status |

### Finding

**`Homey.devices.getDevices()` should be the first broad read removed.**

Candidate replacement: targeted `getDevice({id})` calls only for devices Core actually needs, preferably only when the relevant source changes. The periodic reconciliation path may target the known IDs rather than enumerate the complete Homey device collection.

Do not assume undocumented filtering on `getDevices()` is a stable production mechanism. Prefer explicit targeted device reads and validate the exact Homey API contract in runtime before deployment.

## Current Logic dependency inventory

Known Core inputs visible in the current source / v0.10.17 Planner Input patch include at least:

### EV / goals
- `EV Deadline actief`
- `EV Deadline tijd`
- `EV Latest start`
- `EV Resterend kWh`
- `EV Deadline status`

### Warm water / mode
- `WW_Boilermodus`

### Context / price / PV
- `M7_PV_Top4h`
- `M7_Price_Negative`
- `M7_Price_Cheap_Next4h`
- `M7_Price_Expensive_Next4h`
- `EM2_Context_UpdatedAt`
- `EM2_ContractPrice_Context`
- `EM2_Day_History`
- `EM2_Contract_Type`
- `TEMP_PBTH_JSON_BUFFER`

### Quooker state currently consumed by Core
- `EM_Quooker_Last_Sample`
- `EM_Quooker_Active`
- `EM_Quooker_Power_W`
- `EM_Quooker_Status`
- `EM_Quooker_Switch_On`
- `EM_Quooker_Baseline_L3_W`
- `EM_Quooker_Last_Transition`
- `EM_Quooker_Last_Heating_At`
- `EM_Quooker_Last_Heating_Power_W`
- `EM_Quooker_Transition_History`

### Core-owned / downstream variables
Core also owns or updates semantic outputs such as `EM2_State`, `EM2_Decision`, `EM2_Shadow`, `EM2_Control_WW`, `EM2_Planner_Input` and publisher/control status variables. These are outputs and should not create a second read path.

## Logic-read strategy

`Homey.logic.getVariables()` is the second broad-read elimination target.

The v0.10.17 design already establishes the preferred API pattern for downstream consumers: a stable Logic variable ID plus `Homey.logic.getVariable({id})` / `updateVariable({id,...})` rather than `getVariables()`.

For Core, migrate in two stages:

1. **ID registry / targeted reconciliation**
   - provision and record stable IDs for every required Logic input;
   - targeted-read only those variables during reconciliation;
   - no collection scan during normal ticks.

2. **Event-driven canonical input**
   - trigger only on semantically relevant input changes where Homey Flow supports a reliable variable/device-change trigger;
   - update a narrow canonical input/state object;
   - let Core recompute from that canonical input;
   - retain a slow targeted reconciliation run as self-healing protection.

## Proposed versions

### v0.11a — targeted device reads

Goal: remove `getDevices()` while changing no policy.

- preserve current 5-minute Core cadence initially;
- replace complete device enumeration with targeted reads for the known dependency IDs;
- retain current single `getVariables()` temporarily;
- preserve all State/Decision/control semantics;
- no new downstream triggers;
- no device writes.

Acceptance:

- zero `getDevices()` collection calls per Core run;
- identical material `EM2_State` / `EM2_Decision` output for the same inputs;
- source freshness/skew logic still works;
- no new 429 / `Too many requests`;
- no increased fan-out.

### v0.11b — targeted Logic reads

Goal: remove `getVariables()`.

- establish stable-ID registry for the required Logic inputs;
- use targeted `getVariable({id})` reads;
- preserve current output and semantic suppression;
- provisioning/discovery may be a controlled one-time maintenance action, never a recurring collection scan.

Acceptance:

- zero `getVariables()` collection calls during steady-state Core execution;
- missing or stale required IDs fail closed / produce explicit degraded state rather than silently falling back to a broad scan;
- same functional Core result as baseline for equivalent input snapshots.

### v0.12 — event-driven primary, reconciliation fallback

Only after v0.11a and v0.11b pass soak.

- relevant input changes become the primary Core wake-up mechanism;
- coalesce bursts so multiple near-simultaneous source changes cause at most one Core calculation/commit;
- retain semantic output suppression;
- reduce scheduled Core reconciliation from 5 minutes to a candidate 15–30 minutes;
- choose final reconciliation cadence only from runtime evidence.

No automatic fallback to `getDevices()` or `getVariables()` is allowed.

## Burst / fan-out protection

Event-driven does **not** mean every source event should start a full Core calculation immediately.

Required protections:

- short coalescing/debounce window for simultaneous P1/PV/context events;
- run lease / idempotency guard;
- semantic comparison before Logic writes;
- separate freshness metadata from semantic control state where possible;
- one canonical commit signal per meaningful control-domain change;
- publication remains decoupled from control fan-out.

## Safety boundary

The optimization must not relocate these responsibilities outside Homey:

- realtime gate decisions;
- fail-closed behavior;
- actuator ownership;
- EV anti-flapping / run lease;
- physical write guards;
- local reconciliation when external planning/publication is unavailable.

External systems may own planning, analytics, history and presentation; Homey remains authoritative for local runtime safety/control.

## Test sequence

1. Snapshot current v0.10.17 material outputs and dependency health.
2. Deploy v0.11a only.
3. Run one controlled smoke, then natural soak.
4. Compare material State/Decision outputs and Homey throttle behavior.
5. Only on PASS, prepare v0.11b stable Logic-ID registry.
6. Deploy v0.11b and repeat smoke/soak.
7. Only after both PASS, prototype event-driven v0.12.
8. Evaluate 15-minute vs 30-minute reconciliation against freshness and recovery requirements.

Stop immediately on Homey `429` / `Too many requests`; do not retry-probe during the throttle window.

## Load-map expectation

Current broad-read baseline at 5-minute cadence:

- `getDevices()`: up to 12 collection enumerations/hour;
- `getVariables()`: up to 12 collection enumerations/hour.

After v0.11 steady state:

- `getDevices()`: **0 collection enumerations/hour**;
- `getVariables()`: **0 collection enumerations/hour**;
- only targeted dependency reads remain.

After a later v0.12 event-driven promotion, even targeted scheduled reads should primarily occur in the slower reconciliation path; normal state changes should be handled from narrow event-driven inputs.

## Decision / next action

**Proceed with v0.11a as the next Core load-reduction experiment. Do not deploy v0.12 directly.**

Before implementation, verify the exact targeted Homey device-read call supported in the active HomeyScript runtime and build a capability-by-capability parity checklist from the current Core source. No broad-read fallback may be added merely for convenience.
