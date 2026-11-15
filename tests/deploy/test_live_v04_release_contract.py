#!/usr/bin/env python3
"""Guard V0.4 release against broadened writes or misleading readiness."""
from pathlib import Path

installer = Path("deploy/install/install_live_v0_4.sh").read_text()
assert 'BASELINE_COMMIT="0236a046bc9efebfb7c32d68e5c71e1393911dd3"' in installer
assert 'if [[ "$#" -ne 1 || "$1" != "--apply" ]]' in installer
assert "source/runtime preflight; no changes applied" in installer
assert "cmp -s" in installer and "trap rollback ERR" in installer
assert "curl --fail --silent --max-time 4" in installer
assert "state/current live/battery" in installer
assert "python3 tests/frontend/test_v2_local_assets_contract.py" in installer
for path in (
    "frontend/live/index.html",
    "frontend/live/render/live.js",
    "frontend/live/render/battery.mjs",
    "frontend/live/state/flow-v04.mjs",
    "frontend/live/styles/live-v04.css",
):
    assert path in installer, path
for forbidden in (
    "systemctl restart", "systemctl enable", "systemctl start",
    "rsync --delete", "source ~/.env", "alphaess-readonly.timer",
    "ems-web-data-api/server.py", "Caddyfile",
):
    assert forbidden not in installer, forbidden
print("PASS: Live V0.4 targeted preflight-only frontend release")
