# Diagnostic source of truth

**Status:** canonical diagnostic architecture rule  
**Scope:** EMS runtime, control, command input, website publication and future end-to-end chain analysis

## 1. Purpose

This document defines which source is authoritative when diagnosing each EMS layer. Before inspecting data, first identify the layer and its canonical source. Diagnose a chain from source to destination, one boundary at a time.

## 2. Canonical diagnostic sources

### Runtime state

```text
Homey devices -> Homey Core / EM2_Public_State
 -> direct Homey -> Pi state push -> POST /state/energy
 -> /home/jeroen/ems/data/energy-state-v2.json -> Pi planner/runtime
```

For runtime conclusions, `/home/jeroen/ems/data/energy-state-v2.json` is the canonical Pi-side state artifact.

`docs/data/energy-state-v2.json` is website/publication output and MUST NOT be used to conclude that live runtime state has or has not changed. It may legitimately lag behind runtime.

### Control

```text
Pi planner -> hardened validator -> GET /control/current
 -> Homey PI Dynamic Planner Bridge -> EM2_Power_Intent
 -> device adapter -> validation gate -> actuator -> physical device
```

Do not diagnose a downstream actuator before upstream intent and gate state are verified.

### Website observability

Artifacts under `docs/data/` are derived publication/UI artifacts unless explicitly documented otherwise. They diagnose the website publication layer, not live runtime. The target remains a dedicated read-only Pi web-data boundary.

### User command input

User commands currently have an explicit transitional exception where GitHub command JSON is part of the route. Tesla deadline:

```text
V2 frontend -> authenticated Cloudflare Worker
 -> docs/data/tesla-deadline-command.json
 -> Homey EV Deadline Goal Adapter -> Homey Core
 -> direct Homey -> Pi state push
 -> /home/jeroen/ems/data/energy-state-v2.json
```

The command JSON proves only that the submitted command reached that command boundary. After Homey consumes it, diagnosis continues through Homey/Core and canonical Pi runtime state.

## 3. Mandatory diagnostic method

For every chain incident or end-to-end validation:

1. Identify the exact chain and ownership boundaries from canonical architecture documentation.
2. Identify the canonical diagnostic source at every boundary before inspecting values.
3. Walk the chain in order and establish the last known-good boundary and first failing boundary.
4. Do not jump downstream, restart services, change flows, or weaken freshness/safety guards before localizing the failing boundary.
5. Explicitly distinguish runtime state, control state, command-transfer state and website/publication state.
6. Derived/cached artifacts may corroborate a diagnosis but may not override another layer's canonical source.

## 4. Root-cause documentation rule

Chain knowledge discovered during troubleshooting is part of the architecture.

Whenever analysis of an end-to-end chain establishes a root cause, the investigation MUST finish by updating this diagnostic source-of-truth document with the durable information learned from that chain.

Record where applicable:

- verified canonical chain and ownership boundaries;
- authoritative diagnostic source at each relevant boundary;
- observed failure boundary and root cause;
- misleading/non-authoritative artifacts that must not be used for that conclusion;
- shortest safe verification sequence for recurrence;
- architecture/documentation inconsistencies discovered during investigation.

Do not turn this document into a chronological incident log. Record reusable diagnostic knowledge. Incident-specific detail belongs in a dedicated runbook when needed.

A troubleshooting task is not architecturally complete at "root cause found". It is complete only after reusable chain knowledge is captured here and affected component/runbook documentation is aligned.

## 5. Tesla deadline diagnostic sequence

```text
1. docs/data/tesla-deadline-command.json
   prove submitted command/requestId at command-transfer boundary

2. Homey EV Deadline Goal Adapter / deadline Logic
   prove command ingestion and goal lifecycle

3. /home/jeroen/ems/data/energy-state-v2.json
   prove canonical Homey -> Pi runtime state
   check deadline_active, deadline_at, remaining_kwh, deadline_max_a

4. Pi planner and /control/current
   prove planning/allocation and current bounded command

5. Homey PI Bridge -> EM2_Power_Intent
   prove executor intent

6. EV adapter -> gate -> actuator
   prove translation, safety validation and physical-write decision

7. Easee / Tesla
   prove physical device state and delivered energy

8. website/publication artifacts
   diagnose presentation/publication only after runtime correctness is known
```

### Verified diagnostic lesson - 2026-09-19

A V2 Tesla command for 38% -> 51%, local deadline 10:00 Europe/Amsterdam and max 7 A was correct at the command boundary. GitHub-published `docs/data/energy-state-v2.json` still showed an older deadline and initially appeared to indicate failed ingestion.

Canonical Pi runtime proved ingestion was already correct: `deadline_active=true`, `deadline_at=2026-09-19T08:00:00.000Z`, `deadline_max_a=7`, `remaining_kwh=7.15`, and `need=TESLA_DEADLINE_BLOCKED_NOT_CONNECTED`.

Root cause of the apparent mismatch: a lagging GitHub website-publication artifact was consulted as though it were canonical runtime state.

Reusable rule: after the Tesla command-transfer boundary, validate ingestion against Homey/Core and direct Pi runtime state. Do not use `docs/data/energy-state-v2.json` to decide whether Homey -> Pi runtime ingestion succeeded.

## 6. Related canonical architecture

- `docs/architecture/CURRENT-EMS-STATE.md`
- `docs/architecture/homey-pi-runtime-dataflow.md`
- `docs/architecture/runtime-publication-separation.md`
- `docs/architecture/tesla-deadline-end-to-end.md`
- `docs/architecture/ems-software-architecture-live.md`
