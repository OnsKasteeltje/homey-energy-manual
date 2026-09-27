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
assert policy.get("stepHistoryRetentionHours")==48

from datetime import datetime

allowed_outcomes={
    "ADVANCED_STEP",
    "TARGET_REACHED",
    "BASELINE_TAKEOVER",
    "ENDED",
    "OPPORTUNITY_CHANGED",
}

def parse_ts(value):
    assert isinstance(value,str) and value
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    assert dt.tzinfo is not None and dt.utcoffset() is not None
    return dt

for room in d.get("rooms") or []:
    progression=room.get("progression") or {}
    assert progression.get("physicalWritePerformed") is False
    history=room.get("stepHistory")
    assert isinstance(history,list)
    for interval in history:
        assert isinstance(interval,dict)
        assert isinstance(interval.get("opportunityId"),str) and interval["opportunityId"]
        target=interval.get("target_C")
        assert isinstance(target,(int,float)) and not isinstance(target,bool)
        started=parse_ts(interval.get("startedAt"))
        ended=parse_ts(interval.get("endedAt"))
        assert ended >= started
        assert interval.get("outcome") in allowed_outcomes
        assert "physicalWritePerformed" not in interval

print("PASS: Heating Preheat V0.4 progression is read-only and physical-write-free")
print("PASS: V0.4 stepHistory retention contract is valid")
for room in d.get("rooms") or []:
    pstate=room.get("progression") or {}
    print(
        room.get("key"),
        pstate.get("state"),
        pstate.get("activeStepTarget_C"),
        pstate.get("lastTransition"),
        "historyIntervals=",len(room.get("stepHistory") or []),
    )
PY

sudo systemctl enable --now ems-heating-preheat-progression-shadow.timer
systemctl status ems-heating-preheat-progression-shadow.service --no-pager -l || true
systemctl list-timers --all --no-pager | grep ems-heating-preheat-progression-shadow
