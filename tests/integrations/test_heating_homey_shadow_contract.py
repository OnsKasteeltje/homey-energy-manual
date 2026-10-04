#!/usr/bin/env python3
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "services/pi/integrations/homey/egress/publish_heating_control_intent_shadow.py"

spec = importlib.util.spec_from_file_location("heating_homey_publisher", SOURCE)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)

NOW = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)


def source(action="HOLD", target=None, generated="2026-10-04T09:59:30Z"):
    rooms = []
    defs = {
        "woonkamer": (16.0, 19.0),
        "eetkamer": (16.0, 19.0),
        "keuken": (12.0, 18.5),
        "serre": (12.0, 18.5),
    }
    for key, (cur, future) in defs.items():
        a = action if key == "woonkamer" else "HOLD"
        t = target if key == "woonkamer" else None
        rooms.append({
            "key": key,
            "displayName": key.title(),
            "preheatScope": True,
            "group": "living_area" if key in {"woonkamer", "eetkamer"} else None,
            "opportunityId": f"{key}|2026-10-04T14:00:00+02:00|{future:.3f}",
            "baseline": {
                "currentTarget_C": cur,
                "futureTarget_C": future,
                "direction": "UP",
                "changeAt": "2026-10-04T14:00:00+02:00",
            },
            "command": {
                "action": a,
                "target_C": t,
                "reason": "TEST",
                "physicalWrite": False,
            },
            "shadowOwnership": {
                "wouldOwnOverride": a in {"WOULD_SET_TEMP", "WOULD_KEEP_TEMP"},
                "simulatedRollback": a == "WOULD_RESET_TO_SCHEDULE",
                "physicalOwnershipProven": False,
            },
        })
    return {
        "schema": "EMS_HEATING_CONTROL_GATE_SHADOW_V0.5",
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "controlWrites": False,
        "physicalWriteAllowed": False,
        "generatedAt": generated,
        "baselineAuthority": "HONEYWELL",
        "sourceFreshness": {
            "heating": {"status": "OK"},
            "progression": {"status": "OK"},
            "progressionConsistentWithHeating": True,
            "progressionUpstreamSafe": True,
        },
        "rooms": rooms,
    }


def main():
    hold = m.build_intent(source(), generated_at=NOW)
    assert hold["valid"] is True
    assert hold["physicalWriteAllowed"] is False
    assert hold["safety"]["productionPlannerHeatingGrantPresent"] is False
    assert len(hold["commands"]) == 4
    assert all(c["physicalWrite"] is False for c in hold["commands"])

    set_intent = m.build_intent(source("WOULD_SET_TEMP", 17.5), generated_at=NOW)
    w = [c for c in set_intent["commands"] if c["roomKey"] == "woonkamer"][0]
    assert w["action"] == "SET_TEMP"
    assert w["target_C"] == 17.5
    assert w["wouldWrite"] is True

    later = m.build_intent(
        source("WOULD_SET_TEMP", 17.5),
        generated_at=NOW + timedelta(seconds=20),
    )
    assert later["controlRevision"] == set_intent["controlRevision"]
    assert later["generatedAt"] != set_intent["generatedAt"]

    stale = m.build_intent(
        source(generated="2026-10-04T09:55:00Z"),
        generated_at=NOW,
    )
    assert stale["valid"] is False
    assert stale["commands"] == []
    assert stale["physicalWriteAllowed"] is False

    bad = source("WOULD_SET_TEMP", 17.5)
    bad["rooms"][0]["command"]["physicalWrite"] = True
    rejected = m.build_intent(bad, generated_at=NOW)
    assert rejected["valid"] is False
    assert rejected["commands"] == []

    reset = m.build_intent(source("WOULD_RESET_TO_SCHEDULE", None), generated_at=NOW)
    w = [c for c in reset["commands"] if c["roomKey"] == "woonkamer"][0]
    assert w["action"] == "RESET_TO_SCHEDULE"
    assert w["target_C"] is None

    bad_reset = source("WOULD_RESET_TO_SCHEDULE", None)
    bad_reset["rooms"][0]["shadowOwnership"]["simulatedRollback"] = False
    rejected_reset = m.build_intent(bad_reset, generated_at=NOW)
    assert rejected_reset["valid"] is False
    assert rejected_reset["commands"] == []

    print("PASS: Heating V0.5 -> Homey SHADOW intent contract")


if __name__ == "__main__":
    main()
