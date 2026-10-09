#!/usr/bin/env bash
# EV deadline direct Pi ingress V1.1 — strictly read-only preflight.
# Run in detached PR worktree; never starts/stops services or changes runtime.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "=== GIT SOURCE ==="
git status --short
test -z "$(git status --porcelain)" || { echo "STOP: worktree not clean"; exit 1; }
git log -1 --format='%h %s'
test -f services/pi/api/status/tesla_command_ingest.py
test -f tests/integrations/ev/test_ev_deadline_local_ingress.py

echo
echo "=== PR REGRESSION (NO PYTEST) ==="
python3 -m py_compile \
 services/pi/api/status/server.py \
 services/pi/api/status/tesla_command_ingest.py \
 services/pi/state/ev/deadline/build_deadline_state.py \
 services/pi/api/web-data/server.py
python3 tests/integrations/ev/test_ev_deadline_local_ingress.py
node --check frontend/settings/control/tesla-deadline.js
node --check frontend/settings/state/settings-state.js
bash -n "$0"

echo
echo "=== SOURCE ARCHITECTURE GATE ==="
bash scripts/ems_architecture_gate.sh

echo
echo "=== CADDY SYNTAX (NO RELOAD) ==="
sudo caddy validate --config deploy/caddy/ems-frontend-v2.Caddyfile --adapter caddyfile

echo
echo "=== TAILSCALE IP ==="
tailscale status >/dev/null
tailscale ip -4 | grep -Fxq '100.127.130.0' || { echo "STOP: expected Pi Tailscale IP missing"; exit 1; }
echo "PASS: Pi Tailscale address 100.127.130.0 exists"

echo
echo "=== LIVE BASELINE READ-ONLY ==="
systemctl is-active ems-status-api.service ems-web-data-api.service caddy.service ems-ev-deadline-command.timer
curl -fsS --max-time 8 http://127.0.0.1:3100/health >/dev/null
curl -fsS --max-time 8 http://127.0.0.1:3200/web/commands/current >/dev/null
test -s /home/jeroen/ems/data/tesla-deadline-command.json
echo "PASS: operational APIs and canonical command available"

echo
echo "=== CURRENT WEBSITE LISTENERS (OBSERVATION ONLY) ==="
sudo ss -lntp '( sport = :80 )' || true

echo
echo "=== PREFLIGHT PASS: no production settings changed ==="
echo "NEXT: controlled PR merge and Pi cutover; do not enable a second command writer."
