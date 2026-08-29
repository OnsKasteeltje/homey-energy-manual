---
component: operations
title: Homey API/Load Map
version: 1.2.0
status: active
architecture_status: implemented
last_verified: 2026-08-29
source:
  - Homey runtime inventory and targeted flow reads, 2026-08-29
  - src/homey/MIGRATION_BATCH_2026-08-28.md
  - docs/software-architecture/architecture/05-homey-api-load-governance.md
---

# Homey API/Load Map

This is the canonical runtime-load inventory for the Home Energy Management System. Update this file whenever cadence, polling, broad collection reads, targeted reads, external I/O, device access, actuator access or event fan-out changes.

## Investigation rule

During throttling diagnosis, prefer GitHub/source inspection and exact flow-ID reads. Do not repeatedly enumerate Homey flows. If Homey returns `Too many requests`, stop immediately and do not retry.

## Verified runtime baseline — 2026-08-29

| Flow | ID | Runtime | Trigger / cadence | Homey load | External / device load | Assessment |
|---|---|---:|---|---|---|---|
| `EM v2 | 00 Core Tick | v0.10.17 (Planner Input low-load)` | `227f8d3b-7551-46dd-837d-1b8c69add824` | **ON** | every 5 min | one `getDevices()` + one `getVariables()` per tick; downstream Logic snapshot writes | no external I/O in Core | **Primary proven structural broad-read baseline**; keep as single-reader until a cheaper device-read pattern is proven |
| `EM v2 | 20 Power Intent | P1 v0.2.3 TARGETED-READ LOW-LOAD` | `19d9d8a6-ec32-4639-be5e-71e9f034d31b` | **ON** | `EM2_Control_WW` change | targeted Logic reads only | none | low-load |
| `EM v2 | 80 Validation | P1 Pre-EV Gate v0.2.1 TARGETED-READ` | `557ed7e8-9efe-4173-bc06-8e629214e172` | **ON** | `EM2_Power_Intent` change | targeted Logic reads only | none | low-load |
| `EM v2 | 60 Adapter | EV Power v0.1.1 TARGETED-READ SHADOW` | `953e9b18-3576-4557-b940-ed4a64eb2516` | **ON** | `EM2_Power_Intent` change | targeted Logic reads only | no device access | low-load |
| `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.1 TARGETED-READ` | `ec5e5d34-8205-4cf0-a661-7bf744feb6e0` | **ON** | `EM2_Power_Intent` change +2 s | targeted Logic reads only | none | low-load |
| `EM v2 | 60 Actuator | EV Power v0.2.2 TARGETED-READ LIVE OWNERSHIP` | `fea23193-a03f-49dd-9780-7e72ee48747d` | **ON** | `EM2_EV_Adapter_Gate` change | targeted Logic reads; LIVE=false has zero device reads/writes | LIVE=true may enumerate Easee path for guarded write/no-op | low in SHADOW; safety-critical in LIVE |
| `EM v2 | 40 Data | Publisher v1.0.9 HARD-GATE LOW-LOAD` | `fe84bc17-72d4-4fbb-9a69-b3d751b0ffcd` | **ON** | `EM2_Public_State` change +2 s | five targeted Logic reads | hard minimum 15 min between GitHub publishes; zero GitHub I/O inside gate window | active controlled A/B mitigation |
| `EM v2 | 45 Planner | 24h Energy Plan v0.4.4 SHADOW LOW-LOAD` | `27617767-0a64-43a3-9bcb-e34b0dd6a5c0` | **OFF** | every 15 min +45 s if enabled | one targeted Planner Input read + one targeted snapshot write | Open-Meteo when enabled | no current load |
| `EM v2 | 46 Publish | Planner Shadow v0.4 event-driven LOW-LOAD` | `5b3b80fe-96d1-406d-91ef-cf75a4e65d45` | **OFF** | planner snapshot change +2 s if enabled | four targeted Logic reads | GitHub PUT per new plan key when enabled | no current load |
| `EM v2 | 30 Context | Contract Price Adapter v0.8` | `b1c495cb-6ccd-4fb8-b4bf-365845dbb6e7` | **OFF** | every 15 min if enabled | broad Logic reads; dynamic branch can enumerate PBTH device | PBTH in dynamic mode | no current load; refactor before re-enable |
| `EM v2 | 30 Context | Price + PV v0.6.1 SHADOW` | `d5b79dfe-2cff-4be6-9f93-93bb453dd9fa` | **OFF** | every 15 min if enabled | `getVariables()` + `getDevices()` | PBTH inter-app API | no current load; broad-read candidate |
| `EM v2 | 15 State | Warm Water Observer v0.2` | `957a85b5-a4ff-4fe2-bc6b-2e56e60387ea` | **OFF** | manual/programmatic if enabled | one `getVariables()` | programmatically starts old WW Control v0.3 | no current load; downstream legacy coupling is technical debt |
| `EM v2 | 10 Input | EV Deadline Goal Adapter v0.1` | `445cb82c-5e1f-43c3-b2cf-f2d78fec6e16` | **OFF** | every 1 min if enabled | one `getVariables()` plus multiple Logic writes | GitHub API/raw fetch every run | **high-risk if re-enabled: up to 60 broad Logic reads + 60 external fetches/hour** |
| `EM v2 | 05 Config | EMS Settings Sync v0.3 low-load` | `9193b3ae-1e3d-4b52-aa95-60aff099e68a` | **OFF** | every 5 min if enabled | one `getVariables()`; strict no-op after matching request | GitHub API/raw fetch every run | no current load; targeted/event-driven redesign preferred |
| `EM v2 | 06 Freshness | Day-Night Normalizer v0.1.1` | `a41079f7-2287-4ec0-9e9b-27619e93ba35` | **OFF** | every 5 min +30 s if enabled | one `getVariables()`; may rewrite `EM2_State` and `EM2_Public_State` | none | no current load; **fan-out amplifier if re-enabled** |
| `EM v2 | 70 Planner | WW Scheduling SHADOW v0.2` | `1d822642-87e8-4b0f-870e-5f2e7eef9372` | **OFF** | programmatic if enabled | one `getVariables()` | none | no current load; legacy broad-read |
| `[RETIRED DUPLICATE] EM v2 | 70 Planner | WW Scheduling SHADOW v0.1` | `2248f9ae-159b-474e-8680-2e947709e664` | **OFF** | programmatic if enabled | one `getVariables()` | none | retired duplicate; keep disabled/remove later |
| `EM v2 | 50 Decision | WW Post-Goal Opportunity v0.4 SHADOW` | `5538f1c9-9a21-4328-9896-942952f5c55f` | **OFF** | every 15 min if enabled | one `getVariables()` | none | no current load |
| `EM v2 | 50 Decision | WW Seasonal Source Advisor v0.3 SHADOW idempotent` | `543664be-d07a-4099-92d1-07878b73215d` | **OFF** | daily 20:30 if enabled | one broad Logic snapshot; extra reads only in notification paths | three GitHub GETs | no current load |
| `EM v2 | 70 History | Control Audit v0.4 low-load` | `df295b26-9a47-497a-87c7-ccfd32323db1` | **OFF** | event-driven if enabled | one `getVariables()` per event | bounded GitHub publish | no current load |
| `EM v2 | 70 History | Day Series v0.6 LOCAL SAMPLER` | `14027232-905e-4b8b-828d-5b44b8f6692e` | **OFF / isolation** | implementation currently under redesign | historically broad Logic/device reads + frequent GitHub I/O | history publication path split into local sampler / low-frequency publisher | keep isolated during throttle investigation |
| `EM v2 | 72 History | Immutable Day Archive v0.1` | `322bcfe6-1ec4-46d4-a840-d13009d9c9c9` | **OFF** | hourly if enabled | one `getVariables()` | raw series read + GitHub archive/index I/O | no current load |
| `EM v2 | 76 Evidence | BC Planner Intent Recorder v0.4 local-first` | `9aba3344-b8b4-423f-9132-b606990b9ffe` | **OFF** | every 15 min if enabled | one `getVariables()` | GitHub mainly on rollover/archive | no current load |
| `EM v2 | 81 Observability | EV Control Status v0.1` | `f6edba38-ddf1-45e5-890e-c183aa2055d5` | **OFF** | Gate / actuator change if enabled | one `getVariables()` | GitHub status publish | no current load; migrate before re-enable |
| `EM v2 | 60 Control | Warm Water Actuator v0.8 HYBRID` | `40d45aeb-174e-4a83-9a42-71ae46065cb4` | **OFF** | manual only | broad Logic read; device enumeration only after all guards + kill switch | guarded boiler read/write | no current load |
| `EM v2 | 05 Watchdog | Core + Publish Freshness v0.3.3 staggered` | `8526109f-5c8d-428e-ac24-85a71c95ac36` | **OFF** | every 5 min +120 s if enabled | broad Logic reads | may start flows | keep disabled during investigation |
| washer/dryer analysis, logging, publication | multiple | **OFF** | event/runtime dependent | legacy appliance analysis/logging | publication path | keep disabled during clean A/B |

## Current active-load conclusion

The current verified active control path is much smaller than the previous v1.1.4 load map implied. The old map incorrectly marked multiple planner, context, evidence and WW shadow flows as ON.

The only currently proven active periodic broad collection reader is Core v0.10.17. Core intentionally acts as the single central snapshot reader. Replacing one `getDevices()` with many targeted device calls is not assumed to be cheaper; downstream consumers should consume Core/Logic snapshots rather than independently enumerate Homey collections.

The active EV cascade has been migrated to targeted Logic reads. Publisher v1.0.9 remains active but is hard-gated: event triggers can occur more often, while actual GitHub publication is bounded to at most once per 15 minutes.

## Re-enable blockers

Before re-enabling these flows, refactor or explicitly accept their load model:

1. `EV Deadline Goal Adapter v0.1`: remove 1-minute broad Logic scan and 1-minute GitHub polling; prefer request/event-driven ingestion or a substantially lower cadence with targeted variables.
2. `Day-Night Normalizer v0.1.1`: do not independently rewrite canonical Core state/Public State on a periodic clock; integrate freshness normalization into Core or a single downstream semantic projection without feedback fan-out.
3. `EMS Settings Sync v0.3`: replace broad Logic snapshot with targeted reads and reduce external polling where possible.
4. `WW Scheduling SHADOW v0.2`: consume the canonical Planner snapshot with targeted reads when revived.
5. `EV Control Status v0.1`: use targeted reads before re-enabling observability.

## Next investigation set

Use the 2026-08-29 Homey inventory only as a name/ID index. Verify by exact flow ID, and prioritize currently enabled EMS flows not yet represented above, especially production context/decision/validation paths and any HomeyScript flow containing `getVariables()`, `getDevices()`, periodic external fetches or programmatic flow starts.
