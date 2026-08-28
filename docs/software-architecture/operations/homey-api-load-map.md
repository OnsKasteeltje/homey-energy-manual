---
component: operations
title: Homey API/Load Map
version: 1.1.1
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

| Flow | ID | State | Trigger / cadence | Main Homey load | External load | Fan-out / notes | Class | Lifecycle |
|---|---|---|---|---|---|---|---|---|
| `EM v2 | 00 Core Tick | v0.10.13 (EV electrical context)` | `227f8d3b-7551-46dd-837d-1b8c69add824` | ON | every 5 min | `getDevices()` + `getVariables()` + multiple Logic writes | none in current Core path | updates `EM2_Public_State`, which starts Power Intent cascade | HIGH | PRODUCTION |
| `EM v2 | 70 History | Day Series v0.5.4` | `14027232-905e-4b8b-828d-5b44b8f6692e` | **OFF for isolation test** | every 5 min when enabled | `getVariables()` + targeted P1 `getDevice()`; `getDevices()` for PV snapshot in some paths | GitHub GET/PUT every run for `energy-day-v2.json`; more at rollover | primary current throttling suspect; isolated on 2026-08-28 | **CRITICAL** | EVIDENCE / TELEMETRY |
| `EM v2 | 20 Power Intent | P1 v0.2.1 SHADOW` | `19d9d8a6-ec32-4639-be5e-71e9f034d31b` | ON | `EM2_Public_State` changed | `getVariables()` + one output Logic write when revision changes | none | triggers P1 Gate, EV Adapter and EV Adapter Gate | MEDIUM | SHADOW |
| `EM v2 | 80 Validation | P1 Pre-EV Gate v0.2` | `557ed7e8-9efe-4173-bc06-8e629214e172` | ON | `EM2_Power_Intent` changed | one `getVariables()` + at most one compact `EM2_P1_PreEV_Gate` JSON write per semantic revision | none | runtime-health mode; typed campaign mirrors/counters removed; identical semantic retrigger is no-write | LOW/MEDIUM | VALIDATION / RUNTIME HEALTH |
| `EM v2 | 60 Adapter | EV Power v0.1 SHADOW` | `953e9b18-3576-4557-b940-ed4a64eb2516` | ON | `EM2_Power_Intent` changed | `getVariables()` + adapter output Logic write | none | no device read/write; idempotent by revision/schema/target | MEDIUM | SHADOW |
| `EM v2 | 80 Validation | EV Power Adapter Gate v0.2` | `ec5e5d34-8205-4cf0-a661-7bf744feb6e0` | ON | `EM2_Power_Intent` changed + 2 s | one `getVariables()` + at most one compact `EM2_EV_Adapter_Gate` JSON write per semantic revision | none | safety schema + `finalStatus` preserved for actuator; typed mirror/campaign outputs removed; identical semantic retrigger is no-write | LOW/MEDIUM | VALIDATION / RUNTIME HEALTH |
| `EM v2 | 30 Context | Contract Price Adapter v0.8` | `b1c495cb-6ccd-4fb8-b4bf-365845dbb6e7` | ON | every 15 min + manual | FIXED: two Logic enumerations across condition/classifier, **0 `getDevices()`**; DYNAMIC: PBTH device enumeration only in dynamic branch | PBTH only for DYNAMIC | FIXED path optimized 2026-08-28; removes 4 full device enumerations/hour versus previous implementation | MEDIUM | PRODUCTION CONTEXT |
| `EM v2 | 45 Planner | 24h Energy Plan v0.4.3 SHADOW` | `27617767-0a64-43a3-9bcb-e34b0dd6a5c0` | ON | every 15 min + 45 s + manual | `getVariables()`; 96-slot plan generation | Open-Meteo fetch each run | CPU/data-heavy but no device enumeration; about 4 Logic enumerations + 4 weather fetches/hour | MEDIUM/HIGH | SHADOW |
| `EM v2 | 46 Publish | Planner Shadow v0.3 event-driven` | `5b3b80fe-96d1-406d-91ef-cf75a4e65d45` | ON | `EM2_Energy_Plan_24h` changed + 2 s; manual Start remains | `getVariables()`; one small local publish-cache Logic write after successful publish | steady-state **1 GitHub PUT per new plan**; GET only on cache miss/first run or conflict recovery | 15-min publisher cron removed; duplicate `plan.generatedAt` skipped; approximately **8 -> 4 GitHub HTTP calls/hour** at normal 15-min planner cadence | LOW/MEDIUM | SHADOW / OBSERVABILITY |
| `EM v2 | 76 Evidence | BC Planner Intent Recorder v0.4 local-first` | `9aba3344-b8b4-423f-9132-b606990b9ffe` | ON | every 15 min | `getVariables()` + local buffer/status writes; consumes `EM2_Energy_Plan_24h` directly | no rolling Planner Shadow read-back; GitHub only on immutable/day-rollover archive path | GitHub-as-message-bus anti-pattern removed; about 4 rolling GitHub GETs/hour eliminated | LOW/MEDIUM | EVIDENCE |
| `EM v2 | 50 Decision | WW Post-Goal Opportunity v0.4 SHADOW` | `5538f1c9-9a21-4328-9896-942952f5c55f` | ON | every 15 min + manual | `getVariables()` + up to about 7 Logic writes | none | derived from `EM2_State`, WW state and contract context; no devices/network | MEDIUM | SHADOW |
| `EM v2 | 70 History | Control Audit v0.3 idempotent` | `df295b26-9a47-497a-87c7-ccfd32323db1` | ON | **event-driven on `EM2_Control_WW` changed + 2 s settle** | one `getVariables()` per event; local history write only on semantic change; second Logic enumeration only after successful GitHub publish | GitHub publication only after semantic change and max 1x/30 min | fixed 5-min polling removed, eliminating about 12 scheduled audit runs/hour | LOW/MEDIUM | EVIDENCE / AUDIT |
| `EM v2 | 50 Decision | WW Seasonal Source Advisor v0.3 SHADOW idempotent` | `543664be-d07a-4099-92d1-07878b73215d` | ON | daily 20:30 + manual | one `getVariables()` | 3 parallel GitHub GETs | low average load, moderate daily burst | LOW/MEDIUM | SHADOW |
| `EM v2 | 05 Watchdog | Core + Publish Freshness v0.3.3 staggered` | `8526109f-5c8d-428e-ac24-85a71c95ac36` | OFF | every 5 min + 120 s when enabled | Logic-only `getVariables()`; possible flow starts | none directly | inspect before re-enable; old Core Publish_Due behavior could amplify publication | LOW/MEDIUM | DISABLED |
| `EM v2 | 40 Data | Publisher` | `fe84bc17-72d4-4fbb-9a69-b3d751b0ffcd` | OFF | manual/startable | flow start + delay + script | downstream publication | currently disabled | MEDIUM | DISABLED |
| `EM v2 | 72 History | Immutable Day Archive v0.1` | `322bcfe6-1ec4-46d4-a840-d13009d9c9c9` | OFF | every 60 min when enabled | `getVariables()` + status write | raw GitHub read + GitHub reads/writes for archive/index | disabled during current investigation | LOW/MEDIUM | DISABLED |
| `Energie | Wasmachine & Droger analyse | v1.4.2` | `7f8217ce-1994-46d8-92fb-455b11b046fe` | OFF during clean A/B | event/runtime dependent | appliance analysis | n/a | kept off during throttling isolation | TBD | DISABLED / INVESTIGATION |
| `Energie | Wasmachine & Droger logging | v1.0` | `b8edcb98-621a-4abf-ab93-7306d8f06b79` | OFF during clean A/B | event/runtime dependent | logging | n/a | kept off during throttling isolation | TBD | DISABLED / INVESTIGATION |
| `Energie | Wasmachine & Droger publicatie | v1.1.1` | `fa09ad30-e9fc-4e78-a50c-38635a91b294` | OFF during clean A/B | event/runtime dependent | publication | n/a | kept off during throttling isolation | TBD | DISABLED / INVESTIGATION |

## Known cascades and burst groups

### Five-minute Power Intent cascade

```text
Core Tick (5 min)
  -> EM2_Public_State changes
      -> Power Intent
          -> EM2_Power_Intent changes
              -> P1 Pre-EV Gate
              -> EV Power Adapter
              -> EV Adapter Gate (+2 s)
```

The load impact of this path is the sum of the whole cascade. It must not be assessed as one Core operation. At nominal cadence this path accounts for about 12 full Core device enumerations/hour and, downstream, about 48 full Logic enumerations/hour across Power Intent + P1 Gate + EV Adapter + EV Gate. Gate write amplification has been reduced from many typed mirrors per revision to at most one compact runtime-health JSON per Gate per semantic revision.

### Quarter-hour cluster

```text
t+0    Contract Price Adapter
       BC Planner Intent Recorder v0.4 local-first
       WW Post-Goal Opportunity

t+45s  24h Planner

plan-change +2s
       Planner Shadow Publisher v0.3
```

The Contract Price Adapter no longer performs a device enumeration in FIXED mode. BC Planner Intent Recorder no longer reads Planner Shadow back from GitHub. Planner Shadow Publisher no longer has an independent quarter-hour clock; it follows actual planner output changes.

## Current investigation observations

- Homey returned clean read-only responses during the reduced-load baseline; a clean probe confirms reachability at that moment only and does not by itself prove sustained stability.
- Day Series remains isolated because it combined a 5-minute cadence, direct device access and GitHub publication in one flow.
- Publisher, Watchdog, Immutable Day Archive and washer/dryer analysis/logging/publication remain disabled during the clean throttling isolation.
- Contract Price Adapter FIXED path was corrected on 2026-08-28 so `getDevices()` is not called in FIXED mode. This removes 4 full device enumerations/hour at its 15-minute cadence.
- P1 Pre-EV Gate and EV Power Adapter Gate were converted from validation-campaign mirror engines to compact runtime-health Gates. Both retain their safety schemas/checks while reducing Logic write amplification from roughly 34 mirror writes per Power Intent revision across both Gates to at most 2 compact JSON writes per semantic revision.
- Control Audit was converted from fixed 5-minute polling to event-driven execution on `EM2_Control_WW`, with a 2-second settle. Fixed load of about 12 audit runs/hour is removed; GitHub publication is limited to semantic changes and at most once per 30 minutes.
- BC Planner Intent Recorder was changed to local-first consumption of `EM2_Energy_Plan_24h`; the rolling GitHub read-back path was removed, eliminating about 4 GitHub GETs/hour.
- Planner Shadow Publisher was changed from v0.2 timed publication to v0.3 event-driven publication. Normal external load falls from one GitHub GET + one PUT every 15 minutes (~8 calls/hour) to one PUT per changed planner output (~4 calls/hour), with GET reserved for cache initialization or conflict recovery.

## Required redesign candidates

1. Split Day Series into **local sampling** and **external publication** responsibilities before re-enabling it.
2. Reuse `EM2_State` wherever authoritative telemetry already exists; retain direct device reads only when explicitly needed as an independent measurement checksum.
3. Reduce or eliminate redundant external publication paths; GitHub is an output/archive boundary, not an internal message bus.
4. Resolve the duplicate enabled `WW Scheduling SHADOW v0.1` flows after caller/dependency analysis.
5. Stagger or remove remaining independent clocks where event-driven chaining already establishes correct ordering.
6. Review Core Tick Logic-write fan-out after a clean multi-cycle stability baseline, because Core remains the principal unavoidable 5-minute device reader.
7. Before a positive EV LIVE smoke, separately inspect the actuator/Gate revision-coherency path so load hardening and safety hardening remain distinct concerns.

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
