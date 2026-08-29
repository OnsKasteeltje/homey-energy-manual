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

## Safety invariants
- `EMS_MODE=SHADOW` is mandatory during bootstrap.
- Homey credentials are empty after installation.
- Victron host is empty after installation.
- No positive physical write path is introduced by this installer.
- PostgreSQL has no host/LAN port mapping.
- Mosquitto has no host/LAN port mapping.
- Installation verification must PASS before commissioning continues.

## Runtime stack
- Docker Engine + Compose plugin
- `ems-core` built from the configured Git branch
- `postgres:16-alpine`
- `eclipse-mosquitto:2`

The distributable ZIP checksum is stored next to the generated ZIP as `pi-ems-bootstrap-v0.1.zip.sha256`; the checksum is intentionally external to the ZIP so it can validate the archive itself.
