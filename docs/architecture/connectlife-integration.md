# ConnectLife integration architecture

## Purpose

The ConnectLife integration is the Pi-owned, vendor-specific read-only adapter for oven telemetry.

## Canonical repository location

```text
services/pi/integrations/connectlife/
```

The former `scripts/pi/connectlife/` location is legacy and must not be reintroduced as the implementation source.

## Runtime contract

The adapter writes normalized state only to:

```text
/home/jeroen/ems/runtime/state/oven-state.json
```

Schema: `EMS_OVEN_STATE_V0.1`.

Credentials remain outside GitHub in `/etc/ems/connectlife.env`. The host-local Python environment remains `/home/jeroen/ems/tools/connectlife-probe/.venv/`.

## Safety boundary

The integration is read-only telemetry. It does not control the oven and does not create an actuator path. Any future oven control capability requires a separate architecture and safety decision.

## Migration

After the repository move, reinstall the unit from:

```bash
bash services/pi/integrations/connectlife/install_systemd.sh
```

This updates `WorkingDirectory` and `ExecStart` to the canonical target path while preserving the existing state-file, credentials and Python-environment locations.
