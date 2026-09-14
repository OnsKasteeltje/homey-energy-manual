# Homey integration

This directory defines the Pi-side boundary between Homey and the EMS Pi.

## Architectural roles

- **Pi** is planner/control authority.
- **Homey** is executor and edge-safety layer.
- The integration is deliberately directional and bounded; neither side silently takes over the other side's ownership.

## Homey → Pi (ingress)

Homey publishes the canonical energy-state snapshot to the authenticated Pi endpoint `POST /state/energy`.

The HTTP boundary is implemented by `services/pi/api/status/server.py`; Homey-specific validation and persistence are currently implemented by `services/pi/api/status/state_ingest.py` because they are part of that API endpoint's runtime. The accepted state is written to `/home/jeroen/ems/data/energy-state-v2.json` and then consumed by Pi planners.

Source flow:

```text
Homey Core state
    → POST /state/energy
    → Pi status API
    → energy-state-v2.json + history
    → Pi planner/control
```

Do not duplicate the ingest implementation under this integration directory merely for folder symmetry. The API owns transport; this integration documentation owns the Homey↔Pi boundary semantics.

## Pi → Homey (egress)

`egress/publish_pi_control_intent.py` reads the hardened current Pi command from `http://127.0.0.1:3100/control/current`, validates planner/executor/contract ownership and publishes `EM2_POWER_INTENT_V0.2` to Homey Logic.

It does not write devices directly. Homey adapters/gates and actuators remain responsible for safe execution.

Source flow:

```text
Pi planner/control
    → /control/current
    → egress/publish_pi_control_intent.py
    → Homey EM2_Power_Intent
    → Homey executor/safety
    → devices
```

## Runtime compatibility

Repository placement is independent from the installed Pi runtime layout. During the incremental repository migration, the egress publisher continues to deploy to its existing runtime path:

`/home/jeroen/ems/runtime/homey-deploy/publish_pi_control_intent.py`

This keeps existing runtime callers stable while the Git source converges to the target architecture.

## Out of scope

The legacy `homey_flow_audit.py` and `homey_flow_deploy.py` are operator/maintenance tools, not runtime state/control transport. They remain separate from the Homey↔Pi data path and should move to the repository tooling area when next touched.
