#!/usr/bin/env python3
"""Six-room Pi -> Homey Heating V0.2 SHADOW-only intent regression (no pytest)."""
import copy
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "services/pi/integrations/homey/egress/build_heating_control_intent_six_room_shadow_v0_2.py"
spec = importlib.util.spec_from_file_location("heating_shadow_v02", SOURCE)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)

NOW = datetime(2026, 10, 12, 12, 30, tzinfo=timezone.utc)
AT = (NOW - timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
NEXT = (NOW + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
ROOMS = tuple(m.ROOM_DEVICES)


def source():
    rooms = []
    for key in ROOMS:
        rooms.append({
            "key": key,
            "displayName": key,
            "preheatScope": True,
            "group": "living_area" if key in {"woonkamer", "eetkamer"} else None,
            "opportunityId": key + "|2026-10-12T13:30:00Z|18.000",
            "baseline": {
                "currentTarget_C": 16.0,
                "futureTarget_C": 18.0,
                "direction": "UP",
                "changeAt": NEXT,
            },
            "command": {
                "action": "WOULD_SET_TEMP" if key == "woonkamer" else "HOLD",
                "target_C": 16.5 if key == "woonkamer" else None,
                "reason": "TEST",
                "physicalWrite": False,
            },
            "shadowOwnership": {
                "wouldOwnOverride": key == "woonkamer",
                "simulatedRollback": False,
                "physicalOwnershipProven": False,
            },
        })
    return {
        "schema": m.SOURCE_SCHEMA,
        "mode": "READ_ONLY", "controlMode": "SHADOW",
        "controlWrites": False, "physicalWriteAllowed": False,
        "baselineAuthority": "HONEYWELL",
        "generatedAt": AT,
        "sourceFreshness": {
            "heating": {"status": "OK"},
            "progression": {"status": "OK"},
            "progressionConsistentWithHeating": True,
            "progressionUpstreamSafe": True,
        },
        "rooms": rooms,
    }


def honeywell():
    return {
        "schema": m.VENDOR_SCHEMA, "mode": "READ_ONLY",
        "generatedAt": AT,
        "location": {"systemMode": "auto"},
        "zones": [{
            "key": key,
            "homeyDeviceId": device,
            "setpointMode": "permanent_override" if "douwe" in key else "follow_schedule",
            "targetTemperature_C": 16.0,
            "overrideUntil": None,
        } for key, device in m.ROOM_DEVICES.items()],
    }


def zone(payload, key):
    return next(item for item in payload["zones"] if item["key"] == key)


def room(payload, key):
    return next(item for item in payload["rooms"] if item["key"] == key)


def command(intent, key):
    return next(item for item in intent["commands"] if item["roomKey"] == key)


def is_denied(intent, fragment):
    assert intent["valid"] is False, intent
    assert intent["status"] == "FAIL_CLOSED"
    assert fragment in intent["reason"], intent["reason"]
    assert intent["commands"] == []
    assert intent["physicalWriteAllowed"] is False
    assert intent["liveExecutionAllowed"] is False


def main():
    assert len(m.ROOM_DEVICES) == 6
    data, vendor = source(), honeywell()
    intent = m.build_intent(data, vendor, generated_at=NOW)
    assert intent["valid"] is True, intent
    assert intent["roomCount"] == 6
    assert set(c["roomKey"] for c in intent["commands"]) == set(ROOMS)
    assert intent["schema"] == "EMS_HEATING_CONTROL_INTENT_V0.2"
    assert intent["controlRevision"].startswith("hcs2-")
    assert all(c["physicalWrite"] is False for c in intent["commands"])
    assert all(c["shadowOwnership"]["physicalOwnershipProven"] is False
               for c in intent["commands"])
    assert intent["safety"]["noDeviceWrites"] is True
    assert intent["liveExecutionAllowed"] is False
    assert command(intent, "woonkamer")["action"] == "SET_TEMP"

    # A human override on either Douwe room remains HOLD even if V0.5 proposes SET.
    for key in ("douwe_slaapkamer", "erker_douwe"):
        d = source()
        r = room(d, key)
        r["command"].update(action="WOULD_SET_TEMP", target_C=16.5)
        r["shadowOwnership"]["wouldOwnOverride"] = True
        blocked = m.build_intent(d, vendor, generated_at=NOW)
        cmd = command(blocked, key)
        assert blocked["valid"] is True
        assert cmd["action"] == "HOLD"
        assert cmd["sourceShadowAction"] == "SET_TEMP"
        assert cmd["target_C"] is None
        assert cmd["wouldWrite"] is False
        assert cmd["holdReason"] == "HONEYWELL_OVERRIDE_ACTIVE"
        assert cmd["shadowOwnership"]["wouldOwnOverride"] is False
        assert cmd["physicalWrite"] is False

    # A temporary human override must receive the same protection.
    other = honeywell()
    zone(other, "keuken")["setpointMode"] = "temporary_override"
    temporary = m.build_intent(data, other, generated_at=NOW)
    assert command(temporary, "keuken")["action"] == "HOLD"
    assert command(temporary, "keuken")["holdReason"] == "HONEYWELL_OVERRIDE_ACTIVE"

    # Unknown/contradictory/mismatched vendor mode or target -> only HOLD.
    uncertain = honeywell()
    zone(uncertain, "woonkamer")["setpointMode"] = "unknown"
    assert command(m.build_intent(data, uncertain, generated_at=NOW),
                   "woonkamer")["holdReason"] == "HONEYWELL_MODE_UNKNOWN"
    ambiguous = honeywell()
    zone(ambiguous, "woonkamer")["overrideUntil"] = NEXT
    assert command(m.build_intent(data, ambiguous, generated_at=NOW),
                   "woonkamer")["holdReason"] == "HONEYWELL_OVERRIDE_UNTIL_UNEXPECTED"
    mismatch = honeywell()
    zone(mismatch, "woonkamer")["targetTemperature_C"] = 17.5
    assert command(m.build_intent(data, mismatch, generated_at=NOW),
                   "woonkamer")["holdReason"] == "HONEYWELL_TARGET_MISMATCH"

    not_auto = honeywell()
    not_auto["location"]["systemMode"] = "off"
    system_block = m.build_intent(data, not_auto, generated_at=NOW)
    assert system_block["valid"] is True
    assert command(system_block, "woonkamer")["action"] == "HOLD"
    assert command(system_block, "woonkamer")["holdReason"] == "HONEYWELL_SYSTEM_MODE_NOT_AUTO"

    no_up = source()
    room(no_up, "woonkamer")["baseline"]["direction"] = "DOWN"
    is_denied(m.build_intent(no_up, vendor, generated_at=NOW), "NON-UP")

    expired_up = source()
    room(expired_up, "woonkamer")["baseline"]["changeAt"] = AT
    is_denied(m.build_intent(expired_up, vendor, generated_at=NOW), "EXPIRED")

    # Missing or duplicate canonical rooms, stale vendor and wrong mapping fail closed.
    missing = source()
    missing["rooms"].pop()
    is_denied(m.build_intent(missing, vendor, generated_at=NOW), "MISSING_PREHEAT_ROOMS")
    duplicate = source()
    duplicate["rooms"].append(copy.deepcopy(duplicate["rooms"][0]))
    is_denied(m.build_intent(duplicate, vendor, generated_at=NOW), "DUPLICATE")
    missing_zone = honeywell()
    missing_zone["zones"].pop()
    is_denied(m.build_intent(data, missing_zone, generated_at=NOW), "SIX-ROOM_KEY_SET_MISMATCH")
    duplicate_zone = honeywell()
    duplicate_zone["zones"].append(copy.deepcopy(duplicate_zone["zones"][0]))
    is_denied(m.build_intent(data, duplicate_zone, generated_at=NOW), "DUPLICATE_ZONE")
    wrong = honeywell()
    zone(wrong, "erker_douwe")["homeyDeviceId"] = "incorrect-id"
    is_denied(m.build_intent(data, wrong, generated_at=NOW), "DEVICE_ID_MISMATCH")
    stale = honeywell()
    stale["generatedAt"] = (NOW - timedelta(minutes=20)).isoformat()
    is_denied(m.build_intent(data, stale, generated_at=NOW), "NOT_FRESH")
    bad_past = source()
    bad_past["generatedAt"] = (NOW - timedelta(minutes=10)).isoformat()
    is_denied(m.build_intent(bad_past, vendor, generated_at=NOW), "STALE")
    bad_write = source()
    room(bad_write, "woonkamer")["command"]["physicalWrite"] = True
    is_denied(m.build_intent(bad_write, vendor, generated_at=NOW), "PHYSICALWRITE")
    not_shadow = source()
    not_shadow["controlMode"] = "LIVE"
    is_denied(m.build_intent(not_shadow, vendor, generated_at=NOW), "READ_ONLY/SHADOW")

    later = m.build_intent(data, vendor, generated_at=NOW + timedelta(seconds=5))
    assert later["controlRevision"] == intent["controlRevision"]
    assert later["generatedAt"] != intent["generatedAt"]

    # No CLI publisher, network or device access in this module.
    text = SOURCE.read_text(encoding="utf-8")
    for forbidden in ("subprocess", "Homey.logic", "updateVariable", "setCapabilityValue",
                      "_publish_logic", "HOMEY_CLI"):
        assert forbidden not in text, forbidden

    # Guard against future mapping/schema drift between Pi, Homey adapter, and gate.
    adapter_path = ROOT / "src/homey/adapters/heating-control/heating-control-v0.2.six-room.shadow.js"
    gate_path = ROOT / "src/homey/validation/heating-control-adapter-gate-v0.2.six-room.shadow.js"
    adapter_js = adapter_path.read_text(encoding="utf-8")
    gate_js = gate_path.read_text(encoding="utf-8")
    for key, device_id in m.ROOM_DEVICES.items():
        assert key + ":'" + device_id + "'" in adapter_js, ("adapter", key)
        assert key + ":'" + device_id + "'" in gate_js, ("gate", key)
    assert "EMS_HEATING_CONTROL_INTENT_V0.2" in adapter_js
    assert "EMS_HEATING_CONTROL_INTENT_V0.2" in gate_js
    assert "EMS_HEATING_CONTROL_ADAPTER_SHADOW_V0.2" in gate_js
    for js in (adapter_js, gate_js):
        assert "const IDS=__EMS_HEATING_IDS__;" in js
        assert "length===6" in js
        for forbidden in ("setCapabilityValue(", "setCapabilityValues(", "runFlowCardAction("):
            assert forbidden not in js, forbidden

    print("PASS: six-room Pi -> Homey V0.2 SHADOW intent, overrides HOLD, no publisher")


if __name__ == "__main__":
    main()
