# Homey ↔ GitHub runtime sync baseline — 2026-08-30

This file records the current critical EMS runtime observed directly on Homey and the version that GitHub must treat as the active production baseline. It is intended to prevent documentation/source drift.

## Verified directly on Homey

All flows below were read from Homey on 2026-08-30 and were `enabled: true` and `broken: false` at the time of the check.

| Layer | Homey flow ID | Active runtime |
|---|---|---|
| Core | `227f8d3b-7551-46dd-837d-1b8c69add824` | `EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads)` |
| Power Intent | `19d9d8a6-ec32-4639-be5e-71e9f034d31b` | `EM v2 | 20 Power Intent | P1 v0.2.4 DUAL-SEMANTIC LOW-LOAD` |
| WW state | `957a85b5-a4ff-4fe2-bc6b-2e56e60387ea` | `EM v2 | 15 State | Warm Water Observer v0.2` |
| WW adapter | `472d0355-3bb9-4a42-be43-114b57822136` | `EM v2 | 60 Adapter | WW Power v0.2 TARGETED-READ SHADOW` |
| WW gate | `39c39cc5-12bb-4494-ba45-bad47a656696` | `EM v2 | 80 Validation | WW Power Adapter Gate v0.2 TARGETED-READ` |
| WW actuator | `40d45aeb-174e-4a83-9a42-71ae46065cb4` | `EM v2 | 60 Control | Warm Water Actuator v0.9 TARGETED-READ LIVE` |
| EV goal input | `445cb82c-5e1f-43c3-b2cf-f2d78fec6e16` | `EM v2 | 10 Input | EV Deadline Goal Adapter v0.1` |
| EV adapter | `953e9b18-3576-4557-b940-ed4a64eb2516` | `EM v2 | 60 Adapter | EV Power v0.1.1 TARGETED-READ SHADOW` |
| EV gate | `ec5e5d34-8205-4cf0-a661-7bf744feb6e0` | `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.1 TARGETED-READ` |
| EV actuator | `fea23193-a03f-49dd-9780-7e72ee48747d` | `EM v2 | 60 Actuator | EV Power v0.2.2 TARGETED-READ LIVE OWNERSHIP` |

## Planner baseline

The source-managed planner baseline is:

- `EM v2 | 45 Planner | 24h Energy Plan v0.4.7 SHADOW LOW-LOAD`
- flow ID `27617767-0a64-43a3-9bcb-e34b0dd6a5c0`
- source: `src/homey/planner/energy-plan-24h-v0.4.7.js`
- day-boundary-aware WW planning is required.

The Planner Shadow publisher remains:

- `EM v2 | 46 Publish | Planner Shadow v0.4 event-driven LOW-LOAD`
- flow ID `5b3b80fe-96d1-406d-91ef-cf75a4e65d45`

## Source-of-truth rule

1. The exact Homey flow ID plus active version/name above defines the runtime baseline.
2. GitHub documentation and implementation artifacts must not name an older version as the active production baseline.
3. A newer experimental/SHADOW design may exist in GitHub, but must be clearly marked as not active until deployed and smoke-tested.
4. Any Homey runtime change must be captured in GitHub in the same change cycle.
5. Any GitHub runtime promotion must be followed by a targeted Homey smoke test before it becomes the active baseline.

## Safety state

The existence/enabled state of a LIVE-capable actuator flow does not by itself mean physical writes are armed. Runtime kill/LIVE gates remain authoritative. The EV actuator has a separate `EM2_EV_Actuator_Live_Enabled` guard. The WW actuator remains guarded by mode, schema, revision, gate and freshness checks.

## Audit note

The previous migration inventory dated 2026-08-28 contained superseded runtime names such as Core v0.10.17, Power Intent v0.2.2, Planner v0.4.4, EV Power Adapter v0.1, EV actuator v0.2, WW Power Adapter v0.1 and WW actuator v0.8. Those entries must no longer be interpreted as the current active baseline.
