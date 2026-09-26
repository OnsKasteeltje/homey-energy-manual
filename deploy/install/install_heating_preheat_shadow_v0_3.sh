#!/usr/bin/env bash
set -euo pipefail

REPO=/home/jeroen/ems/repo/homey-energy-manual
SYSTEMD=/etc/systemd/system
WEB_API_RUNTIME=/home/jeroen/ems/runtime/web-data-api
PV_FLEX_TARGET=/var/www/ems-frontend-v2/pv-flex
SHADOW_JSON=/home/jeroen/ems/data/heating-preheat-shadow-v0.3.json
API_CHECK=/tmp/ems-heating-preheat-shadow-api.json

# 1. Install only the new local-only Heating Preheat shadow units.
sudo install -m 0644 "$REPO/deploy/systemd/ems-heating-preheat-shadow.service" "$SYSTEMD/ems-heating-preheat-shadow.service"
sudo install -m 0644 "$REPO/deploy/systemd/ems-heating-preheat-shadow.timer" "$SYSTEMD/ems-heating-preheat-shadow.timer"
sudo systemctl daemon-reload

# 2. Prove one complete local-only shadow build before exposing it.
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

# 3. Refresh only the Web Data API source that exposes the allowlisted shadow.
#    Do not touch Caddy or another ingress boundary.
sudo install -d -o jeroen -g jeroen -m 0755 "$WEB_API_RUNTIME"
sudo install -o jeroen -g jeroen -m 0644 \
  "$REPO/services/pi/api/web-data/server.py" \
  "$WEB_API_RUNTIME/server.py"
sudo systemctl restart ems-web-data-api.service

# 4. Refresh only the PV Flex assets. Do not run the full frontend/Caddy installer.
sudo install -d -o root -g root -m 0755 "$PV_FLEX_TARGET"
sudo rsync -a --delete --chmod=D755,F644 "$REPO/frontend/pv-flex/" "$PV_FLEX_TARGET/"
sudo chown -R root:root "$PV_FLEX_TARGET"

# 5. Validate the private localhost API projection before enabling recurrence.
rm -f "$API_CHECK"
for _ in {1..10}; do
  if curl -fsS http://127.0.0.1:3200/web/planner/heating-preheat-shadow > "$API_CHECK"; then
    break
  fi
  sleep 1
done

python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/ems-heating-preheat-shadow-api.json")
if not path.exists() or path.stat().st_size == 0:
    raise SystemExit("FAIL: Heating Preheat Web Data API not reachable")
data = json.loads(path.read_text())
if data.get("schema") != "EMS_WEB_HEATING_PREHEAT_SHADOW_V1":
    raise SystemExit("FAIL: unexpected Heating Preheat web schema")
if data.get("controlWrites") is not False:
    raise SystemExit("FAIL: web projection unexpectedly permits control writes")
if data.get("baselineAuthority") != "HONEYWELL":
    raise SystemExit("FAIL: web projection lost Honeywell authority")
print("PASS: private Heating Preheat Web Data API projection")
print("house:", data.get("house"))
print("cvGuard:", data.get("cvGuard"))
PY
rm -f "$API_CHECK"

# 6. Only after one-shot + API validation, enable recurring SHADOW evaluation.
sudo systemctl enable --now ems-heating-preheat-shadow.timer

echo
echo "=== HEATING PREHEAT SHADOW ==="
systemctl status ems-heating-preheat-shadow.service --no-pager -l || true
systemctl list-timers --all --no-pager | grep ems-heating-preheat-shadow

echo
echo "PASS: Heating Preheat V0.3 commissioned READ_ONLY/SHADOW"
echo "PV Flex runtime assets refreshed without changing Caddy or other frontend pages."
