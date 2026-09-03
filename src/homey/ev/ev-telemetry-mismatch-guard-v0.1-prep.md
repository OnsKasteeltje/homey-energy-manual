# EV Telemetry Mismatch Guard v0.1 — PREP ONLY

Status: **PREPARED / NOT DEPLOYED / READ-ONLY FIRST**  
Date: 2026-09-03  
Target branch: `main`  
Physical writes: **none**

## Why this exists

On 2026-09-03 the Tesla was physically connected to the Easee charger at approximately 21:52 local time. P1 then showed a characteristic three-phase ramp to approximately 11.7 kW (about 3×16 A), while the Homey Easee device continued to report `plugged_out`, `measure_power=0`, phase currents 0 and `target_charger_current=0`. The Easee cumulative energy value also remained unchanged during the observed interval.

This exposes a control-observability gap: the EMS currently has freshness/coherence checks for its own intent/adapter/state/gate documents, but it does not independently prove that charger telemetry is current before interpreting charger state as physical truth.

## Architectural finding

The current EV actuator validates freshness of these EMS documents:

- Power Intent;
- EV adapter output;
- EM2 State;
- EV adapter gate.

That is necessary but not sufficient. A completely coherent and fresh EMS chain can still consume stale Easee device capabilities.

Therefore **charger telemetry health must be a separately modelled input**. `plugged_out`, `0 W`, `0 A` or an API acknowledgement must never by themselves prove that the physical EV load is absent.

This follows the existing architecture guardrail that requested, commanded and confirmed actuator state are separate and that API acceptance is not physical confirmation.

## Scope of v0.1

v0.1 is deliberately observability-only. It must:

1. read P1 as the authoritative physical grid signal;
2. read only the required Easee charger capabilities;
3. detect a persistent contradiction between a plausible three-phase EV load and charger telemetry claiming inactive/unplugged;
4. publish one compact Logic document, proposed name `EM2_EV_Telemetry_Health`;
5. perform **no physical charger write**;
6. avoid high-frequency polling and broad `getDevices()` / `getVariables()` enumeration where targeted access is available;
7. be idempotent: unchanged health state causes no Logic write.

## Proposed output contract

```json
{
  "schema": "EM2_EV_TELEMETRY_HEALTH_V0.1",
  "sampledAt": "<ISO-8601>",
  "status": "OK | MISMATCH | UNKNOWN",
  "reason": "CONSISTENT | P1_EV_LOAD_BUT_EASEE_INACTIVE | INPUT_INVALID",
  "controlSafe": true,
  "p1": {
    "gridW": 0,
    "l1A": 0,
    "l2A": 0,
    "l3A": 0,
    "evLike3Phase": false
  },
  "easee": {
    "chargerStatus": null,
    "charging": null,
    "chargingState": null,
    "targetA": null,
    "measureW": null,
    "lifetimeKWh": null
  },
  "persistence": {
    "candidateCount": 0,
    "requiredCount": 2
  },
  "physicalWritePerformed": false
}
```

`controlSafe=false` when status is `MISMATCH` or `UNKNOWN` for reasons that prevent trustworthy confirmation of EV physical state.

## Initial mismatch signature

The detector must be conservative. A single high P1 sample is not sufficient.

Candidate EV-like load, initial proposal:

```text
P1 total import >= 4.0 kW
AND L1 >= 5 A
AND L2 >= 5 A
AND L3 >= 5 A
AND max(L1,L2,L3) - min(L1,L2,L3) <= 2 A
```

A mismatch candidate exists only when this physical signature is present **and** Easee reports an inactive contradiction such as:

```text
charging == false
OR chargingState == plugged_out
```

The target-current value is supporting evidence only. `target_charger_current == 0` does not prove the car is physically stopped.

Promote candidate to `MISMATCH` only after at least 2 consecutive low-frequency samples. Clear a mismatch only after at least 2 consecutive consistent samples. Exact cadence is to be selected during Homey load review; v0.1 must not create a high-frequency P1 event fan-out.

## Important limitations

P1 alone cannot prove that the Tesla is the load. The signature means **EV-like balanced three-phase load**, not positive Tesla identification. For that reason v0.1 may raise a telemetry-health fault but must not autonomously execute a destructive or physical corrective action.

A stale Easee integration can also mean that a requested `0 A` or charger-off write is not physically confirmed. Therefore a future control gate must distinguish:

```text
command requested
command accepted by API
physical effect confirmed
```

and must not treat the first two as equivalent to the third.

## Future gate integration — after SHADOW validation only

After v0.1 produces reliable evidence in SHADOW/read-only mode, the EV gate may consume `EM2_EV_Telemetry_Health` with this rule:

```text
Telemetry Health OK       -> existing EV gate rules apply
Telemetry Health UNKNOWN  -> no new positive EV command; physical state remains UNKNOWN
Telemetry Health MISMATCH -> no new positive EV command; raise control-degraded state
```

Do **not** automatically claim `EV_OFF` after a zero-current command while telemetry health is not OK.

Any future physical stop/fail-safe action requires a separately validated charger control path and explicit confirmation that the chosen Easee command causes physical power to disappear at P1. That is outside v0.1.

## Validation plan

### Test A — normal unplugged

- Tesla not connected.
- Low/non-EV P1 load.
- Easee reports unplugged/inactive.
- Expected: `OK`, no alert, no physical write.

### Test B — normal charging with healthy telemetry

- Tesla connected and charging.
- P1 shows balanced three-phase load.
- Easee reports charging/current/power consistently.
- Expected: `OK`, no alert, no physical write.

### Test C — reproduce 2026-09-03 mismatch

- P1 shows persistent EV-like balanced three-phase load.
- Easee reports `plugged_out` / inactive.
- Expected: candidate first, then `MISMATCH` after persistence requirement; no physical write.

### Test D — unrelated large load

- High household load without balanced EV-like three-phase signature.
- Expected: no false Tesla assertion; `OK` or `UNKNOWN` depending input validity.

### Test E — recovery

- Easee telemetry starts matching the physical condition again.
- Expected: mismatch only clears after persistence requirement; no flapping.

## Deployment gate

Do not deploy to Homey until all of the following are complete:

- exact current v0.2.2 EV actuator runtime source is captured/reconciled in GitHub;
- exact current EV gate and state semantics are reconciled;
- targeted device-read method and expected Homey load are confirmed;
- thresholds/cadence have a documented false-positive analysis;
- SHADOW test A–E can be executed without physical writes.

## Repository reconciliation item discovered during preparation

`docs/architecture/homey-runtime-baseline-2026-08-30.md` identifies `EV Power v0.2.2 TARGETED-READ LIVE OWNERSHIP` as the current EV physical writer, while `src/homey/actuators/ev-power/ev-power-v0.2-live-ownership.runtime.md` is an older 2026-08-28 v0.2.1 capture that records `enabled=false` and uses broad `Homey.logic.getVariables()` / `Homey.devices.getDevices()` access.

This source mismatch must be corrected before using the repository copy as the deployable EV actuator baseline.

## Current decision

**PREP PASS. DEPLOYMENT BLOCKED.**

The 2026-09-03 incident is sufficient evidence that charger telemetry freshness/physical confirmation needs its own guard. It is not sufficient evidence to authorize automatic physical stop behavior when Easee telemetry itself is stale.
