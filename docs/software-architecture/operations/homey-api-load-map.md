---
component: operations
title: Homey API/Load Map
version: 1.0.0
status: active
architecture_status: implemented
last_verified: 2026-08-28
source:
  - Homey runtime flow inventory inspected 2026-08-28
  - docs/software-architecture/architecture/05-homey-api-load-governance.md
---

# Homey API/Load Map

This document is the canonical runtime-load inventory for the Homey Energy Management System. Update it in the same change whenever a Homey flow changes cadence, polling, Logic fan-out, external network publication, device access or actuator access.

## Current throttling investigation baseline — 2026-08-28

| Flow | State | Trigger / cadence | Main Homey load | External load | Fan-out / notes | Class | Lifecycle |
|---|---|---|---|---|---|---|---|
| `EM v2 | 00 Core Tick | v0.10.13 (EV electrical context)` | ON | every 5 min | `getDevices()` + `getVariables()` + multiple Logic writes | none in current Core path | updates `EM2_Public_State`, which starts Power Intent cascade | HIGH | PRODUCTION |
| `EM v2 | 70 History | Day Series v0.5.4` | **OFF for isolation test** | every 5 min when enabled | targeted P1 `getDevice()`; `getDevices()` for PV snapshot in some paths; Logic reads/writes | GitHub GET/PUT every run for `energy-day-v2.json`; more at rollover | primary current throttling suspect; isolated on 2026-08-28 | **CRITICAL** | EVIDENCE / TELEMETRY |
| `EM v2 | 20 Power Intent | P1 v0.2.1 SHADOW` | ON | `EM2_Public_State` changed | `getVariables()` + one output Logic write when revision changes | none | triggers P1 Gate, EV Adapter and EV Adapter Gate | MEDIUM | SHADOW |
| `EM v2 | 80 Validation | P1 Pre-EV Gate v0.2` | ON | `EM2_Power_Intent` changed | `getVariables()` + many typed mirror writes | none | validation fan-out per unique revision | HIGH | VALIDATION |
| `EM v2 | 60 Adapter | EV Power v0.1 SHADOW` | ON | `EM2_Power_Intent` changed | `getVariables()` + adapter output Logic write | none | no device read/write; idempotent by revision/schema/target | MEDIUM | SHADOW |
| `EM v2 | 80 Validation | EV Power Adapter Gate v0.2` | ON | `EM2_Power_Intent` changed + 2 s delay | `getVariables()` + many typed mirror writes | none | validation fan-out; approximately 15 mirror variables may be maintained | HIGH | VALIDATION |
| `EM v2 | 46 Publish | Planner Shadow v0.2` | ON | every 15 min + 90 s | `getVariables()` | GitHub GET current SHA + PUT planner snapshot | external publisher from Homey | MEDIUM | SHADOW / OBSERVABILITY |
| `EM v2 | 76 Evidence | BC Planner Intent Recorder v0.3` | ON | every 15 min | `getVariables()` + buffer/status Logic writes | GitHub GET Planner Shadow file | writes to GitHub are not needed for each sample; reads recently published data back into Homey | MEDIUM | EVIDENCE |
| `EM v2 | 05 Watchdog | Core + Publish Freshness v0.3.3 staggered` | OFF | every 5 min + 120 s when enabled | Logic-only `getVariables()`; possible flow start | none directly | disabled during current investigation | LOW/MEDIUM | DISABLED |
| `EM v2 | 40 Data | Publisher` | OFF | manual/startable | flow start + delay + script | downstream publication | currently disabled | MEDIUM | DISABLED |
| `EM v2 | 72 History | Immutable Day Archive v0.1` | OFF | every 60 min when enabled | `getVariables()` + status write | raw GitHub read + GitHub reads/writes for archive/index | disabled during current investigation | LOW/MEDIUM | DISABLED |
| `Energie | Wasmachine & Droger analyse | v1.4.2` | OFF during clean A/B | event/runtime dependent | appliance analysis | n/a | kept off during throttling isolation | TBD | DISABLED / INVESTIGATION |
| `Energie | Wasmachine & Droger logging | v1.0` | OFF during clean A/B | event/runtime dependent | logging | n/a | kept off during throttling isolation | TBD | DISABLED / INVESTIGATION |
| `Energie | Wasmachine & Droger publicatie | v1.1.1` | OFF during clean A/B | event/runtime dependent | publication | n/a | kept off during throttling isolation | TBD | DISABLED / INVESTIGATION |

## Known cascade

```text
Core Tick (5 min)
  -> EM2_Public_State changes
      -> Power Intent
          -> EM2_Power_Intent changes
              -> P1 Pre-EV Gate
              -> EV Power Adapter
              -> EV Adapter Gate (+2 s)
```

The load impact of this path is the sum of the whole cascade. It must not be assessed as one Core operation.

## Current investigation observations

- Homey returned clean read-only responses immediately before and after disabling Day Series.
- A clean single probe confirms reachability at that moment only.
- Day Series is isolated because it combined a 5-minute cadence, direct device access and GitHub publication in one flow.
- Publisher, Watchdog and Immutable Day Archive were already disabled and therefore do not explain the current baseline load.
- The Power Intent validation chain remains active so EV architecture validation can continue without changing its safety criteria.

## Required redesign candidates

1. Split Day Series into **local sampling** and **external publication** responsibilities.
2. Reuse `EM2_State` wherever authoritative telemetry already exists; retain direct device reads only when they are explicitly needed as an independent measurement checksum.
3. Reduce GitHub publication cadence to a separately justified interval, for example 15 or 30 minutes, while keeping local samples at 5 minutes if required.
4. Review whether completed PASS validation gates can switch to low-write production observability or be retired.
5. Consolidate mirror variables and update only values that materially change.
6. Stagger 5-minute and 15-minute work to prevent synchronized bursts.
7. Avoid write-to-GitHub then immediate read-back-to-Homey patterns when the source data already exists locally.

## Load-map maintenance checklist

For every new or changed flow, record:

| Field | Required |
|---|---|
| Flow name + ID | yes |
| Enabled state | yes |
| Purpose/layer | yes |
| Trigger type/cadence | yes |
| Expected runs/hour | yes |
| `getDevices()` / run | yes |
| targeted `getDevice()` / run | yes |
| `getVariables()` / run | yes |
| Logic writes / run | yes |
| Flow starts / run | yes |
| Insights calls / run | yes |
| External GET/PUT/fetch / run | yes |
| Physical device writes / run | yes |
| Downstream triggered flows | yes |
| Burst/cascade group | yes |
| Load class | yes |
| Lifecycle / retirement condition | yes |
| Measured throttling correlation | when known |

## Incident rule

When throttling occurs, change only one runtime contributor at a time. Record the isolation step and result here before changing the next candidate. Safety gates and validation criteria are never relaxed to make a test pass.
