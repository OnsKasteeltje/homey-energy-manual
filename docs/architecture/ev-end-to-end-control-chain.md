# EV end-to-end control chain — Pi planner to Tesla/Easee

Status: production architecture and troubleshooting reference  
Established: 2026-09-14  
Scope: complete EV chain from frontend observability and Pi planning through Homey to the physical Easee charger / Tesla

## Purpose

This document is the primary orientation map for the EV chain. Use it first when analysing EV charging behaviour so that troubleshooting starts at the correct layer and does not confuse frontend observability, planner policy, Homey execution, charger telemetry and physical charging.

The website/frontend is **observability only**. It does not command the charger. The control authority is the Pi planner; Homey is the execution layer; the EV actuator is the single physical Easee writer.

## End-to-end architecture

```text
Website / EV status
        ↑ observability only
        │
Pi dynamic planner
        ↓
/control/current
        ↓ Homey pulls
Homey PI Dynamic Planner Bridge
        ↓
EM2_Power_Intent
        ↓
EV Power Adapter
        ↓
EV Power Adapter Gate
        ↓
EV Power Actuator LIVE
        ↓ physical write
Easee charger
        ↓
Tesla

Tesla / Easee / Homey Core telemetry
        ↓
EM2_State / EV context
        ↓
Pi state input + Homey execution context
        ↑
website/status observability
```

Do not model this as the website commanding Homey or as the Pi directly writing to Easee.

## Layer responsibilities

### 1. Website / frontend

Purpose: visualization and diagnosis only.

It may show planner targets, EV status, deadlines, current, power and control-chain health. A frontend display problem is not by itself a charger-control problem.

Primary published diagnostic artifact:

`docs/data/ev-control-status.json`

### 2. Pi dynamic planner

Purpose: policy and scheduling authority.

The Pi decides the EV target based on planner policy, PV opportunity, deadline requirements, EV availability/state and guardrails. User-facing deadline times are interpreted in `Europe/Amsterdam` local time.

The Pi publishes control guidance through `/control/current`. It does not directly write the Easee charger.

Expected authority/source concepts include:

```text
authority = PI
evSource  = PI_DYNAMIC_PLANNER_V0.3
```

### 3. Homey Pi bridge

Production lineage as validated 2026-09-14:

`EM v2 | 05 Transport | PI Dynamic Planner Bridge v1.3.0`

Purpose: read the current Pi control command, validate it and translate it into Homey control intent. Homey pulls the Pi endpoint; the Pi does not push physical device commands into Homey.

### 4. Canonical Power Intent

`EM2_Power_Intent` is the Homey-side canonical control intent. It must stay revision-coherent with `EM2_State` / Core.

A new Core state revision must propagate into a matching Power Intent revision. The production state-trigger behaviour exists specifically to prevent stale intent execution.

See `ev-revision-mismatch-runbook.md` for the 2026-09-13 incident and invariant.

### 5. EV Power Adapter

Production lineage as validated 2026-09-14:

`EM v2 | 60 Adapter | EV Power v0.1.5 DEADLINE-CAP OPPORTUNITY16 START6 RUN6`

Purpose: translate generic EV power intent into EV/Easee current semantics while applying EV-specific constraints such as deadline cap, opportunity charging and minimum start/run current.

The adapter is read-only with respect to the physical charger.

### 6. EV Power Adapter Gate

Production lineage as validated 2026-09-14:

`EM v2 | 80 Validation | EV Power Adapter Gate v0.2.6 START6`

Purpose: safety and coherence validation before any physical write.

Decisive checks include schema validity, revision alignment, canonical intent/state validity, electrical/current mapping, command range and translation semantics. Invalid control input must fail closed.

Easee telemetry health is useful diagnostic context but stale capability timestamps must not automatically be interpreted as proof that physical control is unavailable. See `ev-device-health-failsafe-v0.2.md`.

### 7. EV Power Actuator

Production lineage as validated 2026-09-14:

`EM v2 | 60 Actuator | EV Power v0.2.7 START6 RUN6 LIVE + EASEE SESSION`

Purpose: the single physical writer to Easee.

Only a valid, coherent adapter/gate contract may cause a physical write. Invalid or stale canonical control input must result in fail-closed behaviour, normally 0 A / no positive write.

Important observability fields include:

```text
status
reason
physicalWritePerformed
targetA
previousA
controlRevision
coreRevision
```

### 8. Easee charger and Tesla

Easee is the physical charging endpoint. Tesla connection/SOC/deadline context influences planning and execution, while actual Easee current/power is the decisive evidence that a charger command became physical behaviour.

For a positive E2E validation, do not stop at `gate.status = PASS`. Confirm Easee target/offered current and measured charging power, and where useful confirm Tesla SOC progression.

## Observability publisher

Production lineage as validated 2026-09-14:

`EM v2 | 95 Observability | EV Control Status Publish v0.4`

It consolidates planner/intent, adapter, gate, actuator and device-health evidence into `docs/data/ev-control-status.json`.

This file is the preferred first diagnostic view because it lets the layers be compared without broad Homey API reads.

## E2E health interpretation

A fully executable positive command should conceptually satisfy:

```text
Pi target > 0
↓
Power Intent target > 0
↓
intent/state/core revisions coherent
↓
adapter valid
↓
gate PASS
↓
actuator live/ready and physical write succeeds
↓
Easee offered/target current > 0
↓
measured charger power > 0
↓
Tesla charging / SOC progresses
```

A disconnected car is a different valid operating state. If Easee reports `plugged_out` and telemetry later becomes stale, a positive physical command must not be forced through. Fail-closed/no-write behaviour is safe and expected.

## Known failure modes and diagnostic order

### A. Positive planner target but actuator `REVISION_MISMATCH`

Likely Homey execution-coherency issue. Compare intent, adapter, state and core revisions before debugging the Pi or Easee. See `ev-revision-mismatch-runbook.md`.

### B. `STALE / EASEE_TELEMETRY_STALE`

Do not automatically conclude that Easee is unreachable. Stable capability timestamps previously produced false stale classifications while the charger remained controllable. Health is diagnostic/observability context; authoritative control checks remain in adapter/gate/actuator. See `ev-device-health-failsafe-v0.2.md`.

### C. Car genuinely disconnected

`chargeState = plugged_out`, target normally 0, no physical positive write. Stale telemetry after the car has left can be normal.

### D. Charging is physically occurring while connection telemetry briefly says disconnected/stale

This remains an explicit improvement item. If Easee is demonstrably drawing charging current/power, a transient vehicle-disconnected or stale-connection signal should not immediately invalidate an otherwise active charging session. The exact safe rule is not yet implemented and must be designed without weakening fail-closed protection for genuinely invalid control contracts.

### E. Frontend looks wrong

First compare the underlying control/status JSON and planner endpoint. The frontend is not control authority and must not be used as sole proof that the charger was or was not commanded.

## Fast troubleshooting sequence

Use this order whenever EV charging behaves unexpectedly:

1. Check Pi target and EV status in `/control/current`.
2. Check `docs/data/ev-control-status.json`.
3. Establish whether `targetW/requestedA` is positive or zero.
4. Check adapter `valid/status/reason`.
5. Check gate `status/errors/checks` and revision coherence.
6. Check actuator `status/reason/physicalWritePerformed/targetA`.
7. Check Easee charge state, offered/target current and measured power.
8. Check Tesla connection/SOC/deadline only in the context of the preceding evidence.
9. Only then investigate frontend rendering if control evidence is healthy but presentation is wrong.

Avoid broad Homey reads during routine diagnosis; follow `homey-api-access-guidelines.md` and prefer the consolidated status artifact plus Pi-local state/history.

## Proven E2E evidence

### 2026-09-12 positive physical validation

A controlled positive Pi command reached the physical charger:

```text
Pi target       4830 W / 7 A
Gate            PASS
Actuator        WRITE_OK_POST_SESSION
physical write  true
Easee           Charging
offered/target  7 A
measured power  ~4.9 kW
```

Returning the Pi target to 0 A physically paused charging. This proves the Pi → Homey bridge → intent → adapter → gate → actuator → Easee path can execute end to end.

### 2026-09-13 revision-coherency validation

After the Power Intent state-trigger fix, a 16 A deadline command propagated with matching revisions, gate PASS and actuator ready/session control, after which Easee changed from paused/0 A to charging at 16 A. See `ev-revision-mismatch-runbook.md`.

### 2026-09-14 disconnected-state validation

With the Tesla away/disconnected, the chain showed Pi authority with EV target 0 / IDLE. Easee context eventually became stale/plugged-out and the downstream path performed no physical positive write. This validates safe no-charge/fail-closed behaviour, but is not a fresh positive physical E2E charging test.

The next natural production validation is the first genuine charging opportunity after the Tesla is reconnected. Follow one planner command through every layer and require physical Easee current/power evidence.

## Safety invariants

- Website/frontend is observability only.
- Pi is planner/control-policy authority; it does not directly write Easee.
- Homey is the execution layer.
- EV actuator is the single physical Easee writer.
- Never bypass adapter/gate revision or translation validation to make charging start.
- Never weaken fail-closed behaviour to hide a coherency problem.
- A stale telemetry heuristic is not equivalent to proven charger unreachability.
- User-facing EV deadlines use `Europe/Amsterdam` local time.
- Physical E2E success requires charger-side evidence, not merely a planner target or gate PASS.

## Related documentation

- `docs/architecture/homey-pi-runtime-dataflow.md` — canonical Homey/Pi directionality and runtime dataflow.
- `docs/architecture/ev-revision-mismatch-runbook.md` — revision mismatch incident, fix and diagnostic procedure.
- `docs/architecture/ev-device-health-failsafe-v0.2.md` — Easee telemetry-health semantics and why stale health is not by itself a hard control veto.
- `docs/architecture/homey-api-access-guidelines.md` — API/throttling discipline during diagnosis.
- `docs/architecture/ems-process-ww-tesla-planner.md` — planner-level WW/Tesla process context.
- `docs/data/ev-control-status.json` — current consolidated EV execution-chain evidence.

## Search terms

When this document is not immediately visible, search for:

`EV end-to-end`, `Pi planner Easee`, `EV control chain`, `EM2_Power_Intent`, `EV Power Adapter`, `EV Power Adapter Gate`, `EV Power Actuator`, `ev-control-status.json`, `LIVE_FAIL_CLOSED`, `REVISION_MISMATCH`, `EASEE_TELEMETRY_STALE`, `Tesla 0A`, `Easee session`.
