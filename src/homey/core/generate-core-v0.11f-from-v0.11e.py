from pathlib import Path

SRC=Path('src/homey/core/core-v0.11e-planner-tesla-intent.js')
OUT=Path('src/homey/core/core-v0.11f-planner-tesla-headroom.js')
text=SRC.read_text()

def one(old,new,label):
    global text
    n=text.count(old)
    assert n==1, f'{label}: expected 1 anchor, got {n}'
    text=text.replace(old,new,1)

one('v0.11e — Planner WW + Tesla intent + bounded thermostat verification rearm','v0.11f — Planner WW + Tesla intent + projected-grid headroom','header')
one("PUB_VERSION='EM2_CORE_STATE_V0.11e'","PUB_VERSION='EM2_CORE_STATE_V0.11f'",'version')
one("const PLANNER_TESLA_MIN_IMPORT_BUDGET_W=4140,plannerTeslaDeadlineSlot=plannerCompatible&&plannerTesla==='PREFERRED_BEFORE_DEADLINE',plannerTeslaImportGuardOk=discretionaryImportBudgetW>=PLANNER_TESLA_MIN_IMPORT_BUDGET_W,plannerTeslaDeadlineEligible=plannerTeslaDeadlineSlot&&deadlineActive&&remaining>0&&Number.isFinite(latestStartMs)&&Date.now()<latestStartMs&&plugged&&p1Fresh&&gridMeasurementValid;","const PLANNER_TESLA_MIN_POWER_W=4140,plannerTeslaProjectedGridW=gridW+PLANNER_TESLA_MIN_POWER_W,plannerTeslaDeadlineSlot=plannerCompatible&&plannerTesla==='PREFERRED_BEFORE_DEADLINE',plannerTeslaImportGuardOk=plannerTeslaProjectedGridW<=BUDGET.maxDiscretionaryImportW,plannerTeslaDeadlineEligible=plannerTeslaDeadlineSlot&&deadlineActive&&remaining>0&&Number.isFinite(latestStartMs)&&Date.now()<latestStartMs&&plugged&&p1Fresh&&gridMeasurementValid;",'guard')
one("reason=`PLANNER_TESLA_DEADLINE_SLOT_EXECUTED | ${plannerTeslaStart}–${plannerTeslaEnd} | importbudget ${Math.round(discretionaryImportBudgetW)} W`;","reason=`PLANNER_TESLA_DEADLINE_SLOT_EXECUTED | ${plannerTeslaStart}–${plannerTeslaEnd} | projectedGrid ${Math.round(plannerTeslaProjectedGridW)} W`;",'accepted reason')
one("reason=`PLANNER_TESLA_BLOCKED_IMPORT_BUDGET | ${Math.round(discretionaryImportBudgetW)} W < ${PLANNER_TESLA_MIN_IMPORT_BUDGET_W} W`;","reason=`PLANNER_TESLA_BLOCKED_PROJECTED_IMPORT | projectedGrid ${Math.round(plannerTeslaProjectedGridW)} W > ${BUDGET.maxDiscretionaryImportW} W`;",'blocked reason')
one("plannerTeslaDeadlineSlot,plannerTeslaDeadlineEligible,plannerTeslaImportGuardOk,plannerGeneratedAt","plannerTeslaDeadlineSlot,plannerTeslaDeadlineEligible,plannerTeslaImportGuardOk,plannerTeslaProjectedGridW,plannerGeneratedAt",'observability')
assert 'EM2_CORE_STATE_V0.11f' in text
assert 'PLANNER_TESLA_BLOCKED_PROJECTED_IMPORT' in text
assert 'plannerTeslaProjectedGridW=gridW+PLANNER_TESLA_MIN_POWER_W' in text
assert text.count('Homey.logic.getVariables()')==1
assert 'setCapabilityValue' not in text
OUT.write_text(text)
print(f'generated {OUT}; bytes={len(text.encode())}')
