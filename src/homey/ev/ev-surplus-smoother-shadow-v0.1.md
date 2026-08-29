# EV Surplus Smoother v0.1 — SHADOW design

Status: **DESIGN / NOT DEPLOYED**

Date: 2026-08-29

## Purpose

Stabilize the Tesla opportunity-charging input without reintroducing `EM2_Public_State` as a control bus and without adding a recurring P1 poller.

The smoother is an upstream signal-conditioning stage only. It does not own EMS policy, does not translate W→A, does not bypass Power Intent, Adapter, Gate or Actuator, and performs no physical device writes.

## Input model

Primary signal:

- Homey P1 capability `measure_power` change event from the existing P1 meter.
- No recurring `getDevices()` or `getVariables()` scan.

EV correction:

```text
EV_surplus_raw_W = max(0, -P1_W + EV_actual_W)
```

The correction is required because P1 net export falls when the Tesla itself starts consuming. Without adding actual EV charging power back, the controller would incorrectly interpret its own load as disappearance of PV surplus.

Sign convention:

- negative P1 power = export;
- positive P1 power = import;
- `EV_actual_W >= 0`.

If EV actual power is unavailable or stale, SHADOW output must mark the sample degraded and must not silently substitute a guessed charging power.

## Smoothing contract

Initial validation setting:

- window: 2 minutes;
- statistic: arithmetic mean;
- evaluation: at most once per 2 minutes;
- input samples may arrive event-driven at P1 capability cadence;
- no downstream wake-up for every raw P1 event.

Output variable proposal:

`EM2_EV_Surplus_Smoothed`

Minimum schema:

```json
{
  "schema": "EM2_EV_SURPLUS_SMOOTHED_V0.1",
  "generatedAt": "ISO-8601",
  "windowSeconds": 120,
  "statistic": "mean",
  "sampleCount": 0,
  "rawLatestW": 0,
  "evActualW": 0,
  "smoothedSurplusW": 0,
  "quality": "GOOD|DEGRADED|STALE",
  "semanticRevision": 0,
  "readOnly": true,
  "deviceWrites": false
}
```

## Semantic suppression

`generatedAt`, sample timestamps and sample count are observability fields and must not cause downstream control fan-out by themselves.

A new semantic output is emitted only when one of these changes materially:

1. `smoothedSurplusW` crosses a control-relevant quantization boundary;
2. quality changes between `GOOD`, `DEGRADED` and `STALE`;
3. an explicit safety condition changes.

Initial quantization proposal for SHADOW comparison: 230 W steps, matching one ampere on one phase only as a conservative signal bucket. This is a SHADOW comparison parameter, not yet an actuator contract. The existing EV Adapter remains authoritative for executable 3-phase current translation and its 6 A minimum.

## Relationship to existing anti-flapping

This smoother and the existing approximately 115/120-second EV start/stop confirmation solve different problems:

- smoothing reduces short-term PV/cloud noise in the requested power signal;
- anti-flapping prevents physical start/stop oscillation after a control request exists.

The anti-flapping guard remains unchanged during SHADOW validation.

## Architecture placement

```text
P1 measure_power changed
        │
        ▼
EV Surplus Smoother v0.1 SHADOW
  - EV correction
  - 2 min mean
  - semantic suppression
        │
        ├──────────────► SHADOW comparison / telemetry only
        │
        └─ future promotion candidate
                 │
                 ▼
          Power Intent
                 ▼
        P1 Pre-EV Gate
                 ▼
         EV Power Adapter
                 ▼
        EV Adapter Gate
                 ▼
         guarded Actuator
```

`EM2_Public_State` is not part of this path.

## Important trigger correction

The active Power Intent P1 v0.2.3 currently triggers only on semantic `EM2_Control_WW` change. Runtime analysis on 2026-08-29 showed this is too narrow for Tesla-only state changes: Core can change `EM2_Decision` between HOLD and `TESLA_BUFFER_EXPORT` / `TESLA_CHARGE_OPPORTUNITY` while `EM2_Control_WW` remains semantically unchanged.

Therefore this smoother must **not** simply be wired into the current P1 trigger contract yet. Before promotion, Power Intent needs a control trigger that covers EV semantic changes without restoring freshness fan-out. Candidate designs are:

1. dedicated semantic EV-control signal emitted after Core has completed State/Decision/WW writes; or
2. dual semantic trigger with a settle/alignment guard for Decision and Control-WW.

A dedicated post-Core semantic EV-control signal is preferred because it avoids transient revision mismatch and keeps one clear producer/consumer responsibility.

## Homey load budget — proposed SHADOW

The design is intentionally event-driven at the device-card boundary but bounded before Logic fan-out.

Recurring/broad load:

- additional broad `getDevices()` scans: **0/hour**;
- additional broad `getVariables()` scans: **0/hour**;
- external HTTP/GitHub calls: **0/hour**;
- physical device writes: **0/hour**.

Event load:

- raw P1 capability events may be frequent, but they remain local to the smoother input path;
- aggregation output is evaluated at most every 2 minutes = **30 evaluations/hour**;
- downstream semantic Logic writes should be materially lower than 30/hour because unchanged quantized values are suppressed;
- while SHADOW, no Power Intent/Adapter/Gate/Actuator fan-out is permitted from this variable.

This is acceptable for a bounded SHADOW experiment only if implemented without broad API reads. Promotion to production control requires measured event/write counts and must still preserve the 50% operational headroom rule.

## SHADOW validation plan

For each 2-minute window record:

- latest raw P1 W;
- EV actual W;
- corrected raw surplus W;
- 2-minute mean surplus W;
- current Core Tesla decision;
- current `EM2_Power_Intent.targets.ev.target_W`;
- current EV Adapter requested A;
- whether existing control would start/stop/change current;
- hypothetical smoother-driven result.

Required scenarios:

1. steady high PV export;
2. short cloud dip under 2 minutes;
3. sustained cloud cover over 2 minutes;
4. recovery from cloud cover;
5. Tesla already charging, proving EV self-load correction;
6. surplus around the 3×6 A executable threshold (4140 W);
7. zero/low surplus;
8. stale or unavailable EV actual power.

## Promotion criteria

Do not connect this output to Power Intent until all are true:

- no Homey 429 during soak;
- no broad recurring reads added;
- measured output writes remain within load budget;
- cloud dips no longer cause unnecessary stop/restart behavior;
- sustained deficit still stops charging within the intended safety/anti-flap envelope;
- EV self-load correction prevents false surplus collapse after charging starts;
- stale/degraded input fails closed;
- Power Intent semantic trigger regression is corrected independently;
- existing Adapter/Gate/Actuator safety contracts remain unchanged.

## Rollback

SHADOW rollout is rollback-safe because the new variable has no production consumer. Disable/remove the smoother flow and delete no existing control variables. No actuator or policy rollback is required.
