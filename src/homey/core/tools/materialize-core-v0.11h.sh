#!/usr/bin/env bash
set -euo pipefail

BASE_COMMIT='bd4edecc219c035399a18671429c2cf24eaea1be'
BASE_PATH='src/homey/core/core-v0.11g.live-homey.js'
EXPECTED_BASE_BLOB='0bdd1fd7228cddcd2c5331df1dbbcfcaa3aab715'
PATCH_PATH='src/homey/core/patches/core-v0.11h-ww-thermostat-low-power.patch'
OUT_PATH='src/homey/core/core-v0.11h.candidate-homey.js'

ROOT="$(git rev-parse --show-toplevel)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/src/homey/core"

git -C "$ROOT" show "$BASE_COMMIT:$BASE_PATH" > "$TMP/$BASE_PATH"
ACTUAL_BASE_BLOB="$(git hash-object "$TMP/$BASE_PATH")"
if [[ "$ACTUAL_BASE_BLOB" != "$EXPECTED_BASE_BLOB" ]]; then
  echo "FAIL: immutable v0.11g baseline blob mismatch: $ACTUAL_BASE_BLOB" >&2
  exit 10
fi

(
  cd "$TMP"
  patch --batch --forward -p1 < "$ROOT/$PATCH_PATH"
)

if [[ ! -f "$TMP/$OUT_PATH" ]]; then
  echo "FAIL: patch did not materialize $OUT_PATH" >&2
  exit 11
fi

# Candidate identity and surgical-gate checks.
grep -Fq "v0.11h" "$TMP/$OUT_PATH"
grep -Fq "EM2_CORE_STATE_V0.11h" "$TMP/$OUT_PATH"
grep -Fq "THERMOSTAT_VERIFY_LOW_W=100" "$TMP/$OUT_PATH"
grep -Fq "thermostatVerifyLowPower" "$TMP/$OUT_PATH"
grep -Fq "THERMOSTAT_VERIFY_ABORT" "$TMP/$OUT_PATH"

mkdir -p "$ROOT/$(dirname "$OUT_PATH")"
cp "$TMP/$OUT_PATH" "$ROOT/$OUT_PATH"

CANDIDATE_BLOB="$(git hash-object "$ROOT/$OUT_PATH")"
echo "PASS: immutable base $BASE_COMMIT / $EXPECTED_BASE_BLOB"
echo "PASS: materialized $OUT_PATH"
echo "candidate_blob=$CANDIDATE_BLOB"
