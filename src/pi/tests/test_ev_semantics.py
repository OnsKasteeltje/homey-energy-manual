from ems.ev_semantics import EvSemanticInput, build_ev_control


def test_hold():
    result = build_ev_control(EvSemanticInput("HOLD", 9000, True, False, 12))
    assert result["mode"] == "HOLD"
    assert result["requestedPowerClass"] == 0


def test_opportunity_below_minimum():
    result = build_ev_control(EvSemanticInput("TESLA_CHARGE_OPPORTUNITY", 3500, True, False, 13))
    assert result["mode"] == "OPPORTUNITY"
    assert result["requestedPowerClass"] == 1


def test_deadline_6200w():
    result = build_ev_control(EvSemanticInput("TESLA_CHARGE_DEADLINE", 6200, True, True, 14))
    assert result["mode"] == "DEADLINE"
    assert result["requestedPowerClass"] == 8
    assert result["deadlineActive"] is True


def test_unavailable_charger_blocks_semantics():
    result = build_ev_control(EvSemanticInput("TESLA_CHARGE_OPPORTUNITY", 6000, False, False, 15))
    assert result["chargerAvailable"] is False
    assert result["safetyState"] == "BLOCKED"
