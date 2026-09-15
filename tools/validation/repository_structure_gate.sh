#!/usr/bin/env bash
set -euo pipefail

BASE_REF="${1:-}"
STRUCTURE_DOC="docs/architecture/repository-structure.md"

fail() { echo "REPOSITORY STRUCTURE GATE: FAIL: $*" >&2; exit 1; }
pass() { echo "REPOSITORY STRUCTURE GATE: PASS: $*"; }

[[ -f "$STRUCTURE_DOC" ]] || fail "$STRUCTURE_DOC missing"
grep -q 'Touch it, place it correctly' "$STRUCTURE_DOC" || fail "canonical placement rule missing"
grep -q 'services/' "$STRUCTURE_DOC" || fail "target services boundary missing"

if [[ -z "$BASE_REF" ]]; then
  pass "canonical repository-structure policy present (no comparison base supplied)"
  exit 0
fi

git rev-parse --verify "$BASE_REF^{commit}" >/dev/null 2>&1 || fail "base ref $BASE_REF is not a commit"
ADDED="$(git diff --diff-filter=A --name-only "$BASE_REF"..HEAD)"

if printf '%s\n' "$ADDED" | grep -Eq '^src/pi/'; then
  echo "New files added below legacy src/pi/:" >&2
  printf '%s\n' "$ADDED" | grep -E '^src/pi/' >&2 || true
  fail "new Pi source must use the target structure under services/pi/ (or another target area defined by repository-structure.md)"
fi

INVALID_PI="$(printf '%s\n' "$ADDED" | grep -E '^services/pi/' | grep -Ev '^services/pi/(planner|control|state|api|integrations|history)/' || true)"
if [[ -n "$INVALID_PI" ]]; then
  echo "Files added outside documented services/pi domains:" >&2
  printf '%s\n' "$INVALID_PI" >&2
  fail "update repository-structure.md deliberately before introducing a new Pi service domain"
fi

DOC_CODE="$(printf '%s\n' "$ADDED" | grep -E '^docs/.*\.(py|pyw|js|mjs|cjs|ts|tsx|sh|service|timer)$' || true)"
if [[ -n "$DOC_CODE" ]]; then
  echo "Executable/runtime-looking files added below docs/:" >&2
  printf '%s\n' "$DOC_CODE" >&2
  fail "production/runtime implementation must live outside docs/; use tests/ or tools/ for intentional examples/validation"
fi

pass "new files respect canonical target-structure boundaries"
