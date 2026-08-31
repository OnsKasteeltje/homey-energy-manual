# Pi EMS Bootstrap v0.1

Purpose: prepare a fresh Raspberry Pi OS Lite 64-bit installation for the Home Energy EMS.

## Safety baseline
- EMS starts in SHADOW mode only.
- Homey reads are not configured by this package.
- Homey writes are not configured.
- Victron writes are not configured.
- PostgreSQL is not exposed to the LAN.
- Mosquitto is not exposed to the LAN.
- The installer does not alter Homey.

## Before you start
1. Install Raspberry Pi OS Lite 64-bit with Raspberry Pi Imager.
2. Enable SSH in Imager and create your normal Pi user.
3. Boot the Pi and make sure it has Internet access.
4. Copy the ZIP to the Pi and unpack it.

## Install
```bash
unzip pi-ems-bootstrap-v0.1.zip
cd pi-ems-bootstrap-v0.1
sudo ./install.sh
```

The installer creates `/opt/ems`, installs Docker if needed, clones the EMS repository, creates a local secret environment file, starts PostgreSQL and Mosquitto, applies the bootstrap database migration, builds `ems-core`, and leaves it in SHADOW mode.

## Verify
```bash
sudo /opt/ems/bootstrap/verify.sh
```

Do not add Homey credentials or enable any LIVE mode during initial installation.
