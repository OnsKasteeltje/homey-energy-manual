#!/usr/bin/env python3
from pathlib import Path

TARGET = Path('/home/jeroen/ems/runtime/planner/dynamic-plan/build_dynamic_shadow_plan.py')
text = TARGET.read_text()
original = text


def replace_once(old, new, label):
    global text
    if old not in text:
        raise SystemExit(f'FAIL: patch anchor not found: {label}')
    if text.count(old) != 1:
        raise SystemExit(f'FAIL: patch anchor not unique: {label} ({text.count(old)})')
    text = text.replace(old, new, 1)

# Explicitly fix the EV shoulder/window bug.
# A window is no longer formed from every slot with residual export > 0.
# First determine whether each individual slot has positive marginal value for
# a feasible 6..16 A charge target. Weak positive shoulders therefore become
# boundaries and cannot dilute a strong central PV peak.
replace_once(
'''def qualify_ev_windows(candidates):
    """Find contiguous residual-PV windows after WW comfort reservation.

    Stable planning uses 6 A. 7 A is actuator kickstart only, not a planner
    threshold. A window must last >=30 min and provide >=50% of the energy
    required for stable 6 A charging over the complete window.
    """
''',
'''def qualify_ev_windows(candidates):
    """Find contiguous *profitable* EV windows after WW reservation.

    Qualification is deliberately performed per slot before grouping. Weak
    positive residual-export shoulders are boundaries, not members of a large
    average window. This prevents e.g. 100..400 W shoulder slots from diluting
    a 2.5..4 kW central PV peak. A resulting profitable run must still span at
    least EV_MIN_WINDOW_SLOTS (30 min) to preserve anti-flapping behaviour.
    """
''',
'EV qualifier docstring')

replace_once(
'''        eligible = (
            slot["teslaOpportunityConnected"]
            and ev_target_from_residual(slot["evResidualExportW"]) > 0
        )
''',
'''        eligible = (
            slot["teslaOpportunityConnected"]
            and float(slot.get("evMarginalTargetCandidateW") or 0) > 0
        )
''',
'EV profitable-slot grouping')

replace_once(
'''        s["wwPlanW"] = ww_w
        s["wwAllocationReason"] = (
            "DYNAMIC_COMFORT_PV_SLOT" if ww_w else "HOLD"
        )
        s["evResidualExportW"] = round(residual_after_ww)
''',
'''        s["wwPlanW"] = ww_w
        s["wwAllocationReason"] = (
            "DYNAMIC_COMFORT_PV_SLOT" if ww_w else "HOLD"
        )
        s["evResidualExportW"] = round(residual_after_ww)
        s["evMarginalTargetCandidateW"] = ev_target_from_residual(
            residual_after_ww
        )
        s["evMarginalEligible"] = s["evMarginalTargetCandidateW"] > 0
''',
'EV per-slot marginal qualification')

replace_once(
'''                ev_w = ev_target_from_residual(s["evResidualExportW"])
''',
'''                ev_w = int(s.get("evMarginalTargetCandidateW") or 0)
''',
'EV selected target uses qualified candidate')

replace_once(
'''            "evMarginalImportPenalty": EV_IMPORT_PENALTY,
''',
'''            "evMarginalImportPenalty": EV_IMPORT_PENALTY,
            "evWindowSegmentation": "CONTIGUOUS_POSITIVE_MARGINAL_VALUE_SLOTS",
''',
'EV window policy guardrail')

replace_once(
'''                "MARGINAL_PV_BENEFIT_AFTER_WW_MIN30M_RUN6A_TO16A"
''',
'''                "PROFITABLE_SUBWINDOWS_AFTER_WW_MIN30M_RUN6A_TO16A"
''',
'EV opportunity policy label')

if text == original:
    raise SystemExit('FAIL: no window-fix changes produced')

TARGET.write_text(text)
print('PASS: EV profitable-subwindow shoulder fix applied')
print('target :', TARGET)
