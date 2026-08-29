# Pi EMS Bootstrap Manifest

Version: `pi-ems-bootstrap-v0.1`
Branch: `pi-ems-bootstrap-v0.1`
Repository: `OnsKasteeltje/homey-energy-manual`
Target: Raspberry Pi 5 / Raspberry Pi OS Lite 64-bit
Mode: `SHADOW`

## Package contents
- `README-FIRST.md`
- `install.sh`
- `verify.sh`
- `config/install.conf`
- `config/ems.env.example`
- `docker/docker-compose.yml`
- `docker/mosquitto.conf`
- `migrations/001_bootstrap.sql`
- `system/security.sh`
- `system/backup.sh`
- `system/ems-backup.service`
- `system/ems-backup.timer`
- `system/capture-image-lock.sh`
- `RESTORE.md`

## Safety invariants
- `EMS_MODE=SHADOW` is mandatory during bootstrap.
- Homey credentials are empty after installation.
- Victron host is empty after installation.
- No positive physical write path is introduced by this installer.
- PostgreSQL has no host/LAN port mapping.
- Mosquitto has no host/LAN port mapping.
- Installation verification must PASS before commissioning continues.

## Host hardening
- Full OS upgrade during initial bootstrap.
- Unattended security upgrades enabled.
- SSH root login and X11 forwarding disabled; authentication method is deliberately not changed during bootstrap to prevent lockout.
- UFW default-deny incoming; the detected SSH port is allowed before the firewall is enabled.

## Container hardening
- `ems-core` is read-only, drops all Linux capabilities and runs with `no-new-privileges`.
- `/tmp` is an explicit tmpfs for `ems-core`.
- PostgreSQL and Mosquitto use `no-new-privileges` where compatible with their normal entrypoints.
- Docker JSON logs are size-rotated.
- Services share a private Compose bridge but publish no host ports. Outbound network access remains possible for later read-only Homey/Cerbo commissioning.

## Reproducibility
- Runtime stack uses `postgres:16-alpine` and `eclipse-mosquitto:2` during bootstrap.
- The exact resolved image RepoDigests are recorded at installation in `/opt/ems/config/container-image-lock.txt`.
- Before production freeze, the recorded digests must be promoted into the release package so a release is immutable across fresh installations.

## Backup/recovery
- A PostgreSQL custom-format dump, local configuration, secret environment, Git commit and runtime version/image inventory are captured daily.
- Backup timer runs daily with a randomized delay and keeps 14 days locally.
- The installer creates an initial backup immediately.
- `RESTORE.md` defines the recovery procedure.
- Local NVMe backup is not sufficient against device/media loss; encrypted off-device backup remains a production prerequisite.

## Runtime stack
- Docker Engine + Compose plugin
- `ems-core` built from the configured Git branch
- `postgres:16-alpine`
- `eclipse-mosquitto:2`

The distributable ZIP checksum is stored next to the generated ZIP as `pi-ems-bootstrap-v0.1.zip.sha256`; the checksum is intentionally external to the ZIP so it can validate the archive itself.
