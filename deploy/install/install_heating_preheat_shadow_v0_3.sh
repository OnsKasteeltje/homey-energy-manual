#!/usr/bin/env bash
set -euo pipefail

REPO=/home/jeroen/ems/repo/homey-energy-manual
SYSTEMD=/etc/systemd/system

sudo install -m 0644 "$REPO/deploy/systemd/ems-heating-preheat-shadow.service" "$SYSTEMD/ems-heating-preheat-shadow.service"
sudo install -m 0644 "$REPO/deploy/systemd/ems-heating-preheat-shadow.timer" "$SYSTEMD/ems-heating-preheat-shadow.timer"
sudo systemctl daemon-reload

# Prove one complete local-only shadow build before enabling recurrence.
sudo systemctl start ems-heating-preheat-shadow.service

python3 - <<'PY'
import json
from pathlib import Path

path = Path("/home/jeroen/ems/data/heating-preheat-shadow-v0.3.json")
data = json.loads(path.read_text())
if data.get("schema") != "EMS_HEATING_PREHEAT_SHADOW_V0.3":
    raise SystemExit("FAIL: unexpected heating shadow schema")
if data.get("mode") != "READ_ONLY" or data.get("controlMode") != "SHADOW":
    raise SystemExit("FAIL: heating shadow is not READ_ONLY / SHADOW")
if data.get("controlWrites") is not False:
    raise SystemExit("FAIL: heating shadow unexpectedly permits control writes")
if data.get("baselineAuthority") != "HONEYWELL":
    raise SystemExit("FAIL: Honeywell baseline authority lost")
print("PASS: Heating Preheat V0.3 one-shot is read-only and fail-closed")
print("generatedAt:", data.get("generatedAt"))
print("cvGuard:", data.get("cvGuard"))
for room in data.get("rooms", []):
    if room.get("preheatScope"):
        print(room.get("key"), room.get("shadow"))
PY

sudo systemctl enable --now ems-heating-preheat-shadow.timer

systemctl status ems-heating-preheat-shadow.service --no-pager -l || true
systemctl list-timers --all --no-pager | grep ems-heating-preheat-shadow
