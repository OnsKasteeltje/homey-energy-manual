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

## Runtime compatibility

Repository placement is independent from the installed Pi runtime layout. During the incremental repository migration the existing runtime contracts stay unchanged:

- state ingress source: `services/pi/integrations/homey/ingress/state_ingest.py`
  → runtime: `/home/jeroen/ems/runtime/status-api/state_ingest.py`
- EV observability ingress source: `services/pi/integrations/homey/ingress/ev_control_ingest.py`
  → runtime: `/home/jeroen/ems/runtime/status-api/ev_control_ingest.py`
- compatibility egress source: `services/pi/integrations/homey/egress/publish_pi_control_intent.py`
  → runtime: `/home/jeroen/ems/runtime/homey-deploy/publish_pi_control_intent.py`

This keeps existing imports and callers stable while the Git source converges to the target architecture.

## Operator / maintenance tooling

Homey Advanced Flow audit/deploy helpers are not part of the runtime state/control transport. They live under:

- `tools/maintenance/homey/homey_flow_audit.py`
- `tools/maintenance/homey/homey_flow_deploy.py`
