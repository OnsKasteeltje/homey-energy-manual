# Honeywell integration architecture

Honeywell source is owned under `services/pi/integrations/honeywell/`.

The deployed compatibility runtime remains `/home/jeroen/ems/runtime/tools/honeywell/` until a separate coordinated runtime-path migration is performed.

Host-local runtime state must be preserved and excluded from Git drift/deletion: `.venv/`, `cache/`, `output/`, `config/account.env`, and Python bytecode caches. `config/account.env.example` remains managed source.

`scripts/deploy_ems_pi.sh` deploys managed Honeywell source from the target repository path into the compatibility runtime path and excludes host-local state. `scripts/ems_pi_drift_check.sh` compares only managed Honeywell files.

Observed Honeywell target history does not add another Honeywell collector. The existing semantic-event history observer reads the local `output/honeywell-state.json` artifact and records sparse target/mode changes in canonical `ems-history.sqlite`. The Web Data API may project seven days of that observed evidence for Heating presentation; weekly schedule data must not be used to synthesize historical target values.

Future Honeywell implementation changes must follow: **inspect → minimal change → update architecture → architecture gate → deploy → validate**.
