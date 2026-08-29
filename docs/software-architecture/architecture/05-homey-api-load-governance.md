---
component: architecture
title: Homey API and Runtime Load Governance
version: 1.1.0
status: active
architecture_status: implemented
last_verified: 2026-08-29
source:
  - docs/codekwaliteit.md
  - docs/software-architecture/operations/homey-api-load-map.md
  - docs/software-architecture/operations/homey-throttling-baseline-2026-08-29.md
---

# Homey API and Runtime Load Governance

## Purpose

Homey runtime load is an explicit architecture constraint. A flow that is functionally correct is not production-ready when its incremental Homey API/runtime load has not been quantified.

The system therefore maintains a version-controlled **Homey API/Load Map**. The map is the canonical inventory for periodic polling, event-driven fan-out, Logic-variable reads/writes, device reads/writes, Flow starts, Insights access and external network traffic initiated from Homey.

## Hard architecture rule

> No Homey flow may be promoted to production unless its incremental runtime load is quantified in the Homey API/Load Map and remains within the agreed Homey load budget. Any change in trigger frequency, polling, Logic-variable fan-out, network publication, device access or actuator access requires the Load Map to be updated in the same change.

## Production load budget — v1.0

These limits are conservative recovery-era guardrails. They are architecture acceptance limits, not claims about Athom's undocumented internal rate-limit implementation.

### Broad collection reads

- `Homey.devices.getDevices()`: **maximum 12/hour system-wide recurring**, owned by the canonical Core 5-minute reader.
- `Homey.logic.getVariables()`: **maximum 12/hour system-wide recurring broad scans** in the normal production control plane.
- No second recurring broad device reader is permitted while Core owns the 5-minute telemetry snapshot.
- A flow requiring a broad collection read outside Core is **not eligible for re-enable** until it is refactored or explicitly approved as a temporary diagnostic with a bounded lifetime.

### Targeted reads

- Downstream control components use exact-ID/targeted Logic or device reads.
- A single flow should normally require **no more than 5 targeted reads/run**.
- The normal control cascade should remain **at or below 25 targeted reads per semantic control event** across Power Intent, gates, adapters and actuator validation combined.
- Targeted reads caused only by timestamp/freshness changes are prohibited.

### Cadence

- Canonical telemetry sampling: **not faster than every 5 minutes** unless a safety-critical requirement is documented and separately budgeted.
- Planner/context computation: **normally not faster than every 15 minutes**.
- Website/publication work: **normally not faster than every 15 minutes** and semantic/idempotent suppression is required where possible.
- History/evidence/archive work: **30 minutes or slower** by default; daily/hourly aggregation is preferred over high-frequency external publication.
- Recurring 1-minute diagnostic/analytics flows are prohibited in the production baseline.

### External I/O

- External GitHub/cloud I/O is never used as a 1-minute control dependency.
- A normal production publisher may perform **at most 4 publication attempts/hour** per publication domain.
- External writes must be idempotent/change-suppressed; unchanged payloads do not justify a PUT/write.
- Control correctness must not depend on successful GitHub publication.

### Fan-out and writes

- One semantic control event may start **at most one instance of each downstream control stage**.
- Timestamp, age, heartbeat, `generatedAt`, publication counters and other freshness-only fields must not trigger the control cascade.
- A producer may have **at most one direct production control consumer per control responsibility** unless an explicit fan-out review documents the additional consumers.
- Logic/status mirror writes are suppressed when the normalized value is unchanged, except for explicitly budgeted freshness heartbeats.

### Burst reserve

- Keep at least **50% operational headroom** relative to the accepted recurring baseline when promoting new periodic work. Because Homey's internal rate-limit accounting is not treated as a known public quota, headroom is evaluated using our own operation counts and soak evidence rather than an assumed Athom request ceiling.
- New 5/15/60-minute jobs must be staggered from Core where practical.
- A new recurring flow that consumes more than **10% of the current counted recurring Homey operations/hour** requires explicit load-impact review before activation.

### Throttling tripwire

- Any `Too many requests`/429 response immediately stops optional diagnostics and reintroduction work.
- No automatic retry loop is allowed.
- Publication, evidence and analytics yield before control/safety acquisition.
- A tripped load budget returns the most recently promoted flow to OFF until the cause is understood.

## Runtime design rules

1. **Single-reader first.** Device telemetry is read centrally where practical. Downstream components consume canonical state such as `EM2_State` instead of independently repeating `getDevices()` or `getDevice()` calls.
2. **No duplicate polling without evidence.** A second device poller requires an explicit reason in the Load Map and must show why the canonical state is insufficient.
3. **Separate sampling from publication.** A 5-minute measurement cadence does not imply a 5-minute external publication cadence. GitHub/cloud publication is independently budgeted and normally slower than local sampling.
4. **Event fan-out is load.** A Logic-variable update that triggers multiple flows is treated as a burst/cascade and counted as such, not as a single lightweight event.
5. **Mirror variables are writes.** Validation and observability mirrors are included in the load budget. High-cardinality mirror updates are suppressed when values have not changed.
6. **Validation gates are lifecycle-bound.** Gates used to prove a release condition must not continue indefinitely at full write fan-out after PASS unless they have an explicit production-observability purpose and budget.
7. **External calls from Homey are exceptional resources.** GitHub GET/PUT, raw fetches and other network requests are counted separately from local Homey operations and must be rate-limited/idempotent.
8. **Burst staggering is explicit.** Flows sharing a 5/15/60-minute boundary must be staggered where practical so that Core, history, planner, publisher and validation work do not peak simultaneously.
9. **Actuator control has priority over observability.** When load reduction is required, evidence/history/publication work is reduced before safety-critical state acquisition or validated actuator control.
10. **Fail-safe under throttling.** A 429/rate-limit condition must not trigger retries that increase load. Physical writes remain fail-closed when required state cannot be verified.

## Coding practices

Every new or materially changed Homey flow records at least:

- flow name and ID;
- enabled/disabled state;
- functional layer and purpose;
- trigger type and cadence;
- expected runs/hour;
- `Homey.devices.getDevices()` count/run;
- targeted `getDevice()` count/run;
- `Homey.logic.getVariables()` count/run;
- expected Logic writes/run;
- programmatic Flow starts/run;
- Insights calls/run;
- external GET/PUT/fetch calls/run;
- physical device writes/run;
- downstream variable-triggered flows;
- burst/cascade membership;
- load class: LOW, MEDIUM, HIGH or CRITICAL;
- lifecycle: PRODUCTION, SHADOW, VALIDATION, EVIDENCE, TEMP or DISABLED.

Changes that add polling, increase cadence, add network publication, add more than one new downstream trigger, or add physical writes require a load-impact review before activation.

## Load classes

- **LOW** — infrequent/local, negligible fan-out, no periodic device polling.
- **MEDIUM** — periodic or event-driven work with bounded Logic/network activity.
- **HIGH** — frequent device reads, large Logic fan-out, multiple downstream triggers or periodic external calls.
- **CRITICAL** — combines frequent device polling with external publication, high write fan-out, large payloads or a demonstrated throttling correlation.

Load class is not a quality judgement; it determines the required optimization and validation rigor.

## Reintroduction acceptance gate

Before an isolated flow may be switched ON again:

1. its exact per-run and per-hour load is present in the Load Map;
2. it fits the production budget above without consuming reserved headroom;
3. broad reads have been removed unless explicitly allowed;
4. trigger semantics cannot create freshness-only fan-out;
5. external I/O is bounded and idempotent;
6. cadence is staggered where applicable;
7. only one flow is promoted at a time;
8. a soak is completed before the next promotion;
9. any 429 immediately fails the promotion and returns that flow to OFF.

## Throttling incident procedure

When Homey throttling is observed:

1. freeze unrelated runtime changes;
2. read the Load Map and rank active contributors;
3. identify periodic bursts and Logic-variable cascades;
4. isolate exactly one candidate at a time;
5. keep actuator safety criteria unchanged;
6. verify Homey reachability with minimal read-only probes;
7. record the observed result in the Load Map;
8. redesign the confirmed source rather than permanently relying on broad feature disablement.

A successful single probe proves current reachability only; it does not prove that the throttling condition is permanently resolved.

## Definition of Done

A Homey runtime change is not **DoD VERIFIED** until:

- the Load Map is updated;
- incremental operations/hour and cascade effects are understood;
- the production load budget is satisfied with reserved headroom;
- no unnecessary duplicate device-reader is introduced;
- external publication cadence is justified;
- new burst alignment has been reviewed;
- validation/temporary flows have an explicit retirement condition;
- the change has been smoke-tested and soaked without creating a throttling condition.
