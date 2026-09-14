# Honeywell integration architecture

## Purpose

This document defines the current repository/runtime boundary for the Honeywell integration after migration to the target Pi service structure.

## Repository source of truth

Honeywell source is owned under:

`services/pi/integrations/honeywell/`

The former source path under `src/pi/ems-runtime/tools/honeywell/` is legacy and must not be reintroduced as the Git source of truth.

## Runtime compatibility path

The deployed runtime remains:

`/home/jeroen/ems/runtime/tools/honeywell/`

This runtime path is intentionally retained for compatibility with existing systemd/runtime references while repository ownership has moved to the target structure.

Deployment copies the managed Honeywell source from `services/pi/integrations/honeywell/` into the compatibility runtime path.

## Host-local state

The following runtime content is host-local and must never be deleted, compared as Git drift, or committed as managed source:

- `.venv/`
- `cache/`
- `output/`
- `config/account.env`
- Python bytecode / `__pycache__/`

`config/account.env.example` remains managed source; `config/account.env` is the local secret-bearing runtime file.

## Deployment and drift rules

`scripts/deploy_ems_pi.sh` must:

- exclude the old Honeywell subtree from the legacy `src/pi/ems-runtime` rsync;
- deploy Honeywell separately from `services/pi/integrations/honeywell/`;
- preserve all host-local state listed above;
- reject unexpected unmanaged files outside the allowed host-local state.

`scripts/ems_pi_drift_check.sh` must compare managed Honeywell files from the target source tree against `/home/jeroen/ems/runtime/tools/honeywell/` while ignoring the same host-local state.

## Change discipline

Future Honeywell implementation changes must be made under `services/pi/integrations/honeywell/` and follow the normal EMS sequence:

**inspect → minimal change → update architecture → architecture gate → deploy → validate**

A future runtime-path migration away from `/home/jeroen/ems/runtime/tools/honeywell/` is a separate coordinated change because systemd/runtime references and local credentials/virtualenv must move atomically.
