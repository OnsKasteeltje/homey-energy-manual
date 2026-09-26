#!/usr/bin/env bash
set -euo pipefail

REPO=/home/jeroen/ems/repo/homey-energy-manual
SYSTEMD=/etc/systemd/system

sudo install -m 0644 "$REPO/deploy/systemd/ems-heating-preheat-progression-shadow.service"   "$SYSTEMD/ems-heating-preheat-progression-shadow.service"
sudo install -m 0644 "$REPO/deploy/systemd/ems-heating-preheat-progression-shadow.timer"   "$SYSTEMD/ems-heating-preheat-progression-shadow.timer"
sudo systemctl daemon-reload

sudo systemctl start ems-heating-preheat-progression-shadow.service

python3 - <<'PY'
import json
from pathlib import Path

p=Path("/home/jeroen/ems/data/heating-preheat-progression-shadow-v0.4.json")
d=json.loads(p.read_text())
assert d.get("schema")=="EMS_HEATING_PREHEAT_PROGRESSION_SHADOW_V0.4"
assert d.get("mode")=="READ_ONLY"
assert d.get("controlMode")=="SHADOW"
assert d.get("controlWrites") is False
assert d.get("physicalWriteAllowed") is False
policy=d.get("policy") or {}
assert policy.get("maxStep_C")==0.5
assert policy.get("advanceOnlyAfterMeasuredStepReached") is True
assert policy.get("groupAdvanceRequiresAllSelectedRoomsReached") is True
assert policy.get("plannerGrantRequiredForStartAndAdvance") is True
assert policy.get("intentionalGridImportAllowed") is False
assert policy.get("rollbackBehavior")=="NOT_DEFINED_SHADOW_ONLY"
for room in d.get("rooms") or []:
    assert (room.get("progression") or {}).get("physicalWritePerformed") is False
print("PASS: Heating Preheat V0.4 progression is read-only and physical-write-free")
for room in d.get("rooms") or []:
    pstate=room.get("progression") or {}
    print(room.get("key"), pstate.get("state"), pstate.get("activeStepTarget_C"), pstate.get("lastTransition"))
PY

sudo systemctl enable --now ems-heating-preheat-progression-shadow.timer
systemctl status ems-heating-preheat-progression-shadow.service --no-pager -l || true
systemctl list-timers --all --no-pager | grep ems-heating-preheat-progression-shadow
