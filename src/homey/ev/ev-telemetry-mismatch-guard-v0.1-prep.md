# EV Telemetry Mismatch Guard v0.1 — SHADOW PREP

Status: **HOMEY PREP PASS / DISABLED / NOT RUN**  
Date: 2026-09-03  
Target branch: `main`  
Physical writes: **none**

## Why this exists

On 2026-09-03 the Tesla was physically connected to the Easee charger at approximately 21:52 local time. P1 then showed a characteristic three-phase ramp to approximately 11.7 kW (about 3×16 A), while the Homey Easee device continued to report `plugged_out`, `measure_power=0`, phase currents 0 and `target_charger_current=0`. The Easee cumulative energy value also remained unchanged during the observed interval.

This exposes a control-observability gap: the EMS currently has freshness/coherence checks for its own intent/adapter/state/gate documents, but it does not independently detect a physical contradiction between authoritative P1 power and Easee charger telemetry.

## Runtime reconciliation completed

The current Homey runtime was read directly on 2026-09-03.

- `EM v2 | 60 Actuator | EV Power v0.2.2 TARGETED-READ LIVE OWNERSHIP` is `enabled=true`, `broken=false` and remains the EV physical-write owner.
- `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.1 TARGETED-READ` is `enabled=true`, `broken=false` and remains Logic-only validation.
- Exact current runtime captures were synchronized to GitHub before this SHADOW implementation was prepared.

## Homey preparation completed

The output Logic variable now exists:

- name: `EM2_EV_Telemetry_Health`
- type: `string`
- stable Logic ID: `db467a16-7d23-4033-af96-42a69b932a2b`

The disabled Advanced Flow now exists:

- name: `EM v2 | 82 Observability | EV Telemetry Mismatch Guard v0.1 SHADOW`
- flow ID: `18a99261-421c-4c5f-a771-36a626b7496a`
- `enabled=false`
- `broken=false`
- trigger: `EM2_State` changed
- manual Start path exists for controlled future validation
- the flow has **not been started**

The runtime source in `src/homey/ev/ev-telemetry-mismatch-guard-v0.1-shadow.js` is bound to the stable Logic ID above.

A temporary one-shot provisioning/readback flow was used because the Homey connector does not expose direct Logic-variable creation/readback. It is disabled. The temporary GitHub ID-readback artifact was deleted immediately after the ID was confirmed. No device or physical writes occurred during provisioning/readback.

## Design refinement: reuse EM2_State

Current Core already performs targeted reads of both P1 and Easee and publishes the relevant values together in `EM2_State`, including P1 total power and L1/L2/L3 current plus Tesla/Easee measured power, requested current, phase currents, charger state and cumulative meter value.

Therefore v0.1 reads only the existing `EM2_State` Logic variable plus its own previous health document. It performs **zero device reads** and **zero physical writes**.

Prepared runtime source:

`src/homey/ev/ev-telemetry-mismatch-guard-v0.1-shadow.js`

## Output contract

`EM2_EV_Telemetry_Health` uses schema `EM2_EV_TELEMETRY_HEALTH_V0.1` with status `OK | MISMATCH | UNKNOWN`, a reason, `controlSafe`, source-state metadata, P1/Easee evidence, persistence counters and thresholds. `controlSafe=false` whenever status is not `OK`. In v0.1 this remains **observability only** and has no effect on the live gate or actuator.

## Historical threshold replay — PASS with refinement

Offline replay used `P1_HomeWizard_normalized_2025-04-01_to_2026-08-31.csv`, containing 49,712 post-Quatt quarter-hours. The source provides quarter-hour import energy plus per-phase maximum watts. For replay only, phase current was approximated as `phase_max_W / 230 V`. Because the three phase maxima may occur at different instants inside a quarter-hour, these results are conservative and are suitable for screening candidate thresholds, not for proving individual EV sessions.

Keeping:

```text
P1 total import >= 4.0 kW
AND L1 >= 5 A
AND L2 >= 5 A
AND L3 >= 5 A
```

produced the following sensitivity to allowed phase spread:

| Max phase spread | Candidate quarter-hours | Candidate clusters | Clusters >=30 min | Clusters >=60 min |
|---:|---:|---:|---:|---:|
| 2.0 A | 281 | 136 | 66 | 22 |
| 1.5 A | 220 | 113 | 49 | 14 |
| 1.0 A | 132 | 66 | 25 | 10 |
| 0.5 A | 51 | 29 | 12 | 2 |

The original 2.0 A spread is therefore unnecessarily permissive for SHADOW v0.1. A 1.0 A limit cuts historical candidate intervals by about 53% while preserving many sustained EV-like plateaus. The known 2026-09-03 incident had an observed P1 phase-current spread of approximately 0.5 A, so it remains comfortably inside a 1.0 A limit.

Several surviving historical clusters sit near characteristic EV-like total power plateaus (roughly 4.6, 5.2, 6.0, 7.2, 8.8 and 11.7 kW) and many occur on Thursday/Friday/weekend evenings. This is supportive but not treated as ground truth because the historical P1 file does not contain authoritative Tesla/Easee session labels.

**Selected SHADOW v0.1 start value: `MAX_PHASE_SPREAD_A = 1.0`.**

## Mismatch signature

Candidate EV-like physical load:

```text
P1 total import >= 4.0 kW
AND L1 >= 5 A
AND L2 >= 5 A
AND L3 >= 5 A
AND max(L1,L2,L3) - min(L1,L2,L3) <= 1 A
```

Contradiction requires that physical signature plus Easee-side evidence claiming no active charge:

```text
chargeState in plugged_out/disconnected/unplugged/idle
OR
Easee measured power <= 100 W and all available Easee phase currents < 1 A
```

`requestedA == 0` remains supporting evidence only. It never proves physical stop.

## Persistence / anti-flapping

- first contradictory sample -> `UNKNOWN / ...PENDING_CONFIRMATION`;
- second consecutive contradictory sample -> `MISMATCH`;
- recovery from an established mismatch also requires 2 consecutive consistent samples;
- stale/invalid source state -> `UNKNOWN / INPUT_INVALID`;
- source-state freshness limit is 7 minutes, matching the current 5-minute Core cadence with margin.

The thresholds remain SHADOW thresholds; no control integration is allowed until live validation has confirmed normal unplugged, healthy charging, mismatch and recovery behavior.

## Homey load properties

Steady-state guard execution is designed as:

```text
1 targeted Logic read: EM2_State
1 targeted Logic read: EM2_EV_Telemetry_Health
0 device reads
0 Insights reads
0 network calls
0 physical writes
<=1 Logic update, semantic-change only
```

Preferred runtime trigger is event-driven on `EM2_State` change. No separate high-frequency timer is used.

## Architectural finding

The live EV actuator validates freshness of Power Intent, EV adapter output, Core State and EV adapter gate. That is necessary but not sufficient. A coherent EMS chain can still coexist with charger telemetry that contradicts physical P1 evidence.

The existing architecture already requires requested, commanded and confirmed actuator state to remain distinct. The new health document fills the missing physical-consistency layer; it does not create another writer.

## Future gate integration — only after SHADOW validation

```text
Telemetry Health OK       -> existing EV gate rules apply
Telemetry Health UNKNOWN  -> no new positive EV command; physical state remains UNKNOWN
Telemetry Health MISMATCH -> no new positive EV command; raise control-degraded state
```

Do not automatically claim `EV_OFF` after a zero-current command while telemetry health is not OK. Any future physical stop/fail-safe action requires separate proof that the chosen Easee command actually removes the physical load at P1. That remains outside v0.1.

## Validation plan

### Test A — normal unplugged
Low/non-EV P1 load; Easee inactive. Expected: `OK`, no physical write.

### Test B — normal charging with healthy telemetry
Balanced three-phase P1 load and Easee charge telemetry consistent with charging. Expected: `OK`, no physical write.

### Test C — reproduce 2026-09-03 mismatch
Persistent EV-like P1 load while Easee reports inactive/zero. Expected: first sample `UNKNOWN`, second sample `MISMATCH`, no physical write.

### Test D — unrelated large load
High household load without balanced three-phase signature. Expected: no Tesla assertion and no false mismatch.

### Test E — recovery
Easee telemetry becomes consistent again. Expected: two consistent samples required to clear an established mismatch.

## Deployment/validation gate

Before enabling the Homey SHADOW flow:

1. synchronize the disabled Homey flow from the old 2.0 A prepared value to the validated 1.0 A GitHub value;
2. re-read the disabled flow and verify no device-write cards and no physical writes in script;
3. execute tests A–E in controlled SHADOW validation;
4. only then consider feeding telemetry health into the existing EV validation gate.

## Current decision

**HISTORICAL THRESHOLD REPLAY PASS. GITHUB SHADOW = 1.0 A. HOMEY FLOW REMAINS DISABLED/NOT RUN AND STILL REQUIRES SYNC BEFORE VALIDATION.**

No control integration or physical write was introduced.
