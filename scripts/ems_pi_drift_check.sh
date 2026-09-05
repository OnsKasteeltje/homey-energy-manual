#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="/home/jeroen/ems/runtime"
SOURCE="$REPO/src/pi/ems-runtime"
SYSTEMD="$REPO/deploy/systemd"

echo "=== EMS PI DRIFT CHECK ==="
echo "Repo:    $REPO"
echo "Source:  $SOURCE"
echo "Runtime: $RUNTIME"
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
done < <(cd "$SOURCE" && find . -type f -printf '%P\n' | sort)

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
