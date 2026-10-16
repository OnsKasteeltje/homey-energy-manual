#!/usr/bin/env python3
"""One focused source/deploy/drift contract for private Caddy startup retry."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "deploy/systemd-dropins/caddy.service.d/10-tailscale-retry.conf"
DROPIN = SOURCE.read_text()
DEPLOY = (ROOT / "scripts/deploy_ems_pi.sh").read_text()
DRIFT = (ROOT / "scripts/ems_pi_drift_check.sh").read_text()
GATE = (ROOT / "scripts/ems_architecture_gate.sh").read_text()
CADDYFILE = (ROOT / "deploy/caddy/ems-frontend-v2.Caddyfile").read_text()

assert DROPIN == (
    "[Unit]\nWants=tailscaled.service\nAfter=tailscaled.service\n\n"
    "[Service]\nRestart=on-failure\nRestartSec=10s\n"
)
assert 'CADDY_DROPIN_SOURCE="$REPO/deploy/systemd-dropins/caddy.service.d/10-tailscale-retry.conf"' in DEPLOY
assert 'CADDY_DROPIN_TARGET="/etc/systemd/system/caddy.service.d/10-tailscale-retry.conf"' in DEPLOY
assert 'cp -a "$CADDY_DROPIN_TARGET" "$BACKUP/caddy.service.d/"' in DEPLOY
install = 'install -D -m 0644 "$CADDY_DROPIN_SOURCE" "$CADDY_DROPIN_TARGET"'
assert install in DEPLOY
assert DEPLOY.index(install) < DEPLOY.index("systemctl daemon-reload")
assert "systemctl restart caddy" not in DEPLOY
assert 'cmp -s "$CADDY_DROPIN_SOURCE" "$CADDY_DROPIN_TARGET"' in DRIFT
assert "test_caddy_tailscale_dropin_contract.py" in GATE
assert "bind 100.127.130.0" in CADDYFILE
print("PASS: Caddy Tailscale retry drop-in, backup, deploy and drift contract")
