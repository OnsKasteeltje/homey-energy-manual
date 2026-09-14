# ConnectLife oven telemetry

This directory contains the read-only ConnectLife oven telemetry integration used by the EMS Pi runtime.

## Repository ownership

Canonical Git source:

```text
services/pi/integrations/connectlife/
```

The former `scripts/pi/connectlife/` path is legacy and must not be reintroduced as the implementation source.

## Scope

The integration observes the oven through ConnectLife and publishes normalized JSON for EMS observability. It does **not** send appliance commands and does not create an actuator path.

Runtime output:

```text
/home/jeroen/ems/runtime/state/oven-state.json
```

Schema: `EMS_OVEN_STATE_V0.1`.

The poller authenticates once and reuses the same API session in watch mode. Production polling is every 60 seconds. After three consecutive failures it exits so systemd can restart it after 30 seconds.

## Files

- `oven_poll.py` — ConnectLife login/session, oven discovery, polling, atomic output and failure handling.
- `oven_state.py` — vendor-state to EMS-state normalization.
- `ems-connectlife-oven.service` — production systemd service.
- `install_systemd.sh` — guarded installation of credentials and service.

## Credentials and runtime dependencies

Credentials are host-local secrets in `/etc/ems/connectlife.env` and must never be committed. The ConnectLife Python environment remains host-local at:

```text
/home/jeroen/ems/tools/connectlife-probe/.venv/bin/python
```

The normalized state remains at `/home/jeroen/ems/runtime/state/oven-state.json`.

## Installation after repository move

From the repository root on the Pi:

```bash
bash services/pi/integrations/connectlife/install_systemd.sh
```

This rewrites the installed systemd unit so `WorkingDirectory` and `ExecStart` use the new canonical repository path.

## Operational checks

```bash
systemctl status ems-connectlife-oven.service --no-pager -l
journalctl -u ems-connectlife-oven.service --since "10 minutes ago" --no-pager
cat /home/jeroen/ems/runtime/state/oven-state.json
```

Consumers must use `generatedAt` to detect staleness. A failed poll deliberately leaves the last valid JSON intact.

## Architecture boundary

ConnectLife is a vendor-specific **read-only adapter**. Higher EMS layers may consume the normalized JSON state but must not depend on raw ConnectLife field names. Any future oven control capability requires a separate architecture/safety decision.
