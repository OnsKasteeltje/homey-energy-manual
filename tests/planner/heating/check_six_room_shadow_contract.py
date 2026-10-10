#!/usr/bin/env python3
"""Standalone six-room heating SHADOW regression check. Run with python3, no pytest."""

import ast
import importlib.util
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SIX = ("woonkamer", "eetkamer", "keuken", "serre", "douwe_slaapkamer", "erker_douwe")
OUTSIDE = ("master_bedroom", "krijn_slaapkamer")
EXPECTED = set(SIX)
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def load(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main():
    zone_map = json.loads((ROOT / "services/pi/integrations/honeywell/config/zone-map.json").read_text())
    mapped = {zone["key"] for zone in zone_map["zones"]}
    assert EXPECTED | set(OUTSIDE) <= mapped, "Canonical Honeywell mapping incomplete"

    model = {
        "schema": "EMS_HEATING_ROOM_MODEL_V0.1",
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "generatedAt": NOW.isoformat(),
        "timezone": "Europe/Amsterdam",
        "baselineAuthority": "HONEYWELL",
        "valid": True,
        "rooms": [
            {
                "key": key,
                "displayName": key,
                "valid": True,
                "current": {
                    "temperature_C": 17.2,
                    "targetTemperature_C": 15.5,
                    "setpointMode": "FOLLOW_SCHEDULE",
                },
                "baseline": {
                    "currentTarget_C": 15.5,
                    "currentSince": (NOW - timedelta(hours=2)).isoformat(),
                    "nextChangeAt": (NOW + timedelta(hours=2)).isoformat(),
                    "nextTarget_C": 19.0,
                    "direction": "UP",
                },
            }
            for key in (*SIX, *OUTSIDE)
        ],
    }
    candidate_builder = load("heating_v02_six_room_check", "services/pi/planner/heating/build_heating_preheat_plan.py")
    candidate = candidate_builder.build_plan(model, generated_at=NOW)
    indexed = {room["key"]: room for room in candidate["rooms"]}
    assert candidate["mode"] == "READ_ONLY" and candidate["controlMode"] == "SHADOW"
    assert candidate["policy"]["maxAdvanceMinutes"] == 180
    assert candidate["policy"]["scopedRooms"] == sorted(SIX)
    for key in SIX:
        room = indexed[key]
        assert room["preheatScope"] is True, key
        assert room["candidate"]["status"] == "ELIGIBLE_UP_TRANSITION", key
        assert room["candidate"]["startAt"] is None, key
        assert max(room["candidate"]["steps_C"]) <= 19.0, key
        assert room["group"] == ("living_area" if key in {"woonkamer", "eetkamer"} else None)
    for key in OUTSIDE:
        assert indexed[key]["preheatScope"] is False, key
        assert indexed[key]["candidate"]["reason"] == "ROOM_OUT_OF_PREHEAT_SCOPE", key

    shadow_builder = load("heating_v03_six_room_check", "services/pi/planner/heating/build_heating_preheat_shadow_v0_3.py")
    quatt = {
        "schema": "EMS_QUATT_CURRENT_STATE_V0.1",
        "mode": "READ_ONLY",
        "generatedAt": NOW.isoformat(),
        "observerOnly": {
            "cvActive": {
                "value": False,
                "observedAt": NOW.isoformat(),
                "sourceLastUpdated": NOW.isoformat(),
            }
        },
    }
    shadow = shadow_builder.build_shadow(model, candidate, quatt, generated_at=NOW)
    assert shadow["controlWrites"] is False
    assert shadow["baselineAuthority"] == "HONEYWELL"
    shadow_rooms = {room["key"]: room for room in shadow["rooms"]}
    for key in SIX:
        assert shadow_rooms[key]["preheatScope"] is True, key
        assert shadow_rooms[key]["shadow"]["state"] == "PREHEAT_READY_FOR_GRANT", key
        assert shadow_rooms[key]["shadow"]["plannerGrant"] == "NOT_EVALUATED", key
        assert shadow_rooms[key]["shadow"]["activeStepTarget_C"] is None, key
    for key in OUTSIDE:
        assert shadow_rooms[key]["preheatScope"] is False, key

    server = ast.parse((ROOT / "services/pi/api/web-data/server.py").read_text())
    required = {
        "heating_schedule_resource": "allowed_keys",
        "heating_temperature_history_resource": "allowed_rooms",
        "heating_preheat_shadow_resource": "allowed_rooms",
        "heating_preheat_progression_resource": "allowed_rooms",
    }
    funcs = {node.name: node for node in server.body if isinstance(node, ast.FunctionDef)}
    for function, variable in required.items():
        values = [
            ast.literal_eval(node.value)
            for node in ast.walk(funcs[function])
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == variable for target in node.targets)
        ]
        assert len(values) == 1 and set(values[0]) == EXPECTED, (function, values)

    renderer = (ROOT / "frontend/heating/render/heating.js").read_text()
    keys_match = re.search(r"const ROOM_KEYS = (\[[^;]+\]);", renderer)
    colors_match = re.search(r"const COLORS = (\[[^;]+\]);", renderer)
    assert keys_match and colors_match
    keys = json.loads(keys_match.group(1))
    colors = json.loads(colors_match.group(1))
    assert tuple(keys) == SIX
    assert len(colors) == len(SIX) and len(set(colors)) == len(SIX)
    assert "Douwe slaapkamer</b> · zelfstandig" in renderer
    assert "Erker Douwe</b> · zelfstandig" in renderer

    print("PASS: six canonical zones included in V0.2, V0.3, four Web API allowlists, and dashboard")
    print("PASS: master/krijn excluded, Honeywell remains authority, no physical write")


if __name__ == "__main__":
    main()
