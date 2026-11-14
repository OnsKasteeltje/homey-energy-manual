#!/usr/bin/env bash
# Narrow AlphaESS Live UI/API release; default is inspection, not deployment.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
ROOT="/var/www/ems-frontend-v2"
RUNTIME_API="/home/jeroen/ems/runtime/web-data-api/server.py"
SOURCE_API="services/pi/api/web-data/server.py"
BACKUP="/home/jeroen/ems/backup/alphaess-live-v0.3-$(date +%Y%m%d-%H%M%S)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "STOP: run with sudo"; exit 1
fi
if [[ "$(git -C "$REPO" branch --show-current)" != "main" ]] ||
   [[ -n "$(git -C "$REPO" status --porcelain)" ]] ||
   [[ "$(git -C "$REPO" rev-parse HEAD)" != "$(git -C "$REPO" rev-parse origin/main)" ]]; then
  echo "STOP: requires clean main synced with origin/main"; exit 1
fi
if ! systemctl is-active --quiet ems-web-data-api.service; then
  echo "STOP: existing read-only Web Data API is not active"; exit 1
fi

echo "=== BATTERY LIVE SOURCE TESTS ==="
(cd "$REPO" && PYTHONDONTWRITEBYTECODE=1 python3 tests/api/test_alphaess_live_battery_resource.py)
(cd "$REPO" && node tests/frontend/test_live_battery_v03.mjs)
(cd "$REPO" && node --check frontend/live/render/battery.mjs)

# Fail closed on any unrelated local changes; prior source must match HEAD^.
# This deliberately avoids broad rsync --delete or a complete EMS deployment.
for rel in "$SOURCE_API" frontend/live/index.html frontend/live/styles/live.css; do
  if [[ "$rel" = "$SOURCE_API" ]]; then
    dest="$RUNTIME_API"
  else
    dest="$ROOT/${rel#frontend/}"
  fi
  if [[ ! -f "$dest" ]]; then
    echo "STOP: deployed file missing: $dest"; exit 1
  fi
  if ! cmp -s "$REPO/$rel" "$dest" &&
     ! cmp -s <(git -C "$REPO" show "HEAD^:$rel") "$dest"; then
    echo "STOP: existing deployed source drift at $dest"; exit 1
  fi
done
for rel in frontend/live/render/battery.mjs frontend/live/state/battery-state.mjs; do
  dest="$ROOT/${rel#frontend/}"
  if [[ -e "$dest" ]] && ! cmp -s "$REPO/$rel" "$dest"; then
    echo "STOP: unmanaged file exists: $dest"; exit 1
  fi
done

echo "PASS: AlphaESS Live V0.3 preflight; no changes applied"
if [[ "$#" -ne 1 || "$1" != "--apply" ]]; then
  echo "Explicit deployment: sudo bash deploy/install/install_alphaess_live_v0_3.sh --apply"
  exit 0
fi

echo "=== BACK UP ONLY TOUCHED FILES ==="
mkdir -p "$BACKUP"
cp -a "$RUNTIME_API" "$BACKUP/server.py"
cp -a "$ROOT/live/index.html" "$BACKUP/index.html"
cp -a "$ROOT/live/styles/live.css" "$BACKUP/live.css"
if [[ -f "$ROOT/live/render/battery.mjs" ]]; then
  cp -a "$ROOT/live/render/battery.mjs" "$BACKUP/battery.mjs"
fi
if [[ -f "$ROOT/live/state/battery-state.mjs" ]]; then
  cp -a "$ROOT/live/state/battery-state.mjs" "$BACKUP/battery-state.mjs"
fi

echo "=== DEPLOY ONLY ALPHAESS LIVE FILES ==="
install -m 0644 "$REPO/$SOURCE_API" "$RUNTIME_API"
for rel in frontend/live/index.html frontend/live/styles/live.css \
           frontend/live/render/battery.mjs frontend/live/state/battery-state.mjs; do
  dest="$ROOT/${rel#frontend/}"
  install -D -m 0644 "$REPO/$rel" "$dest"
done

if ! systemctl restart ems-web-data-api.service ||
   ! systemctl is-active --quiet ems-web-data-api.service; then
  echo "ERROR: restarting Web Data API failed; restoring previous version"
  cp -a "$BACKUP/server.py" "$RUNTIME_API"
  cp -a "$BACKUP/index.html" "$ROOT/live/index.html"
  cp -a "$BACKUP/live.css" "$ROOT/live/styles/live.css"
  if [[ -f "$BACKUP/battery.mjs" ]]; then
    cp -a "$BACKUP/battery.mjs" "$ROOT/live/render/battery.mjs"
  else
    rm -f "$ROOT/live/render/battery.mjs"
  fi
  if [[ -f "$BACKUP/battery-state.mjs" ]]; then
    cp -a "$BACKUP/battery-state.mjs" "$ROOT/live/state/battery-state.mjs"
  else
    rm -f "$ROOT/live/state/battery-state.mjs"
  fi
  systemctl restart ems-web-data-api.service || true
  exit 1
fi
cmp "$REPO/$SOURCE_API" "$RUNTIME_API"
echo "PASS: Web Data API running and Live battery assets deployed"
echo "No battery timer, P1, Homey or EMS control service was changed"
echo "Backup: $BACKUP"
