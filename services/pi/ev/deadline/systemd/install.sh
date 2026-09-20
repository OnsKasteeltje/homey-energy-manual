#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/jeroen/ems/repo/homey-energy-manual"
UNIT_DIR="$ROOT_DIR/services/pi/ev/deadline/systemd"

sudo install -m 644 -o root -g root "$UNIT_DIR/ems-ev-deadline-state.service" /etc/systemd/system/ems-ev-deadline-state.service
sudo install -m 644 -o root -g root "$UNIT_DIR/ems-ev-deadline-state.path" /etc/systemd/system/ems-ev-deadline-state.path
sudo systemctl daemon-reload

echo "Prepared only. Units are installed but NOT enabled or started."
echo "Validate first with:"
echo "  systemd-analyze verify /etc/systemd/system/ems-ev-deadline-state.service /etc/systemd/system/ems-ev-deadline-state.path"
echo "Activation requires an explicit later step."
