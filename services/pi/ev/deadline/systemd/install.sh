#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/jeroen/ems/repo/homey-energy-manual"
UNIT_DIR="$ROOT_DIR/services/pi/ev/deadline/systemd"

for unit in \
  ems-ev-deadline-state.service \
  ems-ev-deadline-state.path \
  ems-ev-deadline-command.service \
  ems-ev-deadline-command.timer \
  ems-ev-deadline-command.path
do
  sudo install -m 644 -o root -g root "$UNIT_DIR/$unit" "/etc/systemd/system/$unit"
done
sudo systemctl daemon-reload

echo "Prepared only. Units are installed but NOT enabled or started."
echo "Validate first with:"
echo "  systemd-analyze verify /etc/systemd/system/ems-ev-deadline-*.service /etc/systemd/system/ems-ev-deadline-*.path /etc/systemd/system/ems-ev-deadline-*.timer"
echo "Activation requires an explicit later step."
