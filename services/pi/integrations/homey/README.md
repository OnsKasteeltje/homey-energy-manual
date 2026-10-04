# Homey integration

This directory defines the Pi-side boundary between Homey and the EMS Pi.

## Architectural roles

- **Pi** is planner/control authority.
- **Homey** is executor and edge-safety layer.
- The integration is deliberately directional and bounded; neither side silently takes over the other side's ownership.

## Homey → Pi (ingress)

Homey publishes the canonical energy-state snapshot to the authenticated Pi endpoint `POST /state/energy`.

The HTTP transport boundary remains implemented by `services/pi/api/status/server.py`. Homey-specific validation and persistence are owned by `services/pi/integrations/homey/ingress/state_ingest.py`. At deployment time that module is placed into the existing status-API runtime directory so the runtime import contract remains unchanged. The accepted state is written to `/home/jeroen/ems/data/energy-state-v2.json` and then consumed by Pi planners.

Source flow:

```text
Homey Core state
    → POST /state/energy
    → services/pi/integrations/homey/ingress/state_ingest.py
    → energy-state-v2.json + history
    → Pi planner/control
```

The API owns HTTP transport; the Homey integration owns Homey-specific state semantics and validation.

### EV control observability ingress

The AI V0.2 evidence path adds a second, strictly observability-only Homey -> Pi
ingress. A targeted Homey observability script reads the existing EV Power
Intent, Adapter, Gate, Actuator Status and Device Health Logic contracts and
posts them to `POST /state/ev-control`.

The HTTP route remains in `services/pi/api/status/server.py`; Homey-specific
validation and local archival semantics live in
`services/pi/integrations/homey/ingress/ev_control_ingest.py`. Accepted events
are appended to `ems-history.sqlite -> ev_control_events`.

This path is not a control input. It performs no device reads or writes and must
never become an upstream dependency of Power Intent, Adapter, Gate or Actuator.


The Quooker observability path follows the same control-neutral pattern without
adding Quooker to the Core snapshot. Canonical Homey source
`apps/homey/observability/quooker/quooker-pi-push-v0.1.homeyscript.js` reads
only the existing Quooker Control, SHADOW Actuator Status and detector
diagnostic Logic contracts and posts them to authenticated
`POST /state/quooker`. Pi-side validation and semantic deduplication are owned
by `services/pi/integrations/homey/ingress/quooker_evidence_ingest.py`; accepted
evidence is archived in `ems-history.sqlite/quooker_control_events`.

This Quooker evidence path is observability-only: the push performs no device
reads, Logic writes, planning decisions or physical writes. The Quooker
actuator evidence is SHADOW and `desiredOn`/`wouldWrite` must never be
interpreted as proof that a physical command was issued.

## Pi → Homey (egress)

The active production transport is Homey pulling `GET /control/current` through the enabled PI Dynamic Planner Bridge. `services/pi/integrations/homey/egress/publish_pi_control_intent.py` remains compatibility code and must not become a second production writer while the Homey bridge is authoritative.

Production flow:

```text
Pi planner/control
    → /control/current
    → Homey PI Dynamic Planner Bridge
    → Homey EM2_Power_Intent
    → adapter / gate / actuator
    → devices
```

The Pi planner never writes devices directly. Homey remains responsible for bounded realtime execution and local safety.

### Heating control-contract SHADOW egress

Heating V0.5 adds a separate commissioning-only egress source:
`services/pi/integrations/homey/egress/publish_heating_control_intent_shadow.py`.
It writes only the dedicated string Logic contract
`EM2_Heating_Control_Intent`, schema `EMS_HEATING_CONTROL_INTENT_V0.1`.

This is deliberately **not** a production Power Intent producer. It declares
`plannerAuthority=SHADOW_ONLY`,
`productionPlannerHeatingGrantPresent=false`,
`deviceWrites=false`, `physicalWriteAllowed=false` and top-level
`liveExecutionAllowed=false` (also repeated under `safety`). The downstream
Homey Heating Adapter/Gate remain SHADOW and no Heating actuator exists. Normal
runtime uses the pinned Logic ID from host-local
`heating-control-homey-shadow-config.json`; first commissioning performs no
bulk Homey discovery.

If first commissioning already reached host-local `state=READY` but final
post-publish readback was interrupted, `--resume-ready` validates only the
pinned Logic/Flow IDs with paced targeted reads, performs one SHADOW publish,
and enables the publisher timer only after Intent, Adapter and Gate pass on the
same control revision. The only Homey mutation in resume validation is the single
normal SHADOW Intent Logic-value publish; no Logic/Flow structure is created or updated.


## Runtime compatibility

Repository placement is independent from the installed Pi runtime layout. During the incremental repository migration the existing runtime contracts stay unchanged:

- state ingress source: `services/pi/integrations/homey/ingress/state_ingest.py`
  → runtime: `/home/jeroen/ems/runtime/status-api/state_ingest.py`
- EV observability ingress source: `services/pi/integrations/homey/ingress/ev_control_ingest.py`
  → runtime: `/home/jeroen/ems/runtime/status-api/ev_control_ingest.py`
- compatibility egress source: `services/pi/integrations/homey/egress/publish_pi_control_intent.py`
  → runtime: `/home/jeroen/ems/runtime/homey-deploy/publish_pi_control_intent.py`
- Heating SHADOW egress source: `services/pi/integrations/homey/egress/publish_heating_control_intent_shadow.py`
  → runtime: `/home/jeroen/ems/runtime/homey-deploy/publish_heating_control_intent_shadow.py`

This keeps existing imports and callers stable while the Git source converges to the target architecture.

## Operator / maintenance tooling

Homey Advanced Flow audit/deploy helpers are not part of the runtime state/control transport. They live under:

- `tools/maintenance/homey/homey_flow_audit.py`
- `tools/maintenance/homey/homey_flow_deploy.py`
