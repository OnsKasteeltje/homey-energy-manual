#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="/home/jeroen/ems/runtime"
SOURCE="$REPO/src/pi/ems-runtime"
TARGET_HISTORY_SOURCE="$REPO/services/pi/history"
TARGET_HISTORY_RUNTIME="$RUNTIME/history"
TARGET_HONEYWELL_SOURCE="$REPO/services/pi/integrations/honeywell"
TARGET_HONEYWELL_RUNTIME="$RUNTIME/tools/honeywell"
PERFORMANCE_COMMAND="/usr/local/bin/ems-performance"
SYSTEMD="$REPO/deploy/systemd"

echo "=== EMS PI DRIFT CHECK ==="
echo "Repo:      $REPO"
echo "Source:    $SOURCE"
echo "History:   $TARGET_HISTORY_SOURCE"
echo "Honeywell: $TARGET_HONEYWELL_SOURCE"
echo "Runtime:   $RUNTIME"
echo

FAIL=0

echo "=== SOURCE FILES ==="
while IFS= read -r rel; do
    src="$SOURCE/$rel"
    dst="$RUNTIME/$rel"

    if [[ ! -f "$dst" ]]; then
        echo "MISSING: $rel"
        FAIL=1
        continue
    fi

    if ! cmp -s "$src" "$dst"; then
        echo "DRIFT:   $rel"
        FAIL=1
    fi
done < <(
    cd "$SOURCE" && find . -type f \
        -not -path '*/__pycache__/*' \
        -not -name '*.pyc' \
        -printf '%P\n' | sort
)

echo
echo "=== TARGET-STRUCTURE HISTORY FILES ==="
while IFS= read -r rel; do
    src="$TARGET_HISTORY_SOURCE/$rel"
    dst="$TARGET_HISTORY_RUNTIME/$rel"

    if [[ ! -f "$dst" ]]; then
        echo "MISSING: history/$rel"
        FAIL=1
        continue
    fi

    if ! cmp -s "$src" "$dst"; then
        echo "DRIFT:   history/$rel"
        FAIL=1
    fi
done < <(
    cd "$TARGET_HISTORY_SOURCE" && find . -type f \
        -not -path '*/__pycache__/*' \
        -not -name '*.pyc' \
        -printf '%P\n' | sort
)

echo
echo "=== TARGET-STRUCTURE HONEYWELL FILES ==="
if [[ ! -d "$TARGET_HONEYWELL_RUNTIME" ]]; then
    echo "MISSING: $TARGET_HONEYWELL_RUNTIME"
    FAIL=1
else
    while IFS= read -r rel; do
        src="$TARGET_HONEYWELL_SOURCE/$rel"
        dst="$TARGET_HONEYWELL_RUNTIME/$rel"

        if [[ ! -f "$dst" ]]; then
            echo "MISSING: tools/honeywell/$rel"
            FAIL=1
            continue
        fi

        if ! cmp -s "$src" "$dst"; then
            echo "DRIFT:   tools/honeywell/$rel"
            FAIL=1
        fi
    done < <(
        cd "$TARGET_HONEYWELL_SOURCE" && find . -type f \
            -not -path './.venv/*' \
            -not -path './cache/*' \
            -not -path './output/*' \
            -not -path './config/account.env' \
            -not -path '*/__pycache__/*' \
            -not -name '*.pyc' \
            -printf '%P\n' | sort
    )
fi

echo
echo "=== EMS PERFORMANCE COMMAND ==="
if [[ ! -L "$PERFORMANCE_COMMAND" ]]; then
    echo "MISSING: $PERFORMANCE_COMMAND symlink"
    FAIL=1
elif [[ "$(readlink -f "$PERFORMANCE_COMMAND")" != "$TARGET_HISTORY_RUNTIME/ems_performance.py" ]]; then
    echo "DRIFT:   $PERFORMANCE_COMMAND -> $(readlink -f "$PERFORMANCE_COMMAND")"
    FAIL=1
elif [[ ! -x "$TARGET_HISTORY_RUNTIME/ems_performance.py" ]]; then
    echo "NOT EXECUTABLE: $TARGET_HISTORY_RUNTIME/ems_performance.py"
    FAIL=1
else
    echo "PASS: ems-performance command installed"
fi

echo
echo "=== SYSTEMD FILES ==="
for src in "$SYSTEMD"/*; do
    name="$(basename "$src")"
    dst="/etc/systemd/system/$name"

    if [[ ! -f "$dst" ]]; then
        echo "MISSING: $name"
        FAIL=1
        continue
    fi

    if ! cmp -s "$src" "$dst"; then
        echo "DRIFT:   $name"
        FAIL=1
    fi
done

echo
if [[ "$FAIL" -eq 0 ]]; then
    echo "PASS: EMS Pi runtime matches Git source"
    exit 0
else
    echo "FAIL: EMS Pi runtime drift detected"
    exit 1
fi
