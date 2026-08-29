from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WwAdapterInput:
    schema: str
    valid: bool
    device_writes: bool
    source_revision: int | None
    target_present: bool
    target_on: bool | None
    source_action: str | None = None


def build_ww_adapter(inp: WwAdapterInput) -> dict[str, object]:
    """Deterministic replay of the captured WW Power v0.1 SHADOW translation contract.

    This contains no policy, device reads, network I/O or physical writes.
    """
    type_ok = inp.target_present and (inp.target_on is None or isinstance(inp.target_on, bool))
    input_valid = (
        inp.schema == "EM2_POWER_INTENT_V0.2"
        and inp.valid is True
        and inp.device_writes is False
        and inp.source_revision is not None
        and type_ok
    )

    status = "INVALID_POWER_INTENT"
    value: bool | None = None
    if input_valid:
        if inp.target_on is True:
            status = "OK_ON"
            value = True
        elif inp.target_on is False:
            status = "OK_OFF"
            value = False
        else:
            status = "OK_HOLD"

    return {
        "schema": "EM2_WW_POWER_ADAPTER_V0.1",
        "inputSchema": "EM2_POWER_INTENT_V0.2",
        "sourceRevision": inp.source_revision,
        "valid": input_valid,
        "status": status,
        "readOnly": True,
        "controlMode": "SHADOW",
        "deviceWrites": False,
        "input": {
            "targetPresent": inp.target_present,
            "target_on": inp.target_on if inp.target_present else None,
            "sourceAction": inp.source_action,
        },
        "command": {
            "capability": "onoff",
            "value": value,
            "physicalWrite": False,
        },
        "safety": {
            "failClosed": True,
            "policyDecisionMadeHere": False,
            "noDeviceReads": True,
            "noDeviceWrites": True,
        },
    }
