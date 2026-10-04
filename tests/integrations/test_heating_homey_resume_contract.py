#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "services/pi/commissioning/install_heating_homey_shadow_chain_v0_1.py"

spec = importlib.util.spec_from_file_location("heating_resume_commission", SOURCE)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def payloads():
    revision = "hcs1-test"
    commands = [
        {"roomKey": key, "action": "HOLD", "physicalWrite": False}
        for key in ("woonkamer", "eetkamer", "keuken", "serre")
    ]
    intent = {
        "schema": "EMS_HEATING_CONTROL_INTENT_V0.1",
        "valid": True,
        "status": "OK",
        "controlRevision": revision,
        "deviceWrites": False,
        "physicalWriteAllowed": False,
        "liveExecutionAllowed": False,
        "commands": commands,
    }
    adapter = {
        "schema": "EMS_HEATING_CONTROL_ADAPTER_SHADOW_V0.1",
        "valid": True,
        "status": "PASS",
        "sourceControlRevision": revision,
        "deviceWrites": False,
        "physicalWriteAllowed": False,
        "liveExecutionAllowed": False,
        "errors": [],
        "commands": commands,
    }
    gate = {
        "schema": "EMS_HEATING_CONTROL_ADAPTER_GATE_SHADOW_V0.1",
        "finalStatus": "PASS",
        "sourceControlRevision": revision,
        "deviceWrites": False,
        "physicalWriteAllowed": False,
        "liveExecutionAllowed": False,
        "errors": [],
        "commands": commands,
    }
    return intent, adapter, gate


def main():
    intent, adapter, gate = payloads()
    assert m._validate_shadow_chain_payloads(intent, adapter, gate) == "hcs1-test"

    broken = dict(intent)
    broken["liveExecutionAllowed"] = None
    try:
        m._validate_shadow_chain_payloads(broken, adapter, gate)
    except RuntimeError as exc:
        assert "LIVE_EXECUTION_BOUNDARY_INVALID" in str(exc)
    else:
        raise AssertionError("missing top-level live execution block must fail")

    broken_gate = dict(gate)
    broken_gate["sourceControlRevision"] = "hcs1-other"
    try:
        m._validate_shadow_chain_payloads(intent, adapter, broken_gate)
    except RuntimeError as exc:
        assert "REVISION_MISMATCH" in str(exc)
    else:
        raise AssertionError("revision mismatch must fail")

    broken_adapter = dict(adapter)
    broken_adapter["status"] = "FAIL_CLOSED"
    try:
        m._validate_shadow_chain_payloads(intent, broken_adapter, gate)
    except RuntimeError as exc:
        assert "ADAPTER_NOT_PASS" in str(exc)
    else:
        raise AssertionError("adapter fail must block timer promotion")

    print("PASS: Heating Homey resume validation contract")


if __name__ == "__main__":
    main()
