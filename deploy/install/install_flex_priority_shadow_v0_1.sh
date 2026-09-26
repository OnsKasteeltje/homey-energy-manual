#!/usr/bin/env bash
set -euo pipefail

REPO=/home/jeroen/ems/repo/homey-energy-manual
SYSTEMD=/etc/systemd/system

sudo install -m 0644 "$REPO/deploy/systemd/ems-flex-priority-shadow.service" "$SYSTEMD/ems-flex-priority-shadow.service"
sudo install -m 0644 "$REPO/deploy/systemd/ems-flex-priority-shadow.timer" "$SYSTEMD/ems-flex-priority-shadow.timer"
sudo systemctl daemon-reload

sudo systemctl start ems-flex-priority-shadow.service

python3 - <<'PY'
import json
from pathlib import Path
p=Path("/home/jeroen/ems/data/flex-priority-shadow-v0.1.json")
d=json.loads(p.read_text())
assert d.get("schema")=="EMS_PI_FLEX_PRIORITY_SHADOW_V0.1"
assert d.get("mode")=="READ_ONLY"
assert d.get("controlMode")=="SHADOW"
assert d.get("controlWrites") is False
assert d.get("policy",{}).get("powerReservationW")==0
assert d.get("policy",{}).get("realtimeOpportunityAuthority")=="P1"
assert d.get("decision",{}).get("physicalWriteAllowed") is False
print("PASS: Flex Priority shadow is read-only, no-reservation and P1-bounded")
print("decision:", d.get("decision"))
PY

sudo systemctl enable --now ems-flex-priority-shadow.timer
systemctl status ems-flex-priority-shadow.service --no-pager -l || true
systemctl list-timers --all --no-pager | grep ems-flex-priority-shadow
