#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="/home/jeroen/ems/runtime"
SOURCE="$REPO/src/pi/ems-runtime"
TARGET_HISTORY_SOURCE="$REPO/services/pi/history"
TARGET_HISTORY_RUNTIME="$RUNTIME/history"
TARGET_FORECAST_SOURCE="$REPO/services/pi/forecast"
TARGET_FORECAST_RUNTIME="$RUNTIME/forecast"

TARGET_WW_SOURCE="$REPO/services/pi/planner/warm-water"
TARGET_WW_RUNTIME="$RUNTIME/planner/warm-water"
TARGET_HONEYWELL_SOURCE="$REPO/services/pi/integrations/honeywell"
TARGET_HONEYWELL_RUNTIME="$RUNTIME/tools/honeywell"
TARGET_HOMEY_INGRESS_SOURCE="$REPO/services/pi/integrations/homey/ingress"
TARGET_HOMEY_EGRESS_SOURCE="$REPO/services/pi/integrations/homey/egress"
TARGET_HOMEY_EGRESS_RUNTIME="$RUNTIME/homey-deploy"
TARGET_STATUS_SOURCE="$REPO/services/pi/api/status"
TARGET_STATUS_RUNTIME="$RUNTIME/status-api"
TARGET_WEB_DATA_SOURCE="$REPO/services/pi/api/web-data"
TARGET_WEB_DATA_RUNTIME="$RUNTIME/web-data-api"
TARGET_ANALYSIS_SOURCE="$REPO/services/pi/api/analysis"
TARGET_ANALYSIS_RUNTIME="$RUNTIME/analysis-api"
TARGET_HEALTH_SOURCE="$REPO/services/pi/health"
TARGET_HEALTH_RUNTIME="$RUNTIME/health"
PERFORMANCE_COMMAND="/usr/local/bin/ems-performance"
CONSTRAINED_REPLAY_COMMAND="/usr/local/bin/ems-constrained-replay"
HEALTH_COMMAND="/usr/local/bin/ems-health"
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
            -printf '%P\n' | sort) \
        <(cd "$RUNTIME" && find . -type f \
            -not -path './data/*' \
            -not -path './logs/*' \
            -not -path './history/*' \
            -not -path './forecast/*' \
            -not -path './thermal/*' \
            -not -path './planner/warm-water/*' \
            -not -path './status-api/*' \
            -not -path './web-data-api/*' \
            -not -path './analysis-api/*' \
            -not -path './health/*' \
            -not -path './tools/honeywell/*' \
            -not -path './homey-deploy/*' \
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

mkdir -p "$TARGET_FORECAST_RUNTIME"
FORECAST_UNMANAGED="$(
    diff -u \
        <(cd "$TARGET_FORECAST_SOURCE" && find . -type f -printf '%P\n' | sort) \
        <(cd "$TARGET_FORECAST_RUNTIME" && find . -type f \
            -not -path '*/__pycache__/*' \
            -not -name '*.pyc' \
            -printf '%P\n' | sort) \
        || true
)"

if echo "$FORECAST_UNMANAGED" | grep -E '^\\+' | grep -v '^+++ ' >/dev/null; then
    echo "ERROR: unmanaged files exist in runtime/forecast."
    echo "Deployment aborted to prevent accidental deletion."
    echo
    echo "$FORECAST_UNMANAGED"
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

for ingress_file in state_ingest.py ev_control_ingest.py quooker_evidence_ingest.py; do
    if [[ ! -f "$TARGET_HOMEY_INGRESS_SOURCE/$ingress_file" ]]; then
        echo "ERROR: Homey ingress source is missing: $ingress_file"
        echo "Deployment aborted to protect the Homey -> Pi state/observability path."
        exit 1
    fi
done

mkdir -p "$TARGET_HOMEY_EGRESS_RUNTIME"
for egress_file in publish_pi_control_intent.py publish_heating_control_intent_shadow.py; do
    if [[ ! -f "$TARGET_HOMEY_EGRESS_SOURCE/$egress_file" ]]; then
        echo "ERROR: Homey egress source is missing: $egress_file"
        echo "Deployment aborted to protect the Pi -> Homey control path."
        exit 1
    fi
done

mkdir -p "$TARGET_STATUS_RUNTIME"
STATUS_UNMANAGED="$(
    diff -u \
        <(cd "$TARGET_STATUS_SOURCE" && find . -type f \
            -printf '%P\n' | sort) \
        <(cd "$TARGET_STATUS_RUNTIME" && find . -type f \
            -not -path './state_ingest.py' \
            -not -path './ev_control_ingest.py' \
            -not -path './quooker_evidence_ingest.py' \
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


mkdir -p "$TARGET_WEB_DATA_RUNTIME"
WEB_DATA_UNMANAGED="$(
    diff -u \
        <(cd "$TARGET_WEB_DATA_SOURCE" && find . -type f -printf '%P\n' | sort) \
        <(cd "$TARGET_WEB_DATA_RUNTIME" && find . -type f \
            -not -path '*/__pycache__/*' \
            -not -name '*.pyc' \
            -printf '%P\n' | sort) \
        || true
)"
if echo "$WEB_DATA_UNMANAGED" | grep -E '^\+' | grep -v '^+++ ' >/dev/null; then
    echo "ERROR: unmanaged files exist in runtime/web-data-api."
    echo "Deployment aborted to prevent accidental deletion."
    echo
    echo "$WEB_DATA_UNMANAGED"
    exit 1
fi

mkdir -p "$TARGET_ANALYSIS_RUNTIME"
ANALYSIS_UNMANAGED="$(
    diff -u \
        <(cd "$TARGET_ANALYSIS_SOURCE" && find . -type f -printf '%P\n' | sort) \
        <(cd "$TARGET_ANALYSIS_RUNTIME" && find . -type f \
            -not -path '*/__pycache__/*' \
            -not -name '*.pyc' \
            -printf '%P\n' | sort) \
        || true
)"
if echo "$ANALYSIS_UNMANAGED" | grep -E '^\+' | grep -v '^+++ ' >/dev/null; then
    echo "ERROR: unmanaged files exist in runtime/analysis-api."
    echo "Deployment aborted to prevent accidental deletion."
    echo
    echo "$ANALYSIS_UNMANAGED"
    exit 1
fi

mkdir -p "$TARGET_HEALTH_RUNTIME"
HEALTH_UNMANAGED="$(
    diff -u \
        <(cd "$TARGET_HEALTH_SOURCE" && find . -type f -printf '%P\n' | sort) \
        <(cd "$TARGET_HEALTH_RUNTIME" && find . -type f \
            -not -path '*/__pycache__/*' \
            -not -name '*.pyc' \
            -printf '%P\n' | sort) \
        || true
)"
if echo "$HEALTH_UNMANAGED" | grep -E '^\+' | grep -v '^+++ ' >/dev/null; then
    echo "ERROR: unmanaged files exist in runtime/health."
    echo "Deployment aborted to prevent accidental deletion."
    echo
    echo "$HEALTH_UNMANAGED"
    exit 1
fi

echo "PASS: runtime contains no unmanaged source files"

echo
echo "=== DEPLOY RUNTIME SOURCE ==="
# tools/, homey-deploy/ and status-api/ are managed separately below.
# thermal/ contains derived operational artifacts (including quatt-current.json)
# produced by target-structure integrations and is not repository-managed source.
# Exclude these complete directories so rsync --delete never removes protected
# runtime state or emits misleading "cannot delete non-empty directory" messages.
rsync -a --delete \
    --exclude='data/' \
    --exclude='logs/' \
    --exclude='history/' \
    --exclude='forecast/' \
    --exclude='thermal/' \
    --exclude='status-api/' \
    --exclude='web-data-api/' \
    --exclude='analysis-api/' \
    --exclude='health/' \
    --exclude='tools/' \
    --exclude='homey-deploy/' \
    --exclude='planner/warm-water/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='*.bak*' \
    --exclude='*.before-*' \
    "$SOURCE/" "$RUNTIME/"

mkdir -p "$TARGET_WW_RUNTIME"
rsync -a --delete \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "$TARGET_WW_SOURCE/" "$TARGET_WW_RUNTIME/"

mkdir -p "$TARGET_HISTORY_RUNTIME"
rsync -a --delete \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "$TARGET_HISTORY_SOURCE/" "$TARGET_HISTORY_RUNTIME/"

mkdir -p "$TARGET_FORECAST_RUNTIME"
rsync -a --delete \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "$TARGET_FORECAST_SOURCE/" "$TARGET_FORECAST_RUNTIME/"

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
# Runtime/homey-deploy also contains maintenance tooling. Copy canonical egress
# sources additively so this deploy step never deletes those host-managed tools.
rsync -a \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "$TARGET_HOMEY_EGRESS_SOURCE/" "$TARGET_HOMEY_EGRESS_RUNTIME/"

mkdir -p "$TARGET_STATUS_RUNTIME"
rsync -a --delete \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "$TARGET_STATUS_SOURCE/" "$TARGET_STATUS_RUNTIME/"
cp -a \
    "$TARGET_HOMEY_INGRESS_SOURCE/state_ingest.py" \
    "$TARGET_STATUS_RUNTIME/state_ingest.py"
cp -a \
    "$TARGET_HOMEY_INGRESS_SOURCE/ev_control_ingest.py" \
    "$TARGET_STATUS_RUNTIME/ev_control_ingest.py"
cp -a \
    "$TARGET_HOMEY_INGRESS_SOURCE/quooker_evidence_ingest.py" \
    "$TARGET_STATUS_RUNTIME/quooker_evidence_ingest.py"

mkdir -p "$TARGET_WEB_DATA_RUNTIME"
rsync -a --delete \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "$TARGET_WEB_DATA_SOURCE/" "$TARGET_WEB_DATA_RUNTIME/"

mkdir -p "$TARGET_ANALYSIS_RUNTIME"
rsync -a --delete \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "$TARGET_ANALYSIS_SOURCE/" "$TARGET_ANALYSIS_RUNTIME/"

mkdir -p "$TARGET_HEALTH_RUNTIME"
rsync -a --delete \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "$TARGET_HEALTH_SOURCE/" "$TARGET_HEALTH_RUNTIME/"

chmod 0755 "$TARGET_HISTORY_RUNTIME/ems_performance.py"
ln -sfn "$TARGET_HISTORY_RUNTIME/ems_performance.py" "$PERFORMANCE_COMMAND"
chmod 0755 "$TARGET_HISTORY_RUNTIME/constrained_replay_v0_1.py"
ln -sfn "$TARGET_HISTORY_RUNTIME/constrained_replay_v0_1.py" "$CONSTRAINED_REPLAY_COMMAND"
chmod 0755 "$TARGET_HEALTH_RUNTIME/ems_health.py"
ln -sfn "$TARGET_HEALTH_RUNTIME/ems_health.py" "$HEALTH_COMMAND"

# Remaining script unchanged below this point.
# Deploy all declared production systemd units, validate drift, reload systemd,
# and write the deployment marker exactly as before.

echo
echo "=== DEPLOY SYSTEMD ==="
for f in "$SYSTEMD"/*; do
    cp -a "$f" "/etc/systemd/system/$(basename "$f")"
done

echo
echo "=== VALIDATE ==="
bash "$REPO/scripts/ems_pi_drift_check.sh"

echo
echo "=== SYSTEMD RELOAD ==="
systemctl daemon-reload

COMMIT="$(git -C "$REPO" rev-parse HEAD)"
printf '%s\n' "$COMMIT" > "$DEPLOY_MARKER"

echo
echo "=== DEPLOYMENT COMPLETE ==="
echo "Release commit: ${COMMIT:0:10}"
echo "Backup: $BACKUP"
echo "Deployment marker: $COMMIT"
echo "Performance command: $PERFORMANCE_COMMAND"
echo "Health command: $HEALTH_COMMAND"
echo "NOTE: Services were NOT restarted by this script."
