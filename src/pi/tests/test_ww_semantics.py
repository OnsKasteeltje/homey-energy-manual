from __future__ import annotations

from ems.ww_semantics import WwAdapterInput, build_ww_adapter


def test_ww_on_translation() -> None:
    out = build_ww_adapter(
        WwAdapterInput(
            schema="EM2_POWER_INTENT_V0.2",
            valid=True,
            device_writes=False,
            source_revision=43,
            target_present=True,
            target_on=True,
            source_action="WW_SCHEDULE",
        )
    )
    assert out["valid"] is True
    assert out["status"] == "OK_ON"
    assert out["command"]["value"] is True
    assert out["command"]["physicalWrite"] is False


def test_ww_hold_translation() -> None:
    out = build_ww_adapter(
        WwAdapterInput(
            schema="EM2_POWER_INTENT_V0.2",
            valid=True,
            device_writes=False,
            source_revision=44,
            target_present=True,
            target_on=None,
        )
    )
    assert out["valid"] is True
    assert out["status"] == "OK_HOLD"
    assert out["command"]["value"] is None


def test_ww_invalid_when_live_intent_reaches_shadow_adapter() -> None:
    out = build_ww_adapter(
        WwAdapterInput(
            schema="EM2_POWER_INTENT_V0.2",
            valid=True,
            device_writes=True,
            source_revision=45,
            target_present=True,
            target_on=True,
        )
    )
    assert out["valid"] is False
    assert out["status"] == "INVALID_POWER_INTENT"
    assert out["command"]["value"] is None


def test_ww_invalid_when_target_missing() -> None:
    out = build_ww_adapter(
        WwAdapterInput(
            schema="EM2_POWER_INTENT_V0.2",
            valid=True,
            device_writes=False,
            source_revision=46,
            target_present=False,
            target_on=None,
        )
    )
    assert out["valid"] is False
    assert out["status"] == "INVALID_POWER_INTENT"
