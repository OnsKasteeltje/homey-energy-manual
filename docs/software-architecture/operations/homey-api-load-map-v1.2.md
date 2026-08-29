---
component: operations
title: Homey API/Load Map
version: 1.2.0
status: active-candidate
architecture_status: runtime-verified
last_verified: 2026-08-29
supersedes_candidate: homey-api-load-map.md v1.1.3
---

# Homey API/Load Map v1.2

This snapshot records the runtime load state after the EV cascade TARGETED-READ LOW-LOAD migration. It is prepared on branch `ev-cascade-low-load-prep`; merge/promotion should make it the canonical load map.

## Current load inventory

| Flow / group | State | Trigger / cadence | Homey API load | Class | Notes |
|---|---|---|---|---|---|
| Core v0.10.17 | ON | every 5 min | 1× `getDevices()` + 1× `getVariables()` per tick, plus bounded Logic writes | HIGH / BOUNDED | Principal unavoidable broad reader; semantic write suppression limits downstream fan-out. |
| Power Intent v0.2.3 TARGETED-READ | ON | `EM2_Control_WW` semantic change | 4× targeted `getVariable(id)`; no collection enumeration | LOW | Public-State decoupled; SHADOW; no device/network calls. |
| P1 Pre-EV Gate v0.2.1 TARGETED-READ | ON | `EM2_Power_Intent` change | 2× targeted `getVariable(id)` | LOW | Logic-only runtime-health gate. |
| EV Power Adapter v0.1.1 TARGETED-READ SHADOW | ON | `EM2_Power_Intent` change | 4× targeted `getVariable(id)` | LOW | No device/network/Insights access; fixed 3×230 V mapping retained. |
| EV Adapter Gate v0.2.1 TARGETED-READ | ON | `EM2_Power_Intent` change + 2 s | 4× targeted `getVariable(id)` | LOW | Revision/safety/electrical coherence checks retained. |
| EV Power Actuator v0.2.2 TARGETED-READ LIVE OWNERSHIP | ON | `EM2_EV_Adapter_Gate` change | 6× targeted `getVariable(id)`; LIVE=false = 0 charger reads/writes; LIVE=true may enumerate charger for write/no-op check | LOW in SHADOW / SAFETY-CRITICAL LIVE | Gate-driven, fail-closed. |
| EV Control Status v0.1 | OFF | Gate/status change + 2 s when enabled | legacy 1× `getVariables()` per event + GitHub publication | OFF / REDESIGN BEFORE ENABLE | Last remaining broad Logic read in EV observability; not part of active runtime load while OFF. |
| Planner v0.4.4 LOW-LOAD | ON | scheduled/manual | targeted Logic access | LOW | No broad Logic scan in current LOW-LOAD implementation. |
| Planner Shadow Publisher v0.4 LOW-LOAD | ON | planner snapshot change | 4× targeted Logic reads; GitHub PUT only for new plan key | LOW | No `getVariables()`, `getDevices()` or Insights. |
| Main Publisher v1.0.8 LOW-LOAD | ON | `EM2_Public_State` change | 5× targeted Logic reads; revision/heartbeat gated GitHub publication | LOW | No broad collection scan. |
| Day Series v0.5.4 | OFF | every 5 min when enabled | `getVariables()` + P1/device access + GitHub GET/PUT | CRITICAL WHEN ON | Keep isolated until split into local sampling and external publication. |
| Watchdog v0.3.3 | OFF | every 5 min + 120 s when enabled | broad Logic enumeration(s), possible flow starts | MEDIUM/HIGH WHEN ON | Keep OFF during throttling investigation. |
| Contract Price Adapter v0.8 | ON | every 15 min | FIXED: broad Logic reads but 0 `getDevices()`; DYNAMIC may access PBTH devices | MEDIUM | Candidate for later targeted-read conversion. |
| BC Planner Intent Recorder | ON | every 15 min | broad `getVariables()` + bounded local writes | LOW/MEDIUM | Candidate for later targeted-read conversion. |
| WW Post-Goal Opportunity | ON | every 15 min | broad `getVariables()` + bounded Logic writes | MEDIUM | Candidate for later targeted-read conversion. |
| Control Audit | ON | event-driven | broad `getVariables()` per semantic event | LOW/MEDIUM | Fixed 5-min polling already removed. |
| WW Seasonal Source Advisor | ON | daily | 1× broad Logic scan + GitHub reads | LOW average | Daily burst only. |
| Immutable Day Archive | OFF | hourly when enabled | broad Logic + GitHub archive access | OFF | No current runtime load. |
| Washer/dryer analysis/logging/publication | OFF | event-dependent | not currently in baseline | OFF | Keep isolated until separately reviewed. |

## EV cascade after LOW-LOAD migration

```text
Core (5 min; broad single-reader remains)
  -> EM2_Control_WW
      -> Power Intent        4 targeted reads
          -> EM2_Power_Intent
              -> P1 Gate     2 targeted reads
              -> EV Adapter  4 targeted reads
              -> EV Gate     4 targeted reads (+2 s)
                   -> EM2_EV_Adapter_Gate
                       -> EV Actuator 6 targeted reads
                          LIVE=false: 0 charger reads/writes
                          LIVE=true: guarded charger access only
```

### Load delta

Before migration, the four upstream EV stages each performed a full `Homey.logic.getVariables()` collection enumeration. At the nominal 12 Core revisions/hour this represented approximately **48 full Logic collection enumerations/hour**.

After the runtime-verified TARGETED-READ migration:

- Power Intent: 0 full Logic enumerations;
- P1 Pre-EV Gate: 0 full Logic enumerations;
- EV Power Adapter: 0 full Logic enumerations;
- EV Adapter Gate: 0 full Logic enumerations;
- EV Actuator: 0 full Logic enumerations;
- active EV control cascade total: **0 full Logic collection enumerations/hour**;
- reads are now bounded targeted `getVariable(id)` calls proportional to actual dependencies.

`EV Control Status v0.1` remains OFF and therefore contributes zero current runtime load. It must be migrated to targeted reads before it is re-enabled.

## Current throttling priority

The EV cascade is no longer a primary structural throttling suspect. Current priorities are:

1. keep Day Series v0.5.4 OFF until redesigned;
2. keep Watchdog OFF during the stability baseline;
3. quantify and convert remaining active quarter-hour broad Logic readers, starting with the highest fan-out/cadence combination;
4. review Core `getDevices()` optimization separately; do not replace its single `getVariables()` reader with many targeted calls without evidence that this reduces Homey API pressure;
5. migrate EV Control Status to targeted reads before re-enabling observability;
6. stop immediately on any Homey `Too many requests` response; no retry loops.

## Runtime evidence — 2026-08-29

Direct Homey flow inspection confirmed the following active runtime versions and access patterns:

- `EM v2 | 20 Power Intent | P1 v0.2.3 TARGETED-READ LOW-LOAD` — ON, 4 targeted Logic reads.
- `EM v2 | 80 Validation | P1 Pre-EV Gate v0.2.1 TARGETED-READ` — ON, 2 targeted Logic reads.
- `EM v2 | 60 Adapter | EV Power v0.1.1 TARGETED-READ SHADOW` — ON, 4 targeted Logic reads.
- `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.1 TARGETED-READ` — ON, 4 targeted Logic reads.
- `EM v2 | 60 Actuator | EV Power v0.2.2 TARGETED-READ LIVE OWNERSHIP` — ON, 6 targeted Logic reads; zero charger access while LIVE=false.
- `EM v2 | 81 Observability | EV Control Status v0.1` — OFF; legacy broad Logic enumeration remains in its code.

This evidence supersedes the EV-cascade rows and the old ~48 Logic-enumerations/hour statement in load-map v1.1.3.