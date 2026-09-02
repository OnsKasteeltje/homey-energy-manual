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

node - "$TMP/$BASE_PATH" "$ROOT/$PATCH_PATH" "$TMP/$OUT_PATH" <<'NODE'
const fs = require('fs');
const [basePath, patchPath, outPath] = process.argv.slice(2);
let source = fs.readFileSync(basePath, 'utf8');
const patch = fs.readFileSync(patchPath, 'utf8');

const lines = patch.split(/\r?\n/);
const replacements = [];
for (let i = 0; i < lines.length - 1; i++) {
  const a = lines[i], b = lines[i + 1];
  if (a.startsWith('-') && !a.startsWith('---') && b.startsWith('+') && !b.startsWith('+++')) {
    replacements.push([a.slice(1), b.slice(1)]);
    i++;
  }
}
if (replacements.length !== 4) {
  throw new Error(`Expected exactly 4 semantic replacement pairs, got ${replacements.length}`);
}

function replaceExactlyOnce(haystack, from, to, label) {
  const first = haystack.indexOf(from);
  if (first < 0) throw new Error(`Missing expected baseline fragment: ${label}`);
  if (haystack.indexOf(from, first + from.length) >= 0) throw new Error(`Baseline fragment is not unique: ${label}`);
  return haystack.slice(0, first) + to + haystack.slice(first + from.length);
}

for (let i = 0; i < replacements.length; i++) {
  source = replaceExactlyOnce(source, replacements[i][0], replacements[i][1], `semantic-${i + 1}`);
}

source = replaceExactlyOnce(
  source,
  '// EM v2 | 00 Core Tick | v0.11g CANDIDATE — Planner v0.5 WW compatibility + existing Tesla headroom',
  '// EM v2 | 00 Core Tick | v0.11h CANDIDATE — WW thermostat low-power gate + Planner v0.5 compatibility + existing Tesla headroom',
  'candidate-header'
);
source = replaceExactlyOnce(
  source,
  "PUB_VERSION='EM2_CORE_STATE_V0.11g'",
  "PUB_VERSION='EM2_CORE_STATE_V0.11h'",
  'publisher-version'
);

if (source.includes("PUB_VERSION='EM2_CORE_STATE_V0.11g'")) throw new Error('Old PUB_VERSION survived materialization');
if (!source.includes('THERMOSTAT_VERIFY_LOW_W=100')) throw new Error('Low-power constant missing');
if (!source.includes('thermostatVerifyLowPower')) throw new Error('Low-power evidence missing');
if (!source.includes("schema:'EM2_CONTROL_WW_V0.11'")) throw new Error('Downstream WW schema changed unexpectedly');

fs.mkdirSync(require('path').dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, source);
NODE

if [[ ! -f "$TMP/$OUT_PATH" ]]; then
  echo "FAIL: materializer did not create $OUT_PATH" >&2
  exit 11
fi

# Candidate identity and surgical-gate checks.
grep -Fq "v0.11h CANDIDATE" "$TMP/$OUT_PATH"
grep -Fq "EM2_CORE_STATE_V0.11h" "$TMP/$OUT_PATH"
grep -Fq "THERMOSTAT_VERIFY_LOW_W=100" "$TMP/$OUT_PATH"
grep -Fq "thermostatVerifyLowPower" "$TMP/$OUT_PATH"
grep -Fq "THERMOSTAT_VERIFY_ABORT" "$TMP/$OUT_PATH"
grep -Fq "schema:'EM2_CONTROL_WW_V0.11'" "$TMP/$OUT_PATH"

mkdir -p "$ROOT/$(dirname "$OUT_PATH")"
cp "$TMP/$OUT_PATH" "$ROOT/$OUT_PATH"

CANDIDATE_BLOB="$(git hash-object "$ROOT/$OUT_PATH")"
echo "PASS: immutable base $BASE_COMMIT / $EXPECTED_BASE_BLOB"
echo "PASS: 4 semantic replacements + 2 identity-only replacements"
echo "PASS: materialized $OUT_PATH"
echo "candidate_blob=$CANDIDATE_BLOB"
