# Pi EMS Restore v0.1

This procedure restores the local Pi EMS state only. It does not authorize Homey or Victron writes.

1. Install the same bootstrap version on a fresh Raspberry Pi OS Lite 64-bit host.
2. Stop `ems-core` before restoring data.
3. Select a backup directory from `/opt/ems/backups/<UTC timestamp>` and verify its `SHA256SUMS`.
4. Restore `/opt/ems/secrets/ems.env` from the backup with mode `0600` if the original local credentials are required.
5. Check out the Git commit recorded in `git-commit.txt`.
6. Recreate PostgreSQL, then restore the custom-format dump with `pg_restore --clean --if-exists -U ems -d ems`.
7. Start the Compose stack again.
8. Run `/opt/ems/bootstrap/verify.sh`.
9. Confirm `EMS_MODE=SHADOW`, no Homey token, and no Victron host before any commissioning continues.

A backup located only on the Pi NVMe is protection against logical/configuration failure, not against loss of the Pi or NVMe. An off-device encrypted backup destination must be added before the system is considered production-ready.
