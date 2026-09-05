#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="/home/jeroen/ems/runtime"
SOURCE="$REPO/src/pi/ems-runtime"
SYSTEMD="$REPO/deploy/systemd"
BACKUP_ROOT="/home/jeroen/ems/backup"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "ERROR: run with sudo"
    exit 1
fi

echo "=== EMS PI DEPLOYMENT ==="
echo "Repository: $REPO"
echo "Commit:     $(git -C "$REPO" rev-parse HEAD)"
echo

if [[ -n "$(git -C "$REPO" status --porcelain)" ]]; then
    echo "ERROR: Git worktree is not clean"
    exit 1
fi

BACKUP="$BACKUP_ROOT/runtime-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"

echo "=== BACKUP ==="
echo "Creating: $BACKUP"

cp -a "$RUNTIME" "$BACKUP/runtime"
for f in "$SYSTEMD"/*; do
    cp -a "/etc/systemd/system/$(basename "$f")" "$BACKUP/" 2>/dev/null || true
done

echo
echo "=== CHECK RUNTIME FOR UNMANAGED FILES ==="

UNMANAGED="$(
    diff -u \
        <(cd "$SOURCE" && find . -type f -printf '%P\n' | sort) \
        <(cd "$RUNTIME" && find . -type f \
            -not -path './data/*' \
            -not -path './logs/*' \
            -not -path '*/__pycache__/*' \
            -not -name '*.pyc' \
            -printf '%P\n' | sort) \
        || true
)"

if echo "$UNMANAGED" | grep -E '^\\+' | grep -v '^+++ ' >/dev/null; then
    echo "ERROR: unmanaged files exist in runtime."
    echo "Deployment aborted to prevent accidental deletion."
    echo
    echo "$UNMANAGED"
    exit 1
fi

echo "PASS: runtime contains no unmanaged source files"

echo
echo "=== DEPLOY RUNTIME SOURCE ==="

rsync -a --delete \
    --exclude='data/' \
    --exclude='logs/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='*.bak*' \
    --exclude='*.before-*' \
    "$SOURCE/" "$RUNTIME/"

echo
echo "=== DEPLOY SYSTEMD ==="

cp -a "$SYSTEMD/"* /etc/systemd/system/

echo
echo "=== VALIDATE ==="

"$REPO/scripts/ems_pi_drift_check.sh"

echo
echo "=== SYSTEMD RELOAD ==="

systemctl daemon-reload

echo
echo "=== DEPLOYMENT COMPLETE ==="
echo "Release commit: $(git -C "$REPO" rev-parse --short HEAD)"
echo "Backup: $BACKUP"
echo
echo "NOTE: Services were NOT restarted by this script."
