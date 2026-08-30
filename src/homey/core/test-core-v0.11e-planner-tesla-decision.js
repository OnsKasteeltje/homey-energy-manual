'use strict';
const assert = require('node:assert/strict');
const { PLANNER_TESLA_MIN_POWER_W, MAX_DISCRETIONARY_IMPORT_W, decideTeslaV011f } = require('./core-v0.11e-planner-tesla-decision');
const T0=Date.parse('2026-08-30T15:30:00Z'), LATEST=Date.parse('2026-08-30T17:50:52.173Z');
function base(o={}){return {deadlineActive:true,remainingKWh:14.85,latestStartMs:LATEST,nowMs:T0,plugged:true,p1Fresh:true,gridMeasurementValid:true,gridW:-1248,plannerCompatible:true,plannerTesla:'PREFERRED_BEFORE_DEADLINE',plannerTeslaStart:'2026-08-30T15:30:00Z',plannerTeslaEnd:'2026-08-30T15:45:00Z',flexExportBudgetW:948,teslaOpportunityW:800,priceNegative:false,priceCheapNext4h:false,teslaPriceBudgetOk:false,noDeadlineBufferThresholdW:1500,...o};}
function check(name,o,e){const out=decideTeslaV011f(base(o));for(const[k,v]of Object.entries(e)){if(k.startsWith('planner.'))assert.equal(out.planner[k.slice(8)],v,`${name}: ${k}`);else if(k==='reasonIncludes')assert.ok(out.reason.includes(v),`${name}: ${out.reason}`);else assert.equal(out[k],v,`${name}: ${k}`);}console.log(`PASS ${name}`);return out;}
assert.equal(PLANNER_TESLA_MIN_POWER_W,4140);assert.equal(MAX_DISCRETIONARY_IMPORT_W,4000);
check('R1 exact 17:30 runtime fixture accepts planner slot',{},{priority:'SHOULD',intent:'TESLA_CHARGE_DEADLINE',triggerSource:'PLANNER_DEADLINE_SLOT','planner.plannerTeslaImportGuardOk':true,'planner.projectedGridWAtMinCharge':2892,reasonIncludes:'PLANNER_TESLA_DEADLINE_SLOT_EXECUTED'});
check('R2 zero grid still blocks 4140 W min against 4000 W import cap',{gridW:0,flexExportBudgetW:0},{priority:'MAY',intent:'HOLD','planner.plannerTeslaImportGuardOk':false,'planner.projectedGridWAtMinCharge':4140,reasonIncludes:'PLANNER_TESLA_BLOCKED_PROJECTED_IMPORT'});
check('R3 140 W export is exact boundary',{gridW:-140,flexExportBudgetW:0},{priority:'SHOULD',intent:'TESLA_CHARGE_DEADLINE','planner.plannerTeslaImportGuardOk':true,'planner.projectedGridWAtMinCharge':4000});
check('R4 139 W export remains blocked',{gridW:-139,flexExportBudgetW:0},{priority:'MAY',intent:'HOLD','planner.plannerTeslaImportGuardOk':false,'planner.projectedGridWAtMinCharge':4001});
check('A stale P1 blocks',{p1Fresh:false},{priority:'MAY',intent:'HOLD',reasonIncludes:'PLANNER_TESLA_BLOCKED_P1'});
check('B disconnected blocks',{plugged:false},{priority:'SHOULD',intent:'TESLA_WAIT_NOT_CONNECTED'});
check('C MUST latest-start overrides projected import',{nowMs:LATEST,gridW:2500},{priority:'MUST',intent:'TESLA_CHARGE_DEADLINE',triggerSource:'LATEST_START_MUST'});
check('D no planner slot keeps realtime PV opportunity',{plannerTesla:'HOLD'},{priority:'SHOULD',intent:'TESLA_CHARGE_OPPORTUNITY',triggerSource:'REALTIME_OPPORTUNITY'});
console.log('All Core v0.11f Planner Tesla headroom regressions PASS');
