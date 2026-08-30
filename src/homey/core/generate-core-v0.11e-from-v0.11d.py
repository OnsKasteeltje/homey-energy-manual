from __future__ import annotations

from pathlib import Path
import sys

BASE = Path(sys.argv[1] if len(sys.argv) > 1 else 'src/homey/core/core-v0.11d-live-capture-2026-08-30.js')
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else 'src/homey/core/core-v0.11e-planner-tesla-intent.js')

text = BASE.read_text()
original = text


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    assert count == 1, f'{label}: expected exactly one anchor, found {count}'
    text = text.replace(old, new, 1)


replace_once(
    "// EM v2 | 00 Core Tick | v0.11d — Planner WW intent + bounded thermostat verification rearm",
    "// EM v2 | 00 Core Tick | v0.11e — Planner WW + Tesla intent + bounded thermostat verification rearm",
    'header',
)
replace_once(
    "PUB_VERSION='EM2_CORE_STATE_V0.11d'",
    "PUB_VERSION='EM2_CORE_STATE_V0.11e'",
    'publisher version',
)

# v0.11d evaluates Tesla before it parses the Planner snapshot for WW. Move only
# the existing Planner snapshot parse block before the Tesla decision so both domains
# consume one already-available semantic input. Do not add a new Homey read.
planner_old = "const plannerSnap=parse(vv('EM2_Energy_Planner_Snapshot')),plannerAtMs=Date.parse(String(plannerSnap?.generatedAt||plannerSnap?.plan?.generatedAt||'')),plannerFresh=Number.isFinite(plannerAtMs)&&Date.now()-plannerAtMs>=0&&Date.now()-plannerAtMs<=PLANNER_FRESH_MS,plannerCompatible=plannerFresh&&String(plannerSnap?.plan?.schema||'')==='EM2_ENERGY_PLAN_24H_V0.4.9',plannerActions=plannerCompatible&&Array.isArray(plannerSnap?.plan?.plan?.actions)?plannerSnap.plan.plan.actions:[],plannerSlot=plannerActions.find(a=>{const s=Date.parse(String(a?.start||'')),e=Date.parse(String(a?.end||''));return Number.isFinite(s)&&Number.isFinite(e)&&s<=Date.now()&&Date.now()<e;})||null,plannerWW=String(plannerSlot?.warmWater||'HOLD').toUpperCase(),plannerWWReason=String(plannerSlot?.warmWaterReason||'UNKNOWN'),plannerWWStart=plannerSlot?.start??null,plannerWWEnd=plannerSlot?.end??null;"
assert text.count(planner_old) == 1, 'planner block anchor changed'
text = text.replace(planner_old + "\n", '', 1)

source_anchor = "const sourceRevision=Number(state.revision),gridW=Number(state.grid.powerW)||0,exportW=Math.max(0,-gridW),importW=Math.max(0,gridW),deadlineActive=bool(state.goals.teslaDeadlineActive),remaining=Math.max(0,Number(state.goals.teslaRemainingKWh)||0),latestStartMs=Date.parse(state.goals.teslaLatestStart||''),chargeState=String(state.tesla.chargeState||'unknown').toLowerCase(),plugged=!chargeState.includes('plugged_out')&&!chargeState.includes('unplug'),negative=ctxFresh&&bool(state.context.priceNegative),cheap=ctxFresh&&bool(state.context.priceCheapNext4h),teslaPriceBudgetOk=discretionaryImportBudgetW>=1500;"
planner_new = planner_old[:-1] + ",plannerTesla=String(plannerSlot?.tesla||'HOLD').toUpperCase(),plannerTeslaStart=plannerSlot?.start??null,plannerTeslaEnd=plannerSlot?.end??null;"
replace_once(source_anchor, planner_new + "\n" + source_anchor, 'move planner block before Tesla decision')

energy_anchor = "let energyState=exportW>=1500?'SURPLUS_HIGH':exportW>=300?'SURPLUS':importW>=1500?'IMPORT_HIGH':importW>=300?'IMPORT':'BALANCED',priority='MAY',intent='HOLD',reason=p1Fresh?(derivedHouseBalanceValid?'Geen harde verplichting of sterke opportunity':balanceDegradedAsync?'PV/Huis reconstructie onderdrukt: P1/PV niet tijdgelijk; P1-export blijft autoritatief voor flex':`PV/Huis diagnostiek ${balanceReason}; P1-export blijft autoritatief voor flex`):'P1-data niet vers; flex-export opportunities geblokkeerd';"
guards = "const PLANNER_TESLA_MIN_IMPORT_BUDGET_W=4140,plannerTeslaDeadlineSlot=plannerCompatible&&plannerTesla==='PREFERRED_BEFORE_DEADLINE',plannerTeslaImportGuardOk=discretionaryImportBudgetW>=PLANNER_TESLA_MIN_IMPORT_BUDGET_W,plannerTeslaDeadlineEligible=plannerTeslaDeadlineSlot&&deadlineActive&&remaining>0&&Number.isFinite(latestStartMs)&&Date.now()<latestStartMs&&plugged&&p1Fresh&&gridMeasurementValid;"
replace_once(energy_anchor, guards + "\n" + energy_anchor, 'Planner Tesla guards')

old_decision = "if(deadlineActive&&remaining>0&&Number.isFinite(latestStartMs)&&Date.now()>=latestStartMs){priority='MUST';intent=plugged?'TESLA_CHARGE_DEADLINE':'TESLA_DEADLINE_BLOCKED_NOT_CONNECTED';reason=`Tesla deadline catch-up: ${remaining.toFixed(2)} kWh resterend`;}else if(deadlineActive&&remaining>0&&(flexExportBudgetW>=BUDGET.teslaOpportunityW||negative||(cheap&&teslaPriceBudgetOk))){priority='SHOULD';intent=plugged?'TESLA_CHARGE_OPPORTUNITY':'TESLA_WAIT_NOT_CONNECTED';reason=flexExportBudgetW>=BUDGET.teslaOpportunityW?`Flex-exportbudget ${Math.round(flexExportBudgetW)} W na Quatt-reserve`:negative?'Negatieve prijs':`Goedkoop prijsvenster; importbudget ${Math.round(discretionaryImportBudgetW)} W`;}else if(!deadlineActive&&plugged&&flexExportBudgetW>=1500){priority='MAY';intent='TESLA_BUFFER_EXPORT';reason=`Geen deadline; flex-exportbudget ${Math.round(flexExportBudgetW)} W na Quatt-reserve`;}"
new_decision = "if(deadlineActive&&remaining>0&&Number.isFinite(latestStartMs)&&Date.now()>=latestStartMs){priority='MUST';intent=plugged?'TESLA_CHARGE_DEADLINE':'TESLA_DEADLINE_BLOCKED_NOT_CONNECTED';reason=`Tesla deadline catch-up: ${remaining.toFixed(2)} kWh resterend`;}else if(plannerTeslaDeadlineEligible&&plannerTeslaImportGuardOk){priority='SHOULD';intent='TESLA_CHARGE_DEADLINE';reason=`PLANNER_TESLA_DEADLINE_SLOT_EXECUTED | ${plannerTeslaStart}–${plannerTeslaEnd} | importbudget ${Math.round(discretionaryImportBudgetW)} W`;}else if(plannerTeslaDeadlineSlot&&deadlineActive&&remaining>0&&!plugged){priority='SHOULD';intent='TESLA_WAIT_NOT_CONNECTED';reason='PLANNER_TESLA_BLOCKED_NOT_CONNECTED | deadline-slot actief';}else if(plannerTeslaDeadlineSlot&&deadlineActive&&remaining>0&&(!p1Fresh||!gridMeasurementValid)){priority='MAY';intent='HOLD';reason='PLANNER_TESLA_BLOCKED_P1 | deadline-slot actief maar P1 niet vers/geldig';}else if(plannerTeslaDeadlineSlot&&deadlineActive&&remaining>0&&!plannerTeslaImportGuardOk){priority='MAY';intent='HOLD';reason=`PLANNER_TESLA_BLOCKED_IMPORT_BUDGET | ${Math.round(discretionaryImportBudgetW)} W < ${PLANNER_TESLA_MIN_IMPORT_BUDGET_W} W`;}else if(deadlineActive&&remaining>0&&(flexExportBudgetW>=BUDGET.teslaOpportunityW||negative||(cheap&&teslaPriceBudgetOk))){priority='SHOULD';intent=plugged?'TESLA_CHARGE_OPPORTUNITY':'TESLA_WAIT_NOT_CONNECTED';reason=flexExportBudgetW>=BUDGET.teslaOpportunityW?`Flex-exportbudget ${Math.round(flexExportBudgetW)} W na Quatt-reserve`:negative?'Negatieve prijs':`Goedkoop prijsvenster; importbudget ${Math.round(discretionaryImportBudgetW)} W`;}else if(!deadlineActive&&plugged&&flexExportBudgetW>=1500){priority='MAY';intent='TESLA_BUFFER_EXPORT';reason=`Geen deadline; flex-exportbudget ${Math.round(flexExportBudgetW)} W na Quatt-reserve`;}"
replace_once(old_decision, new_decision, 'Tesla decision precedence')

old_inputs = "deadlineActive,remainingKWh:remaining,latestStart:state.goals.teslaLatestStart??null,boilerPowerW:state.hotWater.boilerPowerW"
new_inputs = "deadlineActive,remainingKWh:remaining,latestStart:state.goals.teslaLatestStart??null,plannerTesla,plannerTeslaStart,plannerTeslaEnd,plannerTeslaDeadlineSlot,plannerTeslaDeadlineEligible,plannerTeslaImportGuardOk,plannerGeneratedAt:plannerSnap?.generatedAt??plannerSnap?.plan?.generatedAt??null,boilerPowerW:state.hotWater.boilerPowerW"
replace_once(old_inputs, new_inputs, 'decision observability')

# Safety / load invariants. This candidate may move an existing statement but must not
# add a second Planner read, a device write, or a new poller/network path.
assert text.count("vv('EM2_Energy_Planner_Snapshot')") == 1
assert text.count('Homey.devices.getDevice({id})') == original.count('Homey.devices.getDevice({id})')
assert text.count('Homey.logic.getVariables()') == original.count('Homey.logic.getVariables()')
assert text.count("setCapabilityValue") == original.count("setCapabilityValue") == 0
assert text.count("homey:manager:cron:every_nth") == original.count("homey:manager:cron:every_nth") == 0
assert "EM2_DECISION_V0.9" in text
assert "EM2_CONTROL_WW_V0.11" in text
assert "thermostatVerifyConsumedRunKey" in text
assert "const evMode=intent==='TESLA_CHARGE_DEADLINE'?'DEADLINE'" in text
assert "PLANNER_TESLA_MIN_IMPORT_BUDGET_W=4140" in text
assert "PLANNER_TESLA_DEADLINE_SLOT_EXECUTED" in text
assert "EM2_CORE_STATE_V0.11d" not in text

OUT.write_text(text)
print(f'generated {OUT} from exact v0.11d baseline; bytes={len(text.encode())}')
