#!/usr/bin/env bash
set -euo pipefail

REPO=/home/jeroen/ems/repo/homey-energy-manual
SYSTEMD=/etc/systemd/system

sudo install -m 0644 "$REPO/deploy/systemd/ems-forecast-chain.service" "$SYSTEMD/ems-forecast-chain.service"
sudo install -m 0644 "$REPO/deploy/systemd/ems-forecast-chain.timer" "$SYSTEMD/ems-forecast-chain.timer"

sudo systemctl daemon-reload

# Remove the split-generation race. These legacy timers must not own forecast
# generation anymore; their services remain available for manual diagnostics.
sudo systemctl disable --now ems-weather-forecast.timer ems-pv-forecast.timer
sudo systemctl enable --now ems-forecast-chain.timer

# Prove the complete chain once before relying on the timer. Any strict 96-slot
# failure aborts the oneshot and prevents downstream publish steps from running.
sudo systemctl start ems-forecast-chain.service

systemctl status ems-forecast-chain.service --no-pager -l
systemctl list-timers --all --no-pager | grep -E 'ems-(forecast-chain|weather-forecast|pv-forecast)' || true

python3 - <<'PY'
import json
from pathlib import Path

checks = {
    'planner-axis': Path('/home/jeroen/ems/data/planner-axis.json'),
    'dynamic-plan': Path('/home/jeroen/ems/data/dynamic-shadow-plan.json'),
}

for name, path in checks.items():
    d = json.loads(path.read_text())
    count = d.get('slot_count')
    if count is None:
        count = len(d.get('slots') or [])
    if count != 96:
        raise SystemExit(f'FAIL: {name} has {count} slots, expected 96')
    print(f'PASS: {name} slots={count} generated={d.get("generated_at") or d.get("generatedAt")}')
PY
