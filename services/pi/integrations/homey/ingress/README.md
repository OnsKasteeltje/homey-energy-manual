# Homey → Pi ingress

The Homey-to-Pi state path enters the Pi through the authenticated `POST /state/energy` API boundary.

Source ownership is split deliberately:

- HTTP endpoint/transport: `services/pi/api/status/server.py`
- Homey state validation and persistence: `services/pi/integrations/homey/ingress/state_ingest.py`

At deployment time `state_ingest.py` is copied to the existing runtime status-API directory, preserving the current import and runtime path.

```text
Homey Core state
    → POST /state/energy
    → state_ingest.py
    → /home/jeroen/ems/data/energy-state-v2.json
    → Pi planner/control
```

Pi owns accepted canonical state and planning after ingress. Homey remains the source/executor at the edge; this path performs no Pi-to-Homey device writes.
