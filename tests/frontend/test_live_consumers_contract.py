#!/usr/bin/env python3
"""Read-only Live consumer evidence: allowlist and no fabricated device watts."""
import ast
from pathlib import Path

api = Path("services/pi/api/web-data/server.py").read_text(encoding="utf-8")
fn = next(n for n in ast.parse(api).body
          if isinstance(n, ast.FunctionDef) and n.name == "state_current_resource")
code = compile(ast.Module(body=[fn], type_ignores=[]), "<web-data>", "exec")
payload = {
    "meta": {"generated_at": "2026-10-14T06:20:00Z"},
    "grid": {"power_w": 2442, "l1_w": 118, "l2_w": 2264, "l3_w": 59,
             "internal_sensitive": "no"},
    "balance": {"control_gate": {"grid_measurement_valid": True}},
    "loads": {
        "washer": {"active": True, "power_w": None,
                   "state": {"applianceState": "Running", "cyclePhase": "Wash",
                             "private": "no"}},
        "dryer": {"active": False, "state": {"applianceState": "Idle"}},
        "quooker": {"active": False, "fresh": True, "power_w": 0,
                    "private": "no"},
    },
}
ctx = {"load_json": lambda _: payload, "parse_timestamp": lambda _: True,
       "ENERGY_STATE_FILE": "/dev/null", "STATE_API_SCHEMA": "TEST",
       "_live_l1_history": lambda: []}
exec(code, ctx)
result = ctx["state_current_resource"]()
assert result["grid"] == {"power_w": 2442, "l1_w": 118, "l2_w": 2264, "l3_w": 59}
assert result["loads"]["washer"] == {
    "active": True, "appliance_state": "Running", "cycle_phase": "Wash"}
assert "power_w" not in result["loads"]["washer"]
assert result["loads"]["dryer"]["active"] is False
assert result["loads"]["quooker"]["estimated_power_w"] == 0
assert "internal_sensitive" not in result["grid"]
payload["loads"] = {}
result = ctx["state_current_resource"]()
assert result["loads"]["washer"]["active"] is None
assert result["loads"]["dryer"]["active"] is None
assert result["loads"]["quooker"]["active"] is None
assert result["loads"]["quooker"]["estimated_power_w"] is None
frontend = Path("frontend/live/index.html").read_text(encoding="utf-8")
renderer = Path("frontend/live/render/live.js").read_text(encoding="utf-8")
state = Path("frontend/live/state/energy-state.js").read_text(encoding="utf-8")
for key in ("loads-washer-status", "loads-dryer-status", "loads-quooker-status",
            "loads-phase-l1", "loads-phase-l2", "loads-phase-l3",
            "loads-dishwasher-status", "loads-dishwasher-detail",
            "loads-explanation"):
    assert 'id="' + key + '"' in frontend
    assert '"' + key + '"' in renderer or '`loads-phase-' in renderer
assert 'raw?.loads' in state
assert 's.p1Valid' in renderer
assert 'geen directe vermogensmeting' in renderer
assert result["diagnostics"] == {"dishwasher_l1_history": []}
assert "source_sample_at" in result["meta"]
assert "P1_PHASE_METRICS" in Path("services/pi/api/status/history_archive.py").read_text()
for obsolete in ("<section class=\"cards\">", 'aria-label="Actuele EMS-beslissing"', 'id="kpi-grid"', 'id="manager-reason"'):
    assert obsolete not in frontend, obsolete
for keep in ('aria-label="Actuele energiestroom"', 'aria-label="Actieve verbruikers"',
             'id="grid-power"', 'id="pv-power"', 'id="tesla-power"',
             'id="loads-dishwasher-status"'):
    assert keep in frontend, keep
for obsolete in ('set("kpi-grid"', 'set("manager-reason"', 'set("manager-title"'):
    assert obsolete not in renderer, obsolete
print("PASS: Live consumer evidence contract")
