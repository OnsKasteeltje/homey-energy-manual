#!/usr/bin/env bash
set -euo pipefail

REPO=/home/jeroen/ems/repo/homey-energy-manual
RUNTIME=/home/jeroen/ems/runtime
BACKUP=/home/jeroen/ems/backup/heating-v05-observability-$(date +%Y%m%d-%H%M%S)

cd "$REPO"

if [[ -n "$(git status --porcelain)" ]]; then
    echo "ERROR: Git worktree is not clean"
    exit 1
fi

echo "=== ARCHITECTURE GATE ==="
bash ./scripts/ems_architecture_gate.sh

echo
echo "=== BACKUP ==="
sudo mkdir -p "$BACKUP"
for f in   "$RUNTIME/history/archive_flex_context_snapshot.py"   "$RUNTIME/health/ems_health.py"   /etc/systemd/system/ems-flex-context-history.service   /etc/systemd/system/ems-flex-context-history.timer
do
    if sudo test -e "$f"; then
        sudo cp -a "$f" "$BACKUP/"
    fi
done
echo "backup: $BACKUP"

echo
echo "=== INSTALL OBSERVABILITY SOURCE ==="
sudo install -d -m 0755 "$RUNTIME/history" "$RUNTIME/health"
sudo install -m 0755   services/pi/history/archive_flex_context_snapshot.py   "$RUNTIME/history/archive_flex_context_snapshot.py"
sudo install -m 0755   services/pi/health/ems_health.py   "$RUNTIME/health/ems_health.py"
sudo ln -sfn "$RUNTIME/health/ems_health.py" /usr/local/bin/ems-health

sudo install -m 0644   deploy/systemd/ems-flex-context-history.service   /etc/systemd/system/ems-flex-context-history.service
sudo install -m 0644   deploy/systemd/ems-flex-context-history.timer   /etc/systemd/system/ems-flex-context-history.timer
sudo systemctl daemon-reload
sudo systemctl enable --now ems-flex-context-history.timer

echo
echo "=== ARCHIVE ONCE ==="
sudo systemctl start ems-flex-context-history.service

python3 - <<'PY'
import json, sqlite3, zlib

db="/home/jeroen/ems/data/planner-history.sqlite"
con=sqlite3.connect(f"file:{db}?mode=ro", uri=True)
con.execute("PRAGMA query_only=ON")
row=con.execute("""
  SELECT captured_at_utc,snapshot_zlib
  FROM flex_context_snapshots
  ORDER BY captured_at_utc DESC
  LIMIT 1
""").fetchone()
con.close()
assert row, "no flex-context snapshot"
d=json.loads(zlib.decompress(row[1]).decode("utf-8"))
assert d.get("schema")=="EMS_PI_FLEX_CONTEXT_SNAPSHOT_V0.1"
gate=d.get("controlGate") or {}
assert gate.get("physicalWriteAllowed") is False
rooms=gate.get("rooms") or []
for room in rooms:
    command=room.get("command") or {}
    assert command.get("physicalWrite") is False
print("PASS: latest flex-context snapshot contains V0.5 controlGate")
print("capturedAt:",row[0])
for room in rooms:
    if room.get("preheatScope"):
        command=room.get("command") or {}
        print(room.get("key"),command.get("action"),command.get("target_C"),command.get("reason"))
PY

echo
echo "=== HEALTH CONTRACT ==="
/usr/local/bin/ems-health > /tmp/ems-health-heating-v05.json
python3 - <<'PY'
import json

d=json.load(open("/tmp/ems-health-heating-v05.json"))
print("overall:",d.get("status"))
for key in (
    "heatingPreheatV03",
    "flexPriorityV01",
    "heatingProgressionV04",
    "heatingControlGateV05",
):
    print("data",key,":",(d.get("emsData") or {}).get(key))
    print("function",key,":",(d.get("emsFunctions") or {}).get(key))
    assert key in (d.get("emsData") or {})
    assert key in (d.get("emsFunctions") or {})
print("PASS: complete Heating chain is represented in ems-health")
PY

echo
echo "=== TIMER ==="
systemctl is-enabled ems-flex-context-history.timer
systemctl is-active ems-flex-context-history.timer
systemctl show ems-flex-context-history.service   -p Result -p ExecMainStatus --no-pager

echo
echo "=== DONE ==="
echo "No Homey/Honeywell/device writes were added or executed."
