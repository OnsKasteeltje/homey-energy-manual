# Pi Bootstrap Hardening v0.1

Status: PREPARATION ONLY / OFFLINE SHADOW.

The Raspberry Pi bootstrap is hardened before installation-day use without connecting to the operational Homey EMS.

## Host baseline
- Raspberry Pi OS Lite 64-bit.
- Initial OS upgrade.
- Docker Engine from the official Debian repository plus Compose plugin.
- Unattended package upgrades enabled.
- Conservative SSH hardening: root login and X11 forwarding disabled; the authentication method is not changed automatically.
- UFW default-deny incoming with the detected SSH port allowed before firewall activation.

## Container baseline
- No host port mappings for PostgreSQL or Mosquitto.
- `ems-core` is read-only, uses a tmpfs `/tmp`, drops all Linux capabilities and enables `no-new-privileges`.
- PostgreSQL and Mosquitto enable `no-new-privileges`.
- Docker JSON log rotation is bounded.
- The Compose bridge permits outbound access because later SHADOW commissioning needs read-only Homey/Cerbo access, while inbound application ports remain unpublished.

## Reproducibility
Bootstrap currently resolves `postgres:16-alpine` and `eclipse-mosquitto:2` and records their exact RepoDigests in `/opt/ems/config/container-image-lock.txt`. Before a production release is frozen, those digests must be promoted into the release package so fresh installations resolve the same immutable images.

## Backup and recovery
- The installer makes an initial PostgreSQL/configuration backup.
- A systemd timer creates daily backups and retains 14 days locally.
- Backup metadata records Git commit, Docker versions and container image inventory.
- Restore instructions are included in `RESTORE.md`.
- An encrypted off-device destination is still required before production because NVMe-local backup alone does not protect against media/device loss.

## Safety boundary
The hardening work does not configure Homey or Victron endpoints. `EMS_MODE=SHADOW` remains mandatory, Homey credentials remain empty, Victron host remains empty, and no positive physical write path is introduced.
