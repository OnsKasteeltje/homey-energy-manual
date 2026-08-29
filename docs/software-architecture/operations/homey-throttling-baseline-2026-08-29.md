---
component: operations
title: Homey Throttling Recovery Baseline 2026-08-29
version: 1.1.0
status: active
architecture_status: implemented
last_verified: 2026-08-29
---

# Homey Throttling Recovery Baseline — 2026-08-29

## Purpose

This document freezes the clean runtime baseline used to recover from the August 2026 Homey throttling incident. It is not a repository rollback. It is a functional runtime isolation baseline that preserves current source, evidence and documentation while restricting Homey to the smallest proven control/publication set.

The canonical per-flow load inventory remains `docs/software-architecture/operations/homey-api-load-map.md`.

## Recovery evidence

The recovery sequence produced three consecutive successful read-only Homey observations after the previous `Too many requests` condition:

1. device inventory read succeeded;
2. full flow inventory read succeeded;
3. follow-up device inventory read succeeded after the isolated baseline had continued to run.

No Homey writes, flow starts or actuator smokes were required to obtain this evidence.

## KEEP baseline

The following EMS flows form the current keep-set for throttling recovery:

| Flow | Runtime role | Baseline decision |
|---|---|---|
| `EM v2 | 00 Core Tick | v0.10.17 (Planner Input low-load)` | canonical device/logic reader and state producer | KEEP ON |
| `EM v2 | 20 Power Intent | P1 v0.2.3 TARGETED-READ LOW-LOAD` | power-intent generation | KEEP ON |
| `EM v2 | 80 Validation | P1 Pre-EV Gate v0.2.1 TARGETED-READ` | EV pre-gate | KEEP ON |
| `EM v2 | 60 Adapter | EV Power v0.1.1 TARGETED-READ SHADOW` | EV W-to-command adapter | KEEP ON |
| `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.1 TARGETED-READ` | EV adapter validation | KEEP ON |
| `EM v2 | 60 Actuator | EV Power v0.2.2 TARGETED-READ LIVE OWNERSHIP` | guarded actuator ownership path | KEEP ON; respect runtime LIVE guard |
| `EM v2 | 40 Data | Publisher v1.0.10 SCHEDULED LOW-LOAD` | website state publication | KEEP ON at 15-minute cadence |

## Isolation set

During the clean baseline, keep the following classes OFF unless a specific staged reintroduction step explicitly promotes them:

- Planner v0.4.4 and Planner Shadow publication;
- Contract Price Adapter and all Price + PV experimental/rollback variants;
- Day Series sampler/publication, Immutable Day Archive and other history/evidence publishers;
- BC Planner Intent Recorder and contract validation/history publishers;
- Quooker detector and P1 heartbeat diagnostics;
- washer/dryer P1 analysis, logging and publication;
- TEMP, probe, regression, readback and smoke flows;
- legacy/rollback Power Intent, generic adapter and WW planner/control variants;
- any recurring flow that performs broad `getVariables()`/`getDevices()` reads or frequent external GitHub/API I/O without an explicit load-budget entry.

## Baseline rules

1. Homey is the real-time control plane, not the analytics/publication plane.
2. Core remains the single deliberate broad-reader until a cheaper device-read model is proven.
3. New or re-enabled recurring flows require an entry in the Homey API/Load Map before activation.
4. Event fan-out from timestamp-only or semantically unchanged state is not accepted as a trigger justification.
5. Publication and analytics must be bounded by cadence and/or semantic-change suppression.
6. A `Too many requests` response immediately stops diagnostic probing; no retry loop is allowed.
7. Reintroduction follows one change at a time with a soak period before the next promotion.

## Fan-out verification — step 4

Step 4 was verified from source plus exact-ID read-only Homey inspection, without changing the active runtime.

### Control fan-out

The active `EM v2 | 20 Power Intent | P1 v0.2.3 TARGETED-READ LOW-LOAD` is triggered by semantic `EM2_Control_WW` changes, not by `EM2_Public_State`. It performs targeted Logic reads and suppresses duplicate output for an already-processed source revision. Thus freshness-only public-state changes do not wake the Power Intent control cascade.

### Publication fan-out

The active `EM v2 | 40 Data | Publisher v1.0.10 SCHEDULED LOW-LOAD` is scheduled every 15 minutes, uses targeted Logic reads and enforces a hard 15-minute minimum publication interval. It is no longer started by every `EM2_Public_State` change.

### Boundary

The two known structural fan-out amplifiers in the KEEP baseline are therefore removed. Remaining fan-out candidates are contained in the OFF isolation set and cannot be promoted until step 5 gives them an explicit load budget and step 6 validates them one at a time.

## Recovery-plan status

| Step | Status | Evidence |
|---|---|---|
| 1. Stabilize | PASS | Homey recovered from throttling and accepted repeated read-only probes |
| 2. Isolate RC/control baseline | PASS | current keep-set runs while high-load/post-RC paths remain isolated |
| 3. API/load map | PASS | canonical Load Map v1.3.2 plus this frozen recovery baseline |
| 4. Remove fan-out | PASS | Power Intent uses semantic control trigger; Publisher is bounded to 15-minute schedule |
| 5. Introduce load budget | NEXT | define quantitative recurring-read, external-I/O and fan-out limits |
| 6. Staged rebuild + soak | OPEN | re-enable only after step 5 establishes acceptance criteria |

## Next safe action

Proceed with step 5 entirely from GitHub/source first. Define quantitative limits for broad collection reads, targeted reads, external I/O, recurring cadence and event fan-out. Do not enable any isolated flow merely to measure its cost; estimate from source and admit it only after the budget is explicit.
