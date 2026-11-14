#!/usr/bin/env python3
"""Regression: systemd ACTIVE alone must never be treated as API deployment success."""
from pathlib import Path

installer = Path("deploy/install/install_alphaess_live_v0_3.sh").read_text()
check = installer.index("web_api_ready()")
wait = installer.index("wait_for_web_api()")
restart = installer.index("if ! systemctl restart ems-web-data-api.service")
failure = installer.index("ERROR: read-only Web Data API HTTP health check failed")
success = installer.index('PASS: Web Data API HTTP-ready and Live battery assets deployed')
assert check < wait < restart < failure < success
assert "systemctl is-active --quiet ems-web-data-api.service || return 1" in installer
assert "curl --fail --silent --max-time 2" in installer
assert "http://127.0.0.1:3200/web/state/current" in installer
assert "http://127.0.0.1:3200/web/live/battery" in installer
assert 'data.get("schema") == "EMS_WEB_LIVE_BATTERY_V1"' in installer
assert '"FRESH", "STALE", "PARTIAL", "UNAVAILABLE"' in installer
assert "for ((attempt=1; attempt<=20; attempt++))" in installer
assert "if ! wait_for_web_api" not in installer  # restart + readiness are one failure gate
assert "   ! wait_for_web_api live; then" in installer
assert "wait_for_web_api core; then" in installer
assert 'BASELINE_COMMIT="c2ea047e53fe23bd12db1941c018cb5f0f9808c3"' in installer
assert "HEAD^:$rel" not in installer
assert "sudo systemctl enable" not in installer
print("PASS: V0.3 deployment checks HTTP readiness, bounded fallback, no controller changes")
