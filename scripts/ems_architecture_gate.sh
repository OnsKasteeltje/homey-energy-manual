#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOC="docs/architecture/CURRENT-EMS-STATE.md"
POLICY="src/pi/ems-runtime/planner/contract-policy.json"
STATE_INGEST="src/pi/ems-runtime/status-api/state_ingest.py"
HISTORY_ARCHIVE="src/pi/ems-runtime/status-api/history_archive.py"
PLANNER_HISTORY="services/pi/history/archive_planner_snapshot.py"
PERFORMANCE="services/pi/history/ems_performance.py"
HONEYWELL="services/pi/integrations/honeywell"
FORECAST_CHAIN="deploy/systemd/ems-forecast-chain.service"
BASE_REF="${1:-}"

fail() {
  echo "ARCHITECTURE GATE: FAIL: $*" >&2
  exit 1
}

pass() {
  echo "ARCHITECTURE GATE: PASS: $*"
}

cd "$REPO"

[[ -f "$DOC" ]] || fail "$DOC missing"
[[ -f "$POLICY" ]] || fail "$POLICY missing"
[[ -f "$STATE_INGEST" ]] || fail "$STATE_INGEST missing"
[[ -f "$HISTORY_ARCHIVE" ]] || fail "$HISTORY_ARCHIVE missing"
[[ -f "$PLANNER_HISTORY" ]] || fail "$PLANNER_HISTORY missing"
[[ -f "$PERFORMANCE" ]] || fail "$PERFORMANCE missing"
[[ -d "$HONEYWELL" ]] || fail "$HONEYWELL missing"
[[ -f "$FORECAST_CHAIN" ]] || fail "$FORECAST_CHAIN missing"

python3 - "$POLICY" <<'PY'
import json, sys
p = json.load(open(sys.argv[1]))
errors = []
if p.get("productionContractMode") != "FIXED": errors.append("productionContractMode must be FIXED")
if p.get("productionContractId") != "ENGIE_3Y_2026_2029": errors.append("productionContractId must be ENGIE_3Y_2026_2029")
d = p.get("dynamicPricing") or {}
if d.get("enabledForProduction") is not False: errors.append("dynamic pricing must be disabled for production")
if d.get("automaticFallbackAllowed") is not False: errors.append("dynamic fallback must be disabled")
s = p.get("safety") or {}
if s.get("failClosed") is not True: errors.append("failClosed must be true")
if s.get("automaticContractModeSwitchAllowed") is not False: errors.append("automatic contract-mode switching must be disabled")
if errors: raise SystemExit("; ".join(errors))
PY
pass "contract-policy invariants valid"

grep -q 'Canonical current-state document' "$DOC" || fail "canonical document marker missing"
grep -q 'productionContractMode = FIXED' "$DOC" || fail "FIXED contract architecture rule missing from canonical document"
grep -q 'dynamic pricing is \*\*disabled for production\*\*' "$DOC" || fail "dynamic-production prohibition missing from canonical document"
grep -q 'fail closed' "$DOC" || fail "fail-closed architecture rule missing from canonical document"
pass "canonical architecture invariants documented"

grep -q 'from history_archive import archive_state_history' "$STATE_INGEST" || fail "state ingest does not archive accepted Homey pushes"
grep -q 'archive_state_history(payload)' "$STATE_INGEST" || fail "state history archive hook missing"
grep -q 'ems-history.sqlite' "$HISTORY_ARCHIVE" || fail "history archive target is not canonical SQLite"
pass "Homey push-fed local history archive present"

grep -q 'planner-history.sqlite' "$PLANNER_HISTORY" || fail "planner decision history target missing"
grep -q 'PLAN_EMBEDDED_DECISION_OUTPUT' "$PLANNER_HISTORY" || fail "planner history does not declare planner-owned frozen context"
if grep -Eq '^[[:space:]]*(STATE_FILE|WW_FILE)[[:space:]]*=|load\([[:space:]]*(STATE_FILE|WW_FILE)[[:space:]]*\)' "$PLANNER_HISTORY"; then
  fail "planner decision history must not re-read mutable live state after planning"
fi
grep -q '/home/jeroen/ems/runtime/history/archive_planner_snapshot.py' "$FORECAST_CHAIN" || fail "forecast chain does not archive hardened planner decisions"
grep -q 'services/pi/history' scripts/deploy_ems_pi.sh || fail "target-structure Pi history source is not deployed"
grep -q 'TARGET-STRUCTURE HISTORY FILES' scripts/ems_pi_drift_check.sh || fail "target-structure Pi history source is not drift-checked"
pass "planner decision history uses atomic planner-owned context"

grep -q 'EMS_PI_DAY_PERFORMANCE_V0.1' "$PERFORMANCE" || fail "standard EMS performance report schema missing"
grep -q 'ems-history.sqlite' "$PERFORMANCE" || fail "EMS performance command does not use canonical measurement history"
grep -q 'planner-history.sqlite' "$PERFORMANCE" || fail "EMS performance command does not use planner replay history"
grep -q 'constrainedOptimumAvailable' "$PERFORMANCE" || fail "EMS performance report must distinguish constrained optimum from upper bound"
grep -q '/usr/local/bin/ems-performance' scripts/deploy_ems_pi.sh || fail "ems-performance command is not installed by deployment"
grep -q 'EMS PERFORMANCE COMMAND' scripts/ems_pi_drift_check.sh || fail "ems-performance installation is not drift-checked"
pass "standardized read-only EMS performance command present"

grep -q 'services/pi/integrations/honeywell' scripts/deploy_ems_pi.sh || fail "Honeywell target-structure source is not deployed"
grep -q "--exclude='.venv/'" scripts/deploy_ems_pi.sh || fail "Honeywell local virtualenv is not protected during deployment"
grep -q 'TARGET-STRUCTURE HONEYWELL FILES' scripts/ems_pi_drift_check.sh || fail "Honeywell target-structure source is not drift-checked"
grep -q "-not -path './.venv/\*'" scripts/ems_pi_drift_check.sh || fail "Honeywell local virtualenv is not excluded from drift validation"
pass "Honeywell target-structure deployment preserves host-local runtime state"

for legacy_unit in \
  deploy/systemd/ems-day-history.service \
  deploy/systemd/ems-day-history.timer \
  deploy/systemd/ems-homey-insights.service \
  deploy/systemd/ems-homey-insights.timer \
  deploy/systemd/ems-pi-control-publish.service \
  deploy/systemd/ems-pi-control-publish.timer; do
  [[ ! -e "$legacy_unit" ]] || fail "legacy production unit must not be deployable: $legacy_unit"
done
pass "legacy Homey polling/control-push units absent from production deploy set"

if [[ -n "$BASE_REF" ]]; then
  git rev-parse --verify "$BASE_REF^{commit}" >/dev/null 2>&1 || fail "base ref $BASE_REF is not a commit"
  CHANGED="$(git diff --name-only "$BASE_REF"..HEAD)"

  if printf '%s\n' "$CHANGED" | grep -Eq '^(src/pi/ems-runtime/|services/pi/|deploy/systemd/|scripts/deploy_ems_pi\.sh$|scripts/ems_architecture_gate\.sh$|scripts/ems_pi_drift_check\.sh$)'; then
    if ! printf '%s\n' "$CHANGED" | grep -Fxq "$DOC"; then
      echo "Architecture-sensitive files changed since $BASE_REF:" >&2
      printf '%s\n' "$CHANGED" | grep -E '^(src/pi/ems-runtime/|services/pi/|deploy/systemd/|scripts/deploy_ems_pi\.sh$|scripts/ems_architecture_gate\.sh$|scripts/ems_pi_drift_check\.sh$)' >&2 || true
      fail "$DOC was not updated in the same release range"
    fi
    pass "architecture-sensitive changes include canonical document update"
  else
    pass "no architecture-sensitive changes in release range"
  fi
fi

pass "all checks completed"
