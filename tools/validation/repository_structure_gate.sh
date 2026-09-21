#!/usr/bin/env bash
set -euo pipefail

BASE_REF="${1:-}"
STRUCTURE_DOC="docs/architecture/repository-structure.md"
LEGACY_EXCEPTIONS="config/repository/legacy-placement-exceptions.txt"

fail() { echo "REPOSITORY STRUCTURE GATE: FAIL: $*" >&2; exit 1; }
pass() { echo "REPOSITORY STRUCTURE GATE: PASS: $*"; }

[[ -f "$STRUCTURE_DOC" ]] || fail "$STRUCTURE_DOC missing"
grep -q 'Touch it, place it correctly' "$STRUCTURE_DOC" \
  || fail "canonical placement rule missing"
grep -q 'services/' "$STRUCTURE_DOC" \
  || fail "target services boundary missing"

[[ -f "$LEGACY_EXCEPTIONS" ]] \
  || fail "$LEGACY_EXCEPTIONS missing"

if [[ -z "$BASE_REF" ]]; then
  pass "canonical repository-structure policy present (no comparison base supplied)"
  exit 0
fi

git rev-parse --verify "$BASE_REF^{commit}" >/dev/null 2>&1 \
  || fail "base ref $BASE_REF is not a commit"

ADDED="$(git diff --diff-filter=A --name-only "$BASE_REF"..HEAD)"
MODIFIED="$(git diff --diff-filter=M --name-only "$BASE_REF"..HEAD)"

#
# Rule 1:
# New Pi source may never be introduced below legacy src/pi/.
#
NEW_LEGACY="$(printf '%s\n' "$ADDED" | grep -E '^src/pi/' || true)"

if [[ -n "$NEW_LEGACY" ]]; then
  echo "New files added below legacy src/pi/:" >&2
  printf '%s\n' "$NEW_LEGACY" >&2
  fail "new Pi source must use the canonical target structure"
fi

#
# Rule 2:
# Existing legacy Pi files that are modified must either:
# - already be correctly migrated, or
# - have an explicit temporary exception.
#
is_legacy_exception() {
  local file="$1"
  local entry

  while IFS= read -r entry || [[ -n "$entry" ]]; do
    [[ -z "$entry" ]] && continue
    [[ "$entry" =~ ^[[:space:]]*# ]] && continue

    if [[ "$entry" == */ ]]; then
      [[ "$file" == "$entry"* ]] && return 0
    else
      [[ "$file" == "$entry" ]] && return 0
    fi
  done < "$LEGACY_EXCEPTIONS"

  return 1
}

UNAPPROVED_MODIFIED=""
APPROVED_MODIFIED=""

while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  [[ "$file" == src/pi/* ]] || continue

  if is_legacy_exception "$file"; then
    APPROVED_MODIFIED+="${file}"$'\n'
  else
    UNAPPROVED_MODIFIED+="${file}"$'\n'
  fi
done <<< "$MODIFIED"

if [[ -n "$APPROVED_MODIFIED" ]]; then
  echo "Legacy files modified under explicit temporary placement exception:"
  printf '%s' "$APPROVED_MODIFIED"
fi

if [[ -n "$UNAPPROVED_MODIFIED" ]]; then
  echo "Modified legacy Pi files without placement exception:" >&2
  printf '%s' "$UNAPPROVED_MODIFIED" >&2
  fail "Touch it, place it correctly: migrate the file or document a temporary exception"
fi

#
# Rule 3:
# New services/pi files must use a documented service domain.
#
INVALID_PI="$(
  printf '%s\n' "$ADDED" |
    grep -E '^services/pi/' |
    grep -Ev '^services/pi/(planner|forecast|control|state|api|integrations|history)/' ||
    true
)"

if [[ -n "$INVALID_PI" ]]; then
  echo "Files added outside documented services/pi domains:" >&2
  printf '%s\n' "$INVALID_PI" >&2
  fail "update repository-structure.md deliberately before introducing a new Pi service domain"
fi

#
# Rule 4:
# Runtime-looking implementation does not belong below docs/.
#
DOC_CODE="$(
  printf '%s\n' "$ADDED" |
    grep -E '^docs/.*\.(py|pyw|js|mjs|cjs|ts|tsx|sh|service|timer)$' ||
    true
)"

if [[ -n "$DOC_CODE" ]]; then
  echo "Executable/runtime-looking files added below docs/:" >&2
  printf '%s\n' "$DOC_CODE" >&2
  fail "production/runtime implementation must live outside docs/"
fi

pass "repository changes respect canonical target-structure boundaries"
