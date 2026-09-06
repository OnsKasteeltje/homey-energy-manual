#!/usr/bin/env bash
set -u

REPO="/home/jeroen/ems/repo/homey-energy-manual"
RUNTIME="/home/jeroen/ems/runtime"
HEALTH_URL="http://127.0.0.1:3100/health"

PASS=0
FAIL=0

pass() {
    echo "PASS: $1"
    PASS=$((PASS + 1))
}

fail() {
    echo "FAIL: $1"
    FAIL=$((FAIL + 1))
}

echo "========================================"
echo " EMS Pi Deployment Integrity Check"
echo "========================================"

cd "$REPO" || {
    echo "FAIL: cannot enter repository"
    exit 2
}

EXPECTED_REV="$(git rev-parse --short=8 HEAD)"
echo "expected revision: $EXPECTED_REV"
echo

# ------------------------------------------------------------
# 1. Git working tree
# ------------------------------------------------------------

if [ -z "$(git status --short)" ]; then
    pass "Git working tree clean"
else
    fail "Git working tree contains local changes"
    git status --short
fi

# ------------------------------------------------------------
# 2. Source -> runtime Python files
# ------------------------------------------------------------

echo
echo "--- Source / runtime comparison ---"

while IFS= read -r src; do
    rel="${src#"$REPO/src/pi/ems-runtime/"}"
    dst="$RUNTIME/$rel"

    if [ ! -f "$dst" ]; then
        fail "runtime file missing: $rel"
        continue
    fi

    if cmp -s "$src" "$dst"; then
        pass "runtime matches source: $rel"
    else
        fail "runtime differs from source: $rel"
    fi
done < <(
    find "$REPO/src/pi/ems-runtime" \
        -type f \
        -name '*.py' \
        -print | sort
)

# ------------------------------------------------------------
# 3. Canonical planner axis
# ------------------------------------------------------------

echo
echo "--- Planner axis ---"

axis_check="$(
    python3 - <<'PY2'
import json
from pathlib import Path

axis = Path("/home/jeroen/ems/data/planner-axis.json")

try:
    d = json.loads(axis.read_text())
    slots = d.get("slots", [])
    ok = (
        d.get("schema") == "EMS_PI_PLANNER_AXIS_V0.1"
        and len(slots) == 96
        and len(set(slots)) == 96
        and slots == sorted(slots)
    )
    print("ok" if ok else "bad")
except Exception:
    print("bad")
PY2
)"

if [ "$axis_check" = "ok" ]; then
    pass "canonical planner axis valid (96 unique ordered slots)"
else
    fail "canonical planner axis invalid"
fi

# ------------------------------------------------------------
# 4. Status API daemon
# ------------------------------------------------------------

echo
echo "--- Services ---"

status="$(systemctl is-active ems-status-api 2>/dev/null || true)"

if [ "$status" = "active" ]; then
    pass "ems-status-api active"
else
    fail "ems-status-api not active (state=$status)"
fi

# ------------------------------------------------------------
# 5. Oneshot service result
# ------------------------------------------------------------

for service in \
    ems-weather-forecast \
    ems-pv-forecast \
    ems-price-forecast
do
    result="$(systemctl show "$service" \
        --property=Result \
        --value 2>/dev/null || true)"

    if [ "$result" = "success" ]; then
        pass "$service last result=success"
    else
        fail "$service last result=$result"
    fi
done

# ------------------------------------------------------------
# 6. HTTP health endpoint
# ------------------------------------------------------------

echo
echo "--- Health API ---"

health="$(curl -fsS --max-time 5 "$HEALTH_URL" 2>/dev/null || true)"

if [ -n "$health" ]; then
    pass "health endpoint reachable"
else
    fail "health endpoint not reachable"
fi

if [ -n "$health" ]; then
    health_status="$(
        python3 -c '
import json,sys
try:
    d=json.loads(sys.stdin.read())
    print(d.get("status",""))
except Exception:
    print("")
' <<< "$health"
    )"

    if [ "$health_status" = "ok" ]; then
        pass "health overall status=ok"
    else
        fail "health overall status=$health_status"
    fi

    health_revision="$(
        python3 -c '
import json,sys
try:
    d=json.loads(sys.stdin.read())
    print(d.get("git_revision",""))
except Exception:
    print("")
' <<< "$health"
    )"

    if [ "$health_revision" = "$EXPECTED_REV" ]; then
        pass "running API revision matches Git HEAD ($EXPECTED_REV)"
    else
        fail "running API revision mismatch: expected=$EXPECTED_REV actual=$health_revision"
    fi

    for field in \
        pv_forecast_status \
        weather_forecast_status \
        quatt_forecast_status \
        ww_plan_status
    do
        value="$(
            python3 -c "
import json,sys
try:
    d=json.loads(sys.stdin.read())
    print(d.get('$field',''))
except Exception:
    print('')
" <<< "$health"
        )"

        if [ "$value" = "ok" ]; then
            pass "$field=ok"
        else
            fail "$field=$value"
        fi
    done
fi

# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------

echo
echo "========================================"
echo " PASS: $PASS"
echo " FAIL: $FAIL"
echo "========================================"

if [ "$FAIL" -eq 0 ]; then
    echo "DEPLOYMENT INTEGRITY: PASS"
    exit 0
else
    echo "DEPLOYMENT INTEGRITY: FAIL"
    exit 1
fi
