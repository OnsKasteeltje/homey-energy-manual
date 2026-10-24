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

## Operational recovery (24 October 2026)

An incomplete ConnectLife account registration caused login error `LifeConnectAuthError 206001: Account Pending Registration`. Although the cloud response listed missing terms/privacy consent fields, the observed recovery was to **complete the address in the official ConnectLife app**. Inspect the app for incomplete registration details or pending consent prompts; never grant consent programmatically.

The service had an independent `226/NAMESPACE` startup failure because `/home/jeroen/ems/runtime/state` did not exist. Restore that directory with the expected ownership before starting the service. After recovery, verify a fresh `generatedAt` in `oven-state.json`; `systemctl is-active` alone is insufficient. The production EMS planner, safety ownership and read-only adapter contract are unchanged.

See `services/pi/integrations/connectlife/README.md` for the focused troubleshooting steps.
