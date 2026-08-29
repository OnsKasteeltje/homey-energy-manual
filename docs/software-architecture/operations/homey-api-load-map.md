---
component: operations
title: Homey API/Load Map
version: 1.3.2
status: active
architecture_status: implemented
last_verified: 2026-08-29
source:
  - Homey runtime inventory and targeted exact-ID flow reads, 2026-08-29
  - src/homey/MIGRATION_BATCH_2026-08-28.md
  - docs/software-architecture/architecture/05-homey-api-load-governance.md
---

# Homey API/Load Map

This is the canonical runtime-load inventory for the Home Energy Management System. Update this file whenever cadence, polling, broad collection reads, targeted reads, external I/O, device access, actuator access or event fan-out changes.

## Investigation rule

During throttling diagnosis, prefer GitHub/source inspection and exact flow-ID reads. Do not repeatedly enumerate Homey flows. If Homey returns `Too many requests`, stop immediately and do not retry.

## Live Energy attribution rule — 2026-08-29

The regular Live Energy View no longer justifies continuous fingerprint-classification load. A device is split out from `Overige` only when direct power is available or a reliable direct status can be shown. Status-only devices keep power `null`; fingerprint-only devices remain inside `Overige`.

Consequences for Homey load governance:

- appliance fingerprinting is diagnostics-only and defaults OFF;
- washer/dryer P1 transition learning and publication remain OFF for the clean throttling baseline;
- waterkettle/dishwasher/oven fingerprint work is not promoted into continuous Homey runtime detection for Live View;
- existing direct AEG status can still be consumed through canonical Core state without the separate P1 learning pipeline;
- re-enabling a fingerprint flow requires an explicit temporary diagnostic purpose and a Load Map update.

## Verified runtime baseline — 2026-08-29

| Flow | ID | Runtime | Trigger / cadence | Homey load | External / device load | Assessment |
|---|---|---:|---|---|---|---|
| `EM v2 | 00 Core Tick | v0.10.17 (Planner Input low-load)` | `227f8d3b-7551-46dd-837d-1b8c69add824` | **ON** | every 5 min | one `getDevices()` + one `getVariables()` per tick; downstream Logic snapshot writes | no external I/O in Core | **Primary proven structural broad-read baseline**; keep as single-reader until a cheaper device-read pattern is proven |
| `EM v2 | 20 Power Intent | P1 v0.2.3 TARGETED-READ LOW-LOAD` | `19d9d8a6-ec32-4639-be5e-71e9f034d31b` | **ON** | `EM2_Control_WW` change | targeted Logic reads only | none | low-load |
| `EM v2 | 80 Validation | P1 Pre-EV Gate v0.2.1 TARGETED-READ` | `557ed7e8-9efe-4173-bc06-8e629214e172` | **ON** | `EM2_Power_Intent` change | targeted Logic reads only | none | low-load |
| `EM v2 | 60 Adapter | EV Power v0.1.1 TARGETED-READ SHADOW` | `953e9b18-3576-4557-b940-ed4a64eb2516` | **ON** | `EM2_Power_Intent` change | targeted Logic reads only | no device access | low-load |
| `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.1 TARGETED-READ` | `ec5e5d34-8205-4cf0-a661-7bf744feb6e0` | **ON** | `EM2_Power_Intent` change +2 s | targeted Logic reads only | none | low-load |
| `EM v2 | 60 Actuator | EV Power v0.2.2 TARGETED-READ LIVE OWNERSHIP` | `fea23193-a03f-49dd-9780-7e72ee48747d` | **ON** | `EM2_EV_Adapter_Gate` change | targeted Logic reads; LIVE=false has zero device reads/writes | LIVE=true may enumerate Easee path for guarded write/no-op | low in SHADOW; safety-critical in LIVE |
| `EM v2 | 40 Data | Publisher v1.0.10 SCHEDULED LOW-LOAD` | `fe84bc17-72d4-4fbb-9a69-b3d751b0ffcd` | **ON** | every 15 min +2 s; manual start retained | five targeted Logic reads | hard minimum 15 min between GitHub publishes | **low-fanout publication path**; no longer triggered by each `EM2_Public_State` change, reducing starts from up to ~12/hour to ~4/hour without changing control/actuation |
| `EM v2 | 45 Planner | 24h Energy Plan v0.4.4 SHADOW LOW-LOAD` | `27617767-0a64-43a3-9bcb-e34b0dd6a5c0` | **OFF** | every 15 min +45 s if enabled | one targeted Planner Input read + one targeted snapshot write | Open-Meteo when enabled | no current load |
| `EM v2 | 46 Publish | Planner Shadow v0.4 event-driven LOW-LOAD` | `5b3b80fe-96d1-406d-91ef-cf75a4e65d45` | **OFF** | planner snapshot change +2 s if enabled | four targeted Logic reads | GitHub PUT per new plan key when enabled | no current load |
| `EM v2 | 30 Context | Contract Price Adapter v0.8` | `b1c495cb-6ccd-4fb8-b4bf-365845dbb6e7` | **OFF** | every 15 min if enabled | broad Logic reads; dynamic branch can enumerate PBTH device | PBTH in dynamic mode | no current load; refactor before re-enable |
| `EM v2 | 30 Context | Price + PV v0.6.1 SHADOW` | `d5b79dfe-2cff-4be6-9f93-93bb453dd9fa` | **OFF** | every 15 min if enabled | `getVariables()` + `getDevices()` | PBTH inter-app API | no current load; broad-read candidate |
| `EM v2 | 30 Context | Price + PV v0.6 [FAILED-DIRECT-API]` | `0342eff4-6c3a-4905-9142-4b007e4acf11` | **OFF** | every 15 min if enabled | `getVariables()` + `getDevices()` plus separate compatibility-heartbeat `getVariables()` | direct PBTH API attempt + legacy price/PV cards | failed implementation; do not re-enable |
| `EM v2 | 30 Context | Price + PV v0.5.1 [ROLLBACK ACTIVE]` | `b39801dc-640c-4327-b477-baa2976f2bdf` | **OFF** | every 15 min if enabled | broad `getVariables()` + `getDevices()` plus separate heartbeat `getVariables()` | PBTH card/API path + legacy price/PV cards | name is stale/misleading; runtime is OFF |
| `EM v2 | 30 Context | PBTH API Price Adapter v0.1 SHADOW` | `5afbf213-441b-4fb8-b2bf-2cc134c72ada` | **OFF** | every 15 min if enabled | two broad `getVariables()` scans per run | PBTH inter-app `/dap-prices` | no current load; refactor before re-enable |
| `EM v2 | 40 Decision | Contract-aware v0.2` | `11a78b36-a8a5-4988-915c-53b54351737e` | **OFF** | every 5 min if enabled | one broad `getVariables()` + candidate Logic writes | none | no current load |
| `EM v2 | 40 Decision | Contract-aware v0.1 [ROLLBACK]` | `56b87a5c-645c-4a95-9744-880c4d0353bd` | **OFF** | every 5 min if enabled | one broad `getVariables()` + candidate Logic writes | none | retired rollback; keep disabled |
| `EM v2 | 15 State | Warm Water Observer v0.2` | `957a85b5-a4ff-4fe2-bc6b-2e56e60387ea` | **OFF** | manual/programmatic if enabled | one `getVariables()` | programmatically starts old WW Control v0.3 | no current load; legacy coupling |
| `EM v2 | 10 Input | EV Deadline Goal Adapter v0.1` | `445cb82c-5e1f-43c3-b2cf-f2d78fec6e16` | **OFF** | every 1 min if enabled | one `getVariables()` plus multiple Logic writes | GitHub API/raw fetch every run | **high-risk if re-enabled: up to 60 broad Logic reads + 60 external fetches/hour** |
| `EM v2 | 05 Config | EMS Settings Sync v0.3 low-load` | `9193b3ae-1e3d-4b52-aa95-60aff099e68a` | **OFF** | every 5 min if enabled | one `getVariables()`; strict no-op after matching request | GitHub API/raw fetch every run | no current load; targeted/event-driven redesign preferred |
| `EM v2 | 06 Freshness | Day-Night Normalizer v0.1.1` | `a41079f7-2287-4ec0-9e9b-27619e93ba35` | **OFF** | every 5 min +30 s if enabled | one `getVariables()`; may rewrite `EM2_State` and `EM2_Public_State` | none | no current load; **fan-out amplifier if re-enabled** |
| `EM v2 | 01 Quooker Detector | v0.3 SWITCH-AUTH + P1 HEATING` | `04a713a5-105e-439a-a93a-441fb2ca50b4` | **OFF** | every 1 min if enabled | one broad `getVariables()` + one targeted Cooker read; targeted P1 read only after heartbeat | no external I/O | no current load; remove 1-min broad scan before continuous use |
| `EM v2 | 20 Power Intent | P1 v0.1 SHADOW` | `596e9d60-ad2d-4249-8880-88293aa2cde4` | **OFF** | `EM2_Public_State` change if enabled | one broad `getVariables()` | none | rollback baseline; keep disabled |
| `EM v2 | 60 Adapter | Actuator Commands v0.2 SHADOW` | `9acfe4d8-8542-483a-8201-595c32543e70` | **OFF** | `EM2_Power_Intent` change if enabled | one broad `getVariables()` | none | no current load; generic adapter superseded by specific adapters |
| `EM v2 | 60 Adapter | WW Power v0.1 SHADOW` | `472d0355-3bb9-4a42-be43-114b57822136` | **OFF** | `EM2_Power_Intent` change if enabled | one broad `getVariables()` | none | no current load |
| `EM v2 | 80 Validation | WW Power Adapter Gate v0.1` | `39c39cc5-12bb-4494-ba45-bad47a656696` | **OFF** | `EM2_Power_Intent` change +2 s if enabled | one broad `getVariables()` + multiple Gate counter/status writes | none | no current load |
| `EM v2 | 70 Planner | WW Scheduling SHADOW v0.2` | `1d822642-87e8-4b0f-870e-5f2e7eef9372` | **OFF** | programmatic if enabled | one `getVariables()` | none | no current load; legacy broad-read |
| `[RETIRED DUPLICATE] EM v2 | 70 Planner | WW Scheduling SHADOW v0.1` | `2248f9ae-159b-474e-8680-2e947709e664` | **OFF** | programmatic if enabled | one `getVariables()` | none | retired duplicate; keep disabled/remove later |
| `EM v2 | 50 Decision | WW Post-Goal Opportunity v0.4 SHADOW` | `5538f1c9-9a21-4328-9896-942952f5c55f` | **OFF** | every 15 min if enabled | one `getVariables()` | none | no current load |
| `EM v2 | 50 Decision | WW Seasonal Source Advisor v0.3 SHADOW idempotent` | `543664be-d07a-4099-92d1-07878b73215d` | **OFF** | daily 20:30 if enabled | one broad Logic snapshot; extra reads only in notification paths | three GitHub GETs | no current load |
| `EM v2 | 60 Control | Warm Water Actuator v0.6` | `2b9284f6-1d41-453e-a8f9-10c634f56fe5` | **OFF** | every 5 min if enabled | one broad `getVariables()` | none | obsolete shadow control; keep disabled |
| `EM v2 | 60 Control | Warm Water Actuator v0.8 HYBRID` | `40d45aeb-174e-4a83-9a42-71ae46065cb4` | **OFF** | manual only | broad Logic read; device enumeration only after all guards + kill switch | guarded boiler read/write | no current load |
| `EM v2 | 70 History | Control Audit v0.4 low-load` | `df295b26-9a47-497a-87c7-ccfd32323db1` | **OFF** | event-driven if enabled | one `getVariables()` per event | bounded GitHub publish | no current load |
| `EM v2 | 70 History | Day Series v0.6 LOCAL SAMPLER` | `14027232-905e-4b8b-828d-5b44b8f6692e` | **OFF / isolation** | implementation under redesign | historically broad Logic/device reads + frequent GitHub I/O | local sampler / publisher split in progress | keep isolated during throttle investigation |
| `EM v2 | 76 Publish | Day Series v0.1 low-frequency` | `de129562-c4a6-4d2d-8898-ab89d6628b94` | **OFF** | every 30 min if enabled | one broad `getVariables()` | at most GitHub GET + PUT per changed publication | no current load; keep OFF until local sampler passes smoke |
| `EM v2 | 72 History | Immutable Day Archive v0.1` | `322bcfe6-1ec4-46d4-a840-d13009d9c9c9` | **OFF** | hourly if enabled | one `getVariables()` | raw series read + GitHub archive/index I/O | no current load |
| `EM v2 | 76 Evidence | BC Planner Intent Recorder v0.4 local-first` | `9aba3344-b8b4-423f-9132-b606990b9ffe` | **OFF** | every 15 min if enabled | one `getVariables()` | GitHub mainly on rollover/archive | no current load |
| `EM v2 | 80 Validation | Contract History v0.2 idempotent` | `92c11297-665a-4769-8594-4c26518a81e7` | **OFF** | every 15 min if enabled | one broad `getVariables()` + status write | GitHub GET + PUT per run | no current load |
| `EM v2 | 90 Validation | Contract Shadow Snapshot v0.1` | `e8f0f341-2f86-4893-ab9c-ed6c68f7457f` | **OFF** | manual only | one broad `getVariables()` | GitHub GET + PUT | no current load |
| `EM v2 | 80 Validation | WW Adapter Gate Readback` | `17724882-d987-4990-b828-db2ca976b2a9` | **OFF** | manual only | broad `getVariables()`; creates/deletes temporary Logic markers | none | diagnostic only |
| `EM v2 | 80 Validation | EV Adapter Gate Readback` | `23abe95a-6fd0-44de-9966-faf6ec9fc5f4` | **OFF** | manual only | broad `getVariables()`; creates/deletes temporary Logic markers | none | diagnostic only |
| `EM v2 | 80 Validation | P1 Gate Readback` | `7b4e9100-d23d-4675-839f-d456be192db3` | **OFF** | manual only | broad `getVariables()`; creates/deletes temporary Logic markers | none | diagnostic only |
| `EM v2 | 80 Validation | Tesla Action Log v0.1` | `21a46e5b-7293-4484-964a-0728f4a8d632` | **OFF** | every 1 min if enabled | one broad `getVariables()` + Logic history writes | none | **high recurring Logic-load if re-enabled; diagnostics only** |
| `EM v2 | 90 Validation | WW BOILER_ON v0.1` | `07ad062e-0959-4557-a9d8-ea730cb37174` | **OFF** | manual only | multiple broad Logic scans in validation/cleanup path | may temporarily enable/start WW actuator | controlled validation only |
| `EM v2 | 81 Observability | EV Control Status v0.1` | `f6edba38-ddf1-45e5-890e-c183aa2055d5` | **OFF** | Gate / actuator change if enabled | one `getVariables()` | GitHub status publish | no current load; migrate before re-enable |
| `EM v2 | 05 Watchdog | Core + Publish Freshness v0.3.3 staggered` | `8526109f-5c8d-428e-ac24-85a71c95ac36` | **OFF** | every 5 min +120 s if enabled | broad Logic reads | may start flows | keep disabled during investigation |
| `Energie | Wasmachine & Droger analyse | v1.4.2` | `7f8217ce-1994-46f8-92fb-455b11b046fe` | **OFF** | AEG state events + 5-min fallback if enabled | event path performs `getDevices()` + `getVariables()`; fallback reads Logic snapshot | Logic evidence/model writes | diagnostics-only |
| `Energie | Wasmachine & Droger publicatie | v1.1.1` | `fa09ad30-e9fc-4e78-a50c-38635a91b294` | **OFF** | every 5 min if enabled | one `getVariables()` | GitHub GET + PUT | diagnostics-only |
| washer/dryer logging | multiple | **OFF** | event/runtime dependent | legacy appliance logging | possible publication/history path | keep disabled; diagnostics-only |

## Current active-load conclusion

The verified active EMS control path is now substantially smaller than earlier load maps suggested. Exact runtime checks show the old planner, context, WW, history, validation and observability candidates above are OFF.

The only currently proven active periodic broad collection reader is Core v0.10.17. Core intentionally acts as the single central snapshot reader. Replacing its single `getDevices()` with many targeted device calls is not assumed to be cheaper; downstream consumers should consume Core/Logic snapshots rather than independently enumerate Homey collections.

The active EV cascade has been migrated to targeted Logic reads. Publisher v1.0.10 is now scheduled every 15 minutes instead of being triggered by every `EM2_Public_State` change. It still performs five targeted Logic reads and retains the 15-minute hard publication gate. This reduces Publisher wake-ups from up to roughly 12 per hour to roughly 4 per hour while leaving the control and actuator chain unchanged.

No hidden active legacy EMS poller has been found in the exact-ID runtime review so far. The remaining investigation target is therefore the truly active flowset plus any TEMP/DONE/ONE-SHOT artifacts that may unexpectedly still be enabled.

## Re-enable blockers

Before re-enabling these flows, refactor or explicitly accept their load model:

1. `EV Deadline Goal Adapter v0.1`: remove 1-minute broad Logic scan and 1-minute GitHub polling.
2. `Tesla Action Log v0.1`: remove the 1-minute broad Logic scan; use event-driven or targeted reads for bounded diagnostics.
3. `Quooker Detector v0.3`: remove the 1-minute broad Logic scan; retain targeted Cooker/P1 reads only where necessary.
4. `PBTH API Price Adapter v0.1`: replace two full Logic scans per quarter-hour with targeted inputs if revived.
5. `Price + PV v0.6 [FAILED-DIRECT-API]` and `Price + PV v0.5.1 [ROLLBACK ACTIVE]`: do not revive as-is; both combine multiple legacy context paths and broad reads.
6. `Day-Night Normalizer v0.1.1`: do not independently rewrite canonical Core/Public State on a periodic clock.
7. `EMS Settings Sync v0.3`: replace broad Logic snapshot with targeted reads and reduce external polling.
8. `WW Scheduling SHADOW v0.2`, generic `Actuator Commands v0.2`, WW Power Adapter/Gate and EV Control Status: migrate to targeted reads before any production revival.
9. Fingerprint/appliance-analysis flows: only re-enable for a bounded diagnostic experiment; never because the regular Live View requires inferred wattage.

## Next investigation set

The 2026-08-29 Homey inventory is now only a name/ID index. Do not run another full flow enumeration unless the inventory is known to have changed. Next, inspect the remaining `TEMP`, `[DONE]`, `[ONE-SHOT]`, `[FAILED-*]` and explicitly replaced flows by exact ID, mark cleanup candidates, and verify that none is unexpectedly enabled. If any Homey call returns `Too many requests`, stop immediately and do not retry.