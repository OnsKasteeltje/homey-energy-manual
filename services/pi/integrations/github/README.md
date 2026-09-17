# GitHub publication integration

This directory contains Pi-side egress integrations that publish derived observability artifacts to GitHub.

`publish_energy_state.py` reads the canonical local state at `/home/jeroen/ems/data/energy-state-v2.json` and publishes a derived snapshot to `docs/data/energy-state-v2.json` for the website and human-facing observability.

## Boundary

- GitHub publication is **observability only**.
- GitHub is **not** a runtime transport dependency for Homey → Pi state or Pi → Homey control.
- Publication failure must not interrupt state ingest, planning, `/control/current`, Homey execution or physical devices.
- The publisher never writes Homey, Easee, boiler, Honeywell, Quatt or any other actuator.
- The publisher does not create or modify `EM2_Power_Intent`.
- Source freshness and schema are validated before publication; stale/invalid source state fails closed for publication only.

Production scheduling is owned by `deploy/systemd/ems-energy-state-publication.timer` and runs every 15 minutes. The corresponding service is a oneshot observability task.
