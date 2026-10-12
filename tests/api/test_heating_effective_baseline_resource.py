import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "services/pi/api/web-data/server.py"
spec = importlib.util.spec_from_file_location("ems_web_data_server", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


ROOMS = (
    "woonkamer",
    "eetkamer",
    "keuken",
    "serre",
    "douwe_slaapkamer",
    "erker_douwe",
)


def write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def schedule_payload():
    return {
        "schema": "EMS_HONEYWELL_SCHEDULE_V0.2",
        "generatedAt": "2026-10-12T07:07:00Z",
        "zones": [
            {
                "key": key,
                "displayName": key,
                "scheduleStatus": "OK",
                "weeklySchedule": [
                    {
                        "day_of_week": "monday",
                        "switchpoints": [
                            {"time_of_day": "00:00:00", "heat_setpoint": 15.0},
                            {"time_of_day": "12:00:00", "heat_setpoint": 17.0},
                        ],
                    }
                ],
            }
            for key in ROOMS
        ],
    }


def room_model_payload():
    effective_by_room = {
        "woonkamer": {
            "currentTarget_C": 15.0,
            "source": "SCHEDULE",
            "systemMode": "auto",
            "setpointMode": "follow_schedule",
            "overrideUntil": None,
            "preheatAdvanceAllowed": True,
            "reason": "FOLLOW_SCHEDULE",
        },
        "eetkamer": {
            "currentTarget_C": 15.0,
            "source": "SCHEDULE",
            "systemMode": "auto",
            "setpointMode": "follow_schedule",
            "overrideUntil": None,
            "preheatAdvanceAllowed": True,
            "reason": "FOLLOW_SCHEDULE",
        },
        "keuken": {
            "currentTarget_C": 19.0,
            "source": "TEMPORARY_OVERRIDE",
            "systemMode": "auto",
            "setpointMode": "temporary_override",
            "overrideUntil": "2026-10-12T10:30:00+02:00",
            "preheatAdvanceAllowed": False,
            "reason": "HONEYWELL_TEMPORARY_OVERRIDE_ACTIVE",
        },
        "serre": {
            "currentTarget_C": 10.0,
            "source": "SCHEDULE",
            "systemMode": "auto",
            "setpointMode": "follow_schedule",
            "overrideUntil": None,
            "preheatAdvanceAllowed": True,
            "reason": "FOLLOW_SCHEDULE",
        },
        "douwe_slaapkamer": {
            "currentTarget_C": 16.0,
            "source": "PERMANENT_OVERRIDE",
            "systemMode": "auto",
            "setpointMode": "permanent_override",
            "overrideUntil": None,
            "preheatAdvanceAllowed": False,
            "reason": "HONEYWELL_PERMANENT_OVERRIDE_ACTIVE",
        },
        "erker_douwe": {
            "currentTarget_C": 16.0,
            "source": "PERMANENT_OVERRIDE",
            "systemMode": "auto",
            "setpointMode": "permanent_override",
            "overrideUntil": None,
            "preheatAdvanceAllowed": False,
            "reason": "HONEYWELL_PERMANENT_OVERRIDE_ACTIVE",
        },
    }

    return {
        "schema": "EMS_HEATING_ROOM_MODEL_V0.1",
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "generatedAt": "2026-10-12T07:45:00Z",
        "baselineAuthority": "HONEYWELL",
        "rooms": [
            {
                "key": key,
                "valid": True,
                "current": {
                    "temperature_C": effective["currentTarget_C"],
                    "targetTemperature_C": effective["currentTarget_C"],
                    "setpointMode": effective["setpointMode"],
                },
                "effective": effective,
            }
            for key, effective in effective_by_room.items()
        ],
    }


def test_heating_schedule_resource_exposes_effective_override_semantics(tmp_path):
    schedule_file = tmp_path / "honeywell-schedule.json"
    model_file = tmp_path / "heating-room-model.json"
    write_json(schedule_file, schedule_payload())
    write_json(model_file, room_model_payload())

    original_schedule = module.HONEYWELL_SCHEDULE_FILE
    original_model = module.HEATING_ROOM_MODEL_FILE
    module.HONEYWELL_SCHEDULE_FILE = str(schedule_file)
    module.HEATING_ROOM_MODEL_FILE = str(model_file)
    try:
        result = module.heating_schedule_resource()
    finally:
        module.HONEYWELL_SCHEDULE_FILE = original_schedule
        module.HEATING_ROOM_MODEL_FILE = original_model

    assert result["schema"] == "EMS_WEB_HEATING_SCHEDULE_V1"
    assert result["generatedAt"] == "2026-10-12T07:45:00Z"
    assert result["scheduleGeneratedAt"] == "2026-10-12T07:07:00Z"

    rooms = {room["key"]: room for room in result["rooms"]}
    assert rooms["keuken"]["effective"] == {
        "currentTarget_C": 19.0,
        "source": "TEMPORARY_OVERRIDE",
        "systemMode": "auto",
        "setpointMode": "temporary_override",
        "overrideUntil": "2026-10-12T10:30:00+02:00",
        "preheatAdvanceAllowed": False,
        "reason": "HONEYWELL_TEMPORARY_OVERRIDE_ACTIVE",
    }
    assert rooms["douwe_slaapkamer"]["effective"]["currentTarget_C"] == 16.0
    assert rooms["douwe_slaapkamer"]["effective"]["source"] == "PERMANENT_OVERRIDE"
    assert rooms["douwe_slaapkamer"]["effective"]["preheatAdvanceAllowed"] is False
    assert rooms["erker_douwe"]["effective"]["source"] == "PERMANENT_OVERRIDE"
    assert rooms["woonkamer"]["effective"]["preheatAdvanceAllowed"] is True
