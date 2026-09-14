# Homey integration

This directory defines the Pi-side boundary between Homey and the EMS Pi.

## Architectural roles

- **Pi** is planner/control authority.
- **Homey** is executor and edge-safety layer.
- The integration is deliberately directional and bounded; neither side silently takes over the other side's ownership.

## Homey → Pi (ingress)

Homey publishes the canonical energy-state snapshot to the authenticated Pi endpoint `POST /state/energy`.

The HTTP transport boundary remains implemented by `services/pi/api/status/server.py`. Homey-specific validation and persistence are owned by `ingress/state_ingest.py`. At deployment time that module is placed into the existing status-API runtime directory so the runtime import contract remains unchanged. The accepted state is written to `/home/jeroen/ems/data/energy-state-v2.json` and then consumed by Pi planners.

Source flow:

```text
Homey Core state
    → POST /state/energy
    → services/pi/integrations/homey/ingress/state_ingest.py
    → energy-state-v2.json + history
    → Pi planner/control
```

The API owns HTTP transport; the Homey integration owns Homey-specific state semantics and validation.

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

Repository placement is independent from the installed Pi runtime layout. During the incremental repository migration the existing runtime contracts stay unchanged:

- ingress: `/home/jeroen/ems/runtime/status-api/state_ingest.py`
- egress: `/home/jeroen/ems/runtime/homey-deploy/publish_pi_control_intent.py`

This keeps existing imports and callers stable while the Git source converges to the target architecture.

## Out of scope

The legacy `homey_flow_audit.py` and `homey_flow_deploy.py` are operator/maintenance tools, not runtime state/control transport. They remain separate from the Homey↔Pi data path and should move to the repository tooling area when next touched.
