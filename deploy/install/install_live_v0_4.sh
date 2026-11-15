#!/usr/bin/env bash
# EMS Live V0.4 - source-managed frontend-only release.
# Default is preflight. Never changes EMS/P1/battery services or Caddy.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ROOT="/var/www/ems-frontend-v2"
BASELINE_COMMIT="0236a046bc9efebfb7c32d68e5c71e1393911dd3"
BACKUP="/home/jeroen/ems/backup/live-v0.4-$(date +%Y%m%d-%H%M%S)"
FILES=(
  frontend/live/index.html
  frontend/live/render/live.js
  frontend/live/render/battery.mjs
  frontend/live/state/flow-v04.mjs
  frontend/live/styles/live-v04.css
)

if [[ "$(id -u)" -ne 0 ]]; then
  echo "STOP: run with sudo"; exit 1
fi
if [[ "$(git -C "$REPO" branch --show-current)" != "main" ]] ||
   [[ -n "$(git -C "$REPO" status --porcelain)" ]] ||
   [[ "$(git -C "$REPO" rev-parse HEAD)" != "$(git -C "$REPO" rev-parse origin/main)" ]]; then
  echo "STOP: requires clean main matching origin/main"; exit 1
fi

echo "=== LIVE V0.4 OFFLINE TESTS ==="
(cd "$REPO" && node --check frontend/live/render/live.js)
(cd "$REPO" && node --check frontend/live/render/battery.mjs)
(cd "$REPO" && node --check frontend/live/state/flow-v04.mjs)
(cd "$REPO" && node tests/frontend/test_live_v04_flow.mjs)
(cd "$REPO" && node tests/frontend/test_live_battery_v03.mjs)
(cd "$REPO" && PYTHONDONTWRITEBYTECODE=1 python3 tests/frontend/test_live_consumers_contract.py)
(cd "$REPO" && PYTHONDONTWRITEBYTECODE=1 python3 tests/frontend/test_v2_local_assets_contract.py)

# Fail closed if the independent battery/P1 sources are unavailable.
for endpoint in state/current live/battery; do
  curl --fail --silent --max-time 4 \
    "http://127.0.0.1:3200/web/$endpoint" >/dev/null || {
      echo "STOP: read-only Web Data API unavailable at /web/$endpoint"
      exit 1
    }
done

echo "=== CHECK EXISTING LIVE FILES ==="
for rel in "${FILES[@]}"; do
  dest="$ROOT/${rel#frontend/}"
  if [[ -f "$dest" ]] && cmp -s "$REPO/$rel" "$dest"; then
    continue
  fi
  if git -C "$REPO" cat-file -e "$BASELINE_COMMIT:$rel" 2>/dev/null; then
    [[ -f "$dest" ]] || { echo "STOP: missing installed file $dest"; exit 1; }
    if ! cmp -s <(git -C "$REPO" show "$BASELINE_COMMIT:$rel") "$dest"; then
      echo "STOP: deployed drift at $dest"; exit 1
    fi
  elif [[ -e "$dest" ]]; then
    echo "STOP: unmanaged V0.4 asset already exists: $dest"; exit 1
  fi
done
echo "PASS: source/runtime preflight; no changes applied"

if [[ "$#" -ne 1 || "$1" != "--apply" ]]; then
  echo "To install: sudo bash deploy/install/install_live_v0_4.sh --apply"
  exit 0
fi

echo "=== TARGETED BACKUP ==="
mkdir -p "$BACKUP"
for rel in "${FILES[@]}"; do
  dest="$ROOT/${rel#frontend/}"
  if [[ -f "$dest" ]]; then
    install -D -m 0644 "$dest" "$BACKUP/${rel#frontend/}"
  fi
done

rollback() {
  echo "ERROR: V0.4 frontend installation failed; restoring selected Live files"
  for rel in "${FILES[@]}"; do
    dest="$ROOT/${rel#frontend/}"
    if [[ -f "$BACKUP/${rel#frontend/}" ]]; then
      install -D -m 0644 "$BACKUP/${rel#frontend/}" "$dest"
    else
      rm -f "$dest"
    fi
  done
}
trap rollback ERR

echo "=== INSTALL LIVE ONLY ==="
for rel in "${FILES[@]}"; do
  dest="$ROOT/${rel#frontend/}"
  install -D -m 0644 "$REPO/$rel" "$dest"
  cmp "$REPO/$rel" "$dest"
done
trap - ERR

echo "PASS: V0.4 Live frontend deployed; no API, Caddy, Homey or AlphaESS service restarted"
echo "Backup: $BACKUP"
