#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="/home/jeroen/ems/runtime"
SOURCE="$REPO/src/pi/ems-runtime"
TARGET_HISTORY_SOURCE="$REPO/services/pi/history"
TARGET_HISTORY_RUNTIME="$RUNTIME/history"
TARGET_HONEYWELL_SOURCE="$REPO/services/pi/integrations/honeywell"
TARGET_HONEYWELL_RUNTIME="$RUNTIME/tools/honeywell"
TARGET_HOMEY_INGRESS_FILE="$REPO/services/pi/integrations/homey/ingress/state_ingest.py"
TARGET_HOMEY_EGRESS_SOURCE="$REPO/services/pi/integrations/homey/egress"
TARGET_HOMEY_EGRESS_RUNTIME="$RUNTIME/homey-deploy"
TARGET_STATUS_SOURCE="$REPO/services/pi/api/status"
TARGET_STATUS_RUNTIME="$RUNTIME/status-api"
PERFORMANCE_COMMAND="/usr/local/bin/ems-performance"
SYSTEMD="$REPO/deploy/systemd"
BACKUP_ROOT="/home/jeroen/ems/backup"
DEPLOY_MARKER="/home/jeroen/ems/data/deployed-git-commit"

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

BASE_REF=""
if [[ -s "$DEPLOY_MARKER" ]]; then
    BASE_REF="$(tr -d '[:space:]' < "$DEPLOY_MARKER")"
    if ! git -C "$REPO" rev-parse --verify "$BASE_REF^{commit}" >/dev/null 2>&1; then
        echo "ERROR: deployment marker does not contain a valid commit: $BASE_REF"
        exit 1
    fi
else
    echo "NOTE: no deployment marker yet; architecture release-range check starts after this deployment."
fi

echo "=== ARCHITECTURE GATE ==="
if [[ -n "$BASE_REF" ]]; then
    bash "$REPO/scripts/ems_architecture_gate.sh" "$BASE_REF"
else
    bash "$REPO/scripts/ems_architecture_gate.sh"
fi

echo
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
        <(cd "$SOURCE" && find . -type f \
            -not -path './status-api/*' \
            -not -path './tools/honeywell/*' \
            -not -path './homey-deploy/publish_pi_control_intent.py' \
            -printf '%P\n' | sort) \
        <(cd "$RUNTIME" && find . -type f \
            -not -path './data/*' \
            -not -path './logs/*' \
            -not -path './history/*' \
            -not -path './status-api/*' \
            -not -path './tools/honeywell/*' \
            -not -path './homey-deploy/publish_pi_control_intent.py' \
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

mkdir -p "$TARGET_HISTORY_RUNTIME"
HISTORY_UNMANAGED="$(
    diff -u \
        <(cd "$TARGET_HISTORY_SOURCE" && find . -type f -printf '%P\n' | sort) \
        <(cd "$TARGET_HISTORY_RUNTIME" && find . -type f \
            -not -path '*/__pycache__/*' \
            -not -name '*.pyc' \
            -printf '%P\n' | sort) \
        || true
)"

if echo "$HISTORY_UNMANAGED" | grep -E '^\\+' | grep -v '^+++ ' >/dev/null; then
    echo "ERROR: unmanaged files exist in runtime/history."
    echo "Deployment aborted to prevent accidental deletion."
    echo
    echo "$HISTORY_UNMANAGED"
    exit 1
fi

mkdir -p "$TARGET_HONEYWELL_RUNTIME"
HONEYWELL_UNMANAGED="$(
    diff -u \
        <(cd "$TARGET_HONEYWELL_SOURCE" && find . -type f -printf '%P\n' | sort) \
        <(cd "$TARGET_HONEYWELL_RUNTIME" && find . -type f \
            -not -path './.venv/*' \
            -not -path './cache/*' \
            -not -path './output/*' \
            -not -path './config/account.env' \
            -not -path '*/__pycache__/*' \
            -not -name '*.pyc' \
            -printf '%P\n' | sort) \
        || true
)"

if echo "$HONEYWELL_UNMANAGED" | grep -E '^\\+' | grep -v '^+++ ' >/dev/null; then
    echo "ERROR: unmanaged files exist in runtime/tools/honeywell."
    echo "Deployment aborted to protect Honeywell runtime state and credentials."
    echo
    echo "$HONEYWELL_UNMANAGED"
    exit 1
fi

if [[ ! -f "$TARGET_HOMEY_INGRESS_FILE" ]]; then
    echo "ERROR: Homey ingress source is missing."
    echo "Deployment aborted to protect the Homey -> Pi state path."
    exit 1
fi

mkdir -p "$TARGET_HOMEY_EGRESS_RUNTIME"
if [[ ! -f "$TARGET_HOMEY_EGRESS_SOURCE/publish_pi_control_intent.py" ]]; then
    echo "ERROR: Homey egress source is missing."
    echo "Deployment aborted to protect the Pi -> Homey control path."
    exit 1
fi

mkdir -p "$TARGET_STATUS_RUNTIME"
STATUS_UNMANAGED="$(
    diff -u \
        <(cd "$TARGET_STATUS_SOURCE" && find . -type f \
            -not -path './state_ingest.py' \
            -printf '%P\n' | sort) \
        <(cd "$TARGET_STATUS_RUNTIME" && find . -type f \
            -not -path './state_ingest.py' \
            -not -path '*/__pycache__/*' \
            -not -name '*.pyc' \
            -printf '%P\n' | sort) \
        || true
)"

if echo "$STATUS_UNMANAGED" | grep -E '^\\+' | grep -v '^+++ ' >/dev/null; then
    echo "ERROR: unmanaged files exist in runtime/status-api."
    echo "Deployment aborted to prevent accidental deletion."
    echo
    echo "$STATUS_UNMANAGED"
    exit 1
fi

echo "PASS: runtime contains no unmanaged source files"

echo
echo "=== DEPLOY RUNTIME SOURCE ==="
rsync -a --delete \
    --exclude='data/' \
    --exclude='logs/' \
    --exclude='history/' \
    --exclude='status-api/' \
    --exclude='tools/honeywell/' \
    --exclude='homey-deploy/publish_pi_control_intent.py' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='*.bak*' \
    --exclude='*.before-*' \
    "$SOURCE/" "$RUNTIME/"

mkdir -p "$TARGET_HISTORY_RUNTIME"
rsync -a --delete \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "$TARGET_HISTORY_SOURCE/" "$TARGET_HISTORY_RUNTIME/"

mkdir -p "$TARGET_HONEYWELL_RUNTIME"
rsync -a --delete \
    --exclude='.venv/' \
    --exclude='cache/' \
    --exclude='output/' \
    --exclude='config/account.env' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "$TARGET_HONEYWELL_SOURCE/" "$TARGET_HONEYWELL_RUNTIME/"

mkdir -p "$TARGET_HOMEY_EGRESS_RUNTIME"
cp -a \
    "$TARGET_HOMEY_EGRESS_SOURCE/publish_pi_control_intent.py" \
    "$TARGET_HOMEY_EGRESS_RUNTIME/publish_pi_control_intent.py"

mkdir -p "$TARGET_STATUS_RUNTIME"
rsync -a --delete \
    --exclude='state_ingest.py' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "$TARGET_STATUS_SOURCE/" "$TARGET_STATUS_RUNTIME/"
cp -a "$TARGET_HOMEY_INGRESS_FILE" "$TARGET_STATUS_RUNTIME/state_ingest.py"

chmod 0755 "$TARGET_HISTORY_RUNTIME/ems_performance.py"
ln -sfn "$TARGET_HISTORY_RUNTIME/ems_performance.py" "$PERFORMANCE_COMMAND"

echo
echo "=== DEPLOY SYSTEMD ==="
cp -a "$SYSTEMD/"* /etc/systemd/system/

echo
echo "=== VALIDATE ==="
"$REPO/scripts/ems_pi_drift_check.sh"

echo
echo "=== SYSTEMD RELOAD ==="
systemctl daemon-reload

mkdir -p "$(dirname "$DEPLOY_MARKER")"
git -C "$REPO" rev-parse HEAD > "$DEPLOY_MARKER"

echo
echo "=== DEPLOYMENT COMPLETE ==="
echo "Release commit: $(git -C "$REPO" rev-parse --short HEAD)"
echo "Backup: $BACKUP"
echo "Deployment marker: $(cat "$DEPLOY_MARKER")"
echo "Performance command: $PERFORMANCE_COMMAND"
echo
echo "NOTE: Services were NOT restarted by this script."
