# ConnectLife integration architecture

## Purpose

This document defines the repository and runtime boundary for the read-only ConnectLife oven telemetry integration.

## Repository source of truth

Canonical source is:

`services/pi/integrations/connectlife/`

The former `scripts/pi/connectlife/` location is legacy and must not be reintroduced.

## Runtime boundary

The integration runs directly from the checked-out canonical repository path through `ems-connectlife-oven.service`. It writes only normalized state to:

`/home/jeroen/ems/runtime/state/oven-state.json`

Schema: `EMS_OVEN_STATE_V0.1`.

The ConnectLife Python virtual environment remains host-local at `/home/jeroen/ems/tools/connectlife-probe/.venv/`. Credentials remain host-local in `/etc/ems/connectlife.env` and are never Git-managed.

## Safety boundary

ConnectLife is read-only telemetry. It may observe vendor state and normalize it for EMS consumers, but it does not control the oven. Any future actuator/control path requires a separate architecture and safety decision.

## Migration rule

After moving the repository source, the installed systemd unit must be reinstalled from `services/pi/integrations/connectlife/install_systemd.sh` so `WorkingDirectory` and `ExecStart` point at the canonical target path.
