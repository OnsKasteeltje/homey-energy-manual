#!/usr/bin/env bash
set -euo pipefail

SRC="src/homey/planner/energy-plan-24h-v0.4.7.js"
OUT="src/homey/planner/energy-plan-24h-v0.4.8.js"

python3 - "$SRC" "$OUT" <<'PY'
from pathlib import Path
import sys
src = Path(sys.argv[1])
out = Path(sys.argv[2])
text = src.read_text()
repls = [
    ('24h Energy Plan v0.4.7 SHADOW LOW-LOAD', '24h Energy Plan v0.4.8 SHADOW LOW-LOAD'),
    ("EM2_ENERGY_PLAN_24H_V0.4.7", "EM2_ENERGY_PLAN_24H_V0.4.8"),
    ("Homey-EMS-Planner-v0.4.7", "Homey-EMS-Planner-v0.4.8"),
    ("const contract=String(input.contractType||priceCtx?.contractType||'UNKNOWN').toUpperCase();",
     "const contractRaw=String(input.contractType||priceCtx?.contractType||'UNKNOWN').toUpperCase();\nconst contract=contractRaw==='VAST'?'FIXED':contractRaw;")
]
for old, new in repls:
    if old not in text:
        raise SystemExit(f'Expected source fragment missing: {old}')
    text = text.replace(old, new, 1)
out.write_text(text)
PY

grep -q "EM2_ENERGY_PLAN_24H_V0.4.8" "$OUT"
grep -q "const contractRaw=" "$OUT"
grep -q "contractRaw==='VAST'?'FIXED':contractRaw" "$OUT"
grep -q "contract==='DYNAMIC'" "$OUT"
grep -q "contract==='FIXED'" "$OUT"

# Syntax-check HomeyScript source by wrapping top-level await in an async function.
{
  echo '(async()=>{'
  cat "$OUT"
  echo '})()'
} > /tmp/energy-plan-v0.4.8-check.js
node --check /tmp/energy-plan-v0.4.8-check.js

echo "Materialized $OUT"
