#!/usr/bin/env python3
import importlib.util
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "services/pi/commissioning/install_heating_homey_shadow_chain_v0_1.py"

spec = importlib.util.spec_from_file_location("heating_homey_commission", SOURCE)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def expect_runtime_error(fn, contains):
    try:
        fn()
    except RuntimeError as exc:
        assert contains in str(exc), str(exc)
    else:
        raise AssertionError(f"expected RuntimeError containing {contains}")


def valid_commands():
    return [
        {"roomKey": key, "physicalWrite": False}
        for key in ("woonkamer", "eetkamer", "keuken", "serre")
    ]


def test_targeted_ready_readback():
    assert m.READ_SPACING_SECONDS >= 5

    logic = {
        "intent": {"id": "logic-intent", "name": m.LOGIC_NAMES["intent"]},
        "adapter": {"id": "logic-adapter", "name": m.LOGIC_NAMES["adapter"]},
        "gate": {"id": "logic-gate", "name": m.LOGIC_NAMES["gate"]},
    }
    adapter_source = "return true;"
    gate_source = "return true;"
    adapter_candidate = m.adapter_flow(logic, adapter_source)
    gate_candidate = m.gate_flow(logic, gate_source)
    flows = {
        "adapter": {"id": "flow-adapter", "name": m.FLOW_NAMES["adapter"]},
        "gate": {"id": "flow-gate", "name": m.FLOW_NAMES["gate"]},
    }
    config = {
        "state": "READY",
        "logic": logic,
        "flows": flows,
    }

    calls = []
    sleeps = []

    def fake_get_variable(var_id):
        calls.append(("logic", var_id))
        for key, meta in logic.items():
            if meta["id"] == var_id:
                return {"id": var_id, "name": m.LOGIC_NAMES[key], "type": "string"}
        raise AssertionError(var_id)

    def fake_get_flow(flow_id):
        calls.append(("flow", flow_id))
        if flow_id == "flow-adapter":
            return {"id": flow_id, **adapter_candidate}
        if flow_id == "flow-gate":
            return {"id": flow_id, **gate_candidate}
        raise AssertionError(flow_id)

    original_get_variable = m.get_variable
    original_get_flow = m.get_flow
    original_sleep = m.time.sleep
    m.get_variable = fake_get_variable
    m.get_flow = fake_get_flow
    m.time.sleep = lambda seconds: sleeps.append(seconds)
    try:
        out_logic, out_flows = m.validate_ready_pinned_objects(
            config, adapter_source, gate_source
        )
    finally:
        m.get_variable = original_get_variable
        m.get_flow = original_get_flow
        m.time.sleep = original_sleep

    assert out_logic == logic
    assert out_flows == flows
    assert calls == [
        ("logic", "logic-intent"),
        ("logic", "logic-adapter"),
        ("logic", "logic-gate"),
        ("flow", "flow-adapter"),
        ("flow", "flow-gate"),
    ]
    assert len(sleeps) == 5
    assert all(seconds >= 5 for seconds in sleeps)


def test_shadow_output_validation():
    revision = "hcs1-test"
    intent = {
        "schema": "EMS_HEATING_CONTROL_INTENT_V0.1",
        "valid": True,
        "status": "OK",
        "reason": "V0_5_SHADOW_CONTRACT_VALID",
        "controlRevision": revision,
        "deviceWrites": False,
        "physicalWriteAllowed": False,
        "liveExecutionAllowed": False,
        "safety": {"liveExecutionAllowed": False},
        "commands": valid_commands(),
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
        "commands": valid_commands(),
    }
    gate = {
        "schema": "EMS_HEATING_CONTROL_ADAPTER_GATE_SHADOW_V0.1",
        "finalStatus": "PASS",
        "sourceControlRevision": revision,
        "adapterControlRevision": revision,
        "deviceWrites": False,
        "physicalWriteAllowed": False,
        "liveExecutionAllowed": False,
        "errors": [],
        "commands": valid_commands(),
    }

    assert m.validate_shadow_outputs(intent, adapter, gate) == revision

    broken_intent = dict(intent)
    broken_intent["liveExecutionAllowed"] = None
    expect_runtime_error(
        lambda: m.validate_shadow_outputs(broken_intent, adapter, gate),
        "RESUME_INTENT_LIVE_EXECUTION_ALLOWED",
    )

    broken_gate = dict(gate)
    broken_gate["adapterControlRevision"] = "wrong"
    expect_runtime_error(
        lambda: m.validate_shadow_outputs(intent, adapter, broken_gate),
        "RESUME_GATE_ADAPTER_REVISION_MISMATCH",
    )


def test_resume_contains_no_homey_object_mutation():
    source = inspect.getsource(m.resume_ready)
    for forbidden in (
        "create_variable",
        "create_flow",
        "update_flow",
        "ensure_logic_variables",
        "ensure_flow",
    ):
        assert forbidden not in source
    assert "validate_ready_pinned_objects" in source
    assert "validate_shadow_outputs" in source
    assert "ems-heating-homey-shadow-publish.timer" in source


def main():
    test_targeted_ready_readback()
    test_shadow_output_validation()
    test_resume_contains_no_homey_object_mutation()
    print("PASS: Heating Homey READY resume contract")


if __name__ == "__main__":
    main()
