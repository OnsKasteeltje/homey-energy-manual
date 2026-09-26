#!/usr/bin/env python3
"""Static safety contract for Heating Preheat V0.3 commissioning."""

from pathlib import Path

text = Path("deploy/install/install_heating_preheat_shadow_v0_3.sh").read_text()

required = [
    "ems-heating-preheat-shadow.service",
    "ems-heating-preheat-shadow.timer",
    "services/pi/api/web-data/server.py",
    "/home/jeroen/ems/runtime/web-data-api",
    "frontend/pv-flex/",
    "/var/www/ems-frontend-v2/pv-flex",
    "/web/planner/heating-preheat-shadow",
    "EMS_HEATING_PREHEAT_SHADOW_V0.3",
    "EMS_WEB_HEATING_PREHEAT_SHADOW_V1",
    'data.get("controlWrites") is not False',
    "systemctl enable --now ems-heating-preheat-shadow.timer",
]

for token in required:
    assert token in text, token

for forbidden in (
    "install_private_frontend_v2.sh",
    "/etc/caddy/Caddyfile",
    "systemctl restart caddy",
    "homey api",
):
    assert forbidden not in text.lower(), forbidden

assert text.index("systemctl start ems-heating-preheat-shadow.service") < text.index(
    "systemctl enable --now ems-heating-preheat-shadow.timer"
)
assert text.index("/web/planner/heating-preheat-shadow") < text.index(
    "systemctl enable --now ems-heating-preheat-shadow.timer"
)

print("PASS: Heating Preheat V0.3 commissioning is minimal and shadow-first")
