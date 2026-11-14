#!/usr/bin/env bash
# Targeted AlphaESS-only install; never starts or enables timers.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SOURCE="$REPO/services/pi/integrations/alphaess"
TARGET_ALPHAESS_RUNTIME="/home/jeroen/ems/runtime/integrations/alphaess"
UNITS="$REPO/deploy/systemd"
SERVICE="ems-alphaess-readonly.service"
TIMER="ems-alphaess-readonly.timer"
BACKUP="/home/jeroen/ems/backup/alphaess-v0.2-$(date +%Y%m%d-%H%M%S)"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "STOP: run with sudo"; exit 1
fi
if [[ "$(git -C "$REPO" branch --show-current)" != "main" ]] ||
   [[ -n "$(git -C "$REPO" status --porcelain)" ]] ||
   [[ "$(git -C "$REPO" rev-parse HEAD)" != "$(git -C "$REPO" rev-parse origin/main)" ]]; then
    echo "STOP: requires clean Pi checkout synced with origin/main"; exit 1
fi
if systemctl is-active --quiet "$SERVICE" ||
   systemctl is-active --quiet "$TIMER"; then
    echo "STOP: AlphaESS service/timer active"; exit 1
fi
for file in "$SOURCE/collect_readonly.py" "$SOURCE/README.md" \
    "$UNITS/$SERVICE" "$UNITS/$TIMER"; do
    [[ -f "$file" ]] || { echo "STOP: missing $file"; exit 1; }
done

echo "=== ALPHAESS OFFLINE REGRESSION ==="
(
  cd "$REPO"
  PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tests/integrations/alphaess/test_alphaess_readonly.py
)

# Explicitly protect any non-source host files in the target subtree.
if [[ -d "$TARGET_ALPHAESS_RUNTIME" ]]; then
  while IFS= read -r rel; do
    case "$rel" in
      collect_readonly.py|README.md) ;;
      *) echo "STOP: unmanaged AlphaESS runtime file: $rel"; exit 1 ;;
    esac
  done < <(cd "$TARGET_ALPHAESS_RUNTIME" && find . -type f \
    -not -path '*/__pycache__/*' -not -name '*.pyc' -printf '%P\n')
fi

echo "=== ALPHAESS-ONLY BACKUP ==="
mkdir -p "$BACKUP"
if [[ -d "$TARGET_ALPHAESS_RUNTIME" ]]; then
  cp -a "$TARGET_ALPHAESS_RUNTIME" "$BACKUP/runtime"
fi
for unit in "$SERVICE" "$TIMER"; do
  if [[ -f "/etc/systemd/system/$unit" ]]; then
    cp -a "/etc/systemd/system/$unit" "$BACKUP/$unit"
  fi
done

echo "=== INSTALL (NO START) ==="
mkdir -p "$TARGET_ALPHAESS_RUNTIME"
install -m 0644 "$SOURCE/collect_readonly.py" "$TARGET_ALPHAESS_RUNTIME/collect_readonly.py"
install -m 0644 "$SOURCE/README.md" "$TARGET_ALPHAESS_RUNTIME/README.md"
for unit in "$SERVICE" "$TIMER"; do
  install -m 0644 "$UNITS/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
cmp "$SOURCE/collect_readonly.py" "$TARGET_ALPHAESS_RUNTIME/collect_readonly.py"
cmp "$SOURCE/README.md" "$TARGET_ALPHAESS_RUNTIME/README.md"
for unit in "$SERVICE" "$TIMER"; do
  cmp "$UNITS/$unit" "/etc/systemd/system/$unit"
done
echo "PASS: AlphaESS source and systemd units match Git; timer NOT started."
echo "Backup: $BACKUP"
