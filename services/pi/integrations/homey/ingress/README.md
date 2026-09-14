# Homey → Pi ingress

The Homey-to-Pi state path enters the Pi through the authenticated `POST /state/energy` API boundary.

The endpoint and its Homey-specific validation currently live in:

- `services/pi/api/status/server.py`
- `services/pi/api/status/state_ingest.py`

This directory exists to make the integration direction and ownership explicit without duplicating transport implementation.

```text
Homey Core state
    → POST /state/energy
    → Pi status API
    → /home/jeroen/ems/data/energy-state-v2.json
    → Pi planner/control
```

Pi owns accepted canonical state and planning after ingress. Homey remains the source/executor at the edge; this path performs no Pi-to-Homey device writes.
