#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOC="docs/architecture/CURRENT-EMS-STATE.md"
POLICY="src/pi/ems-runtime/planner/contract-policy.json"
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

python3 - "$POLICY" <<'PY'
import json, sys
p = json.load(open(sys.argv[1]))
errors = []
if p.get("productionContractMode") != "FIXED":
    errors.append("productionContractMode must be FIXED")
if p.get("productionContractId") != "ENGIE_3Y_2026_2029":
    errors.append("productionContractId must be ENGIE_3Y_2026_2029")
d = p.get("dynamicPricing") or {}
if d.get("enabledForProduction") is not False:
    errors.append("dynamic pricing must be disabled for production")
if d.get("automaticFallbackAllowed") is not False:
    errors.append("dynamic fallback must be disabled")
s = p.get("safety") or {}
if s.get("failClosed") is not True:
    errors.append("failClosed must be true")
if s.get("automaticContractModeSwitchAllowed") is not False:
    errors.append("automatic contract-mode switching must be disabled")
if errors:
    raise SystemExit("; ".join(errors))
PY
pass "contract-policy invariants valid"

grep -q 'Canonical current-state document' "$DOC" || fail "canonical document marker missing"
grep -q 'productionContractMode = FIXED' "$DOC" || fail "FIXED contract architecture rule missing from canonical document"
grep -q 'dynamic pricing is \*\*disabled for production\*\*' "$DOC" || fail "dynamic-production prohibition missing from canonical document"
grep -q 'fail closed' "$DOC" || fail "fail-closed architecture rule missing from canonical document"
pass "canonical architecture invariants documented"

if [[ -n "$BASE_REF" ]]; then
  git rev-parse --verify "$BASE_REF^{commit}" >/dev/null 2>&1 || fail "base ref $BASE_REF is not a commit"
  CHANGED="$(git diff --name-only "$BASE_REF"..HEAD)"

  if printf '%s\n' "$CHANGED" | grep -Eq '^(src/pi/ems-runtime/|deploy/systemd/|scripts/deploy_ems_pi\.sh$|scripts/ems_architecture_gate\.sh$)'; then
    if ! printf '%s\n' "$CHANGED" | grep -Fxq "$DOC"; then
      echo "Architecture-sensitive files changed since $BASE_REF:" >&2
      printf '%s\n' "$CHANGED" | grep -E '^(src/pi/ems-runtime/|deploy/systemd/|scripts/deploy_ems_pi\.sh$|scripts/ems_architecture_gate\.sh$)' >&2 || true
      fail "$DOC was not updated in the same release range"
    fi
    pass "architecture-sensitive changes include canonical document update"
  else
    pass "no architecture-sensitive changes in release range"
  fi
fi

pass "all checks completed"
