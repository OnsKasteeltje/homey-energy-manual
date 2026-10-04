#!/usr/bin/env bash
set -euo pipefail

REPO=/home/jeroen/ems/repo/homey-energy-manual
SYSTEMD=/etc/systemd/system

sudo install -m 0644 "$REPO/deploy/systemd/ems-heating-control-gate-shadow.service" "$SYSTEMD/ems-heating-control-gate-shadow.service"
sudo install -m 0644 "$REPO/deploy/systemd/ems-heating-control-gate-shadow.timer" "$SYSTEMD/ems-heating-control-gate-shadow.timer"
sudo systemctl daemon-reload
sudo systemctl start ems-heating-control-gate-shadow.service

python3 - <<'PY'
import json
from pathlib import Path

d=json.loads(Path("/home/jeroen/ems/data/heating-control-gate-shadow-v0.5.json").read_text())
assert d.get("schema")=="EMS_HEATING_CONTROL_GATE_SHADOW_V0.5"
assert d.get("mode")=="READ_ONLY"
assert d.get("controlMode")=="SHADOW"
assert d.get("controlWrites") is False
assert d.get("physicalWriteAllowed") is False
assert d.get("baselineAuthority")=="HONEYWELL"
p=d.get("policy") or {}
assert p.get("maxStep_C")==0.5
assert p.get("physicalWriteAllowed") is False
assert p.get("intentionalGridImportAllowed") is False
assert p.get("singlePhysicalWriterRequired") is True
assert p.get("futurePhysicalWriter")=="HOMEY_HONEYWELL_ACTUATOR_ONLY"
assert p.get("rollbackBehavior")=="RESET_TO_HONEYWELL_SCHEDULE_IF_SHADOW_OWNED"
assert p.get("shadowOwnershipIsPhysicalProof") is False
assert p.get("livePromotionRequires")=="HOMEY_ACK_AND_HONEYWELL_READBACK"
allowed={"HOLD","WOULD_SET_TEMP","WOULD_KEEP_TEMP","WOULD_RESET_TO_SCHEDULE"}
for room in d.get("rooms") or []:
    cmd=room.get("command") or {}
    assert cmd.get("action") in allowed
    assert cmd.get("physicalWrite") is False
    assert (room.get("shadowOwnership") or {}).get("physicalOwnershipProven") is False
print("PASS: Heating Control Gate V0.5 is READ_ONLY / SHADOW / no physical writes")
for room in d.get("rooms") or []:
    cmd=room.get("command") or {}
    print(room.get("key"), cmd.get("action"), cmd.get("target_C"), cmd.get("reason"))
PY

sudo systemctl enable --now ems-heating-control-gate-shadow.timer
systemctl status ems-heating-control-gate-shadow.service --no-pager -l || true
systemctl list-timers --all --no-pager | grep ems-heating-control-gate-shadow
