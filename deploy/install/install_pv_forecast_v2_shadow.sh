#!/usr/bin/env bash
set -e
SRC=/home/jeroen/ems/repo/homey-energy-manual
DST=/home/jeroen/ems/runtime/forecast/pv
mkdir -p "$DST"
install -m 0755 "$SRC/services/pi/forecast/pv/build_pv_forecast_v2.py" "$DST/"
install -m 0755 "$SRC/services/pi/forecast/pv/archive_forecast.py" "$DST/"
sudo install -m 0644 "$SRC/deploy/systemd/ems-pv-forecast-v2-shadow.service" /etc/systemd/system/
sudo install -m 0644 "$SRC/deploy/systemd/ems-pv-forecast-v2-shadow.timer" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ems-pv-forecast-v2-shadow.timer
