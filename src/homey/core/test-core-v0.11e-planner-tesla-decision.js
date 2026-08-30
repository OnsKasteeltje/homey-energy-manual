'use strict';

const assert = require('node:assert/strict');
const {
  PLANNER_TESLA_MIN_IMPORT_BUDGET_W,
  decideTeslaV011e,
} = require('./core-v0.11e-planner-tesla-decision');

const T0 = Date.parse('2026-08-30T15:00:00Z');
const LATEST = Date.parse('2026-08-30T18:00:00Z');

function base(overrides = {}) {
  return {
    deadlineActive: true,
    remainingKWh: 14.85,
    latestStartMs: LATEST,
    nowMs: T0,
    plugged: true,
    p1Fresh: true,
    gridMeasurementValid: true,
    discretionaryImportBudgetW: 5000,
    plannerCompatible: true,
    plannerTesla: 'PREFERRED_BEFORE_DEADLINE',
    plannerTeslaStart: '2026-08-30T15:00:00Z',
    plannerTeslaEnd: '2026-08-30T15:15:00Z',
    flexExportBudgetW: 0,
    teslaOpportunityW: 800,
    priceNegative: false,
    priceCheapNext4h: false,
    teslaPriceBudgetOk: false,
    noDeadlineBufferThresholdW: 1500,
    ...overrides,
  };
}

function check(name, overrides, expected) {
  const out = decideTeslaV011e(base(overrides));
  for (const [k, v] of Object.entries(expected)) {
    if (k.startsWith('planner.')) {
      assert.equal(out.planner[k.slice('planner.'.length)], v, `${name}: ${k}`);
    } else if (k === 'reasonIncludes') {
      assert.ok(out.reason.includes(v), `${name}: reason '${out.reason}' should include '${v}'`);
    } else {
      assert.equal(out[k], v, `${name}: ${k}`);
    }
  }
  console.log(`PASS ${name}`);
  return out;
}

assert.equal(PLANNER_TESLA_MIN_IMPORT_BUDGET_W, 4140);

check('A1 planner slot accepted', {}, {
  priority: 'SHOULD',
  intent: 'TESLA_CHARGE_DEADLINE',
  triggerSource: 'PLANNER_DEADLINE_SLOT',
  'planner.plannerTeslaDeadlineSlot': true,
  'planner.plannerTeslaDeadlineEligible': true,
  'planner.plannerTeslaImportGuardOk': true,
  reasonIncludes: 'PLANNER_TESLA_DEADLINE_SLOT_EXECUTED',
});

check('A2 import budget blocks planner', { discretionaryImportBudgetW: 4139 }, {
  priority: 'MAY',
  intent: 'HOLD',
  triggerSource: 'PLANNER_DEADLINE_SLOT',
  'planner.plannerTeslaImportGuardOk': false,
  reasonIncludes: 'PLANNER_TESLA_BLOCKED_IMPORT_BUDGET',
});

check('A3 stale P1 blocks planner', { p1Fresh: false }, {
  priority: 'MAY',
  intent: 'HOLD',
  triggerSource: 'PLANNER_DEADLINE_SLOT',
  reasonIncludes: 'PLANNER_TESLA_BLOCKED_P1',
});

check('A4 invalid grid blocks planner', { gridMeasurementValid: false }, {
  priority: 'MAY',
  intent: 'HOLD',
  triggerSource: 'PLANNER_DEADLINE_SLOT',
  reasonIncludes: 'PLANNER_TESLA_BLOCKED_P1',
});

check('A5 disconnected blocks physical charging', { plugged: false }, {
  priority: 'SHOULD',
  intent: 'TESLA_WAIT_NOT_CONNECTED',
  triggerSource: 'PLANNER_DEADLINE_SLOT',
  reasonIncludes: 'PLANNER_TESLA_BLOCKED_NOT_CONNECTED',
});

check('A6 inactive deadline cannot be invented by planner', { deadlineActive: false }, {
  priority: 'MAY',
  intent: 'HOLD',
  triggerSource: 'NONE',
});

check('A7 zero remaining cannot be invented by planner', { remainingKWh: 0 }, {
  priority: 'MAY',
  intent: 'HOLD',
  triggerSource: 'NONE',
});

check('A8 unknown planner semantic fails closed', { plannerTesla: 'UNKNOWN_NEW_VALUE' }, {
  priority: 'MAY',
  intent: 'HOLD',
  triggerSource: 'NONE',
  'planner.plannerTeslaDeadlineSlot': false,
});

check('A9 stale planner represented by incompatible=false cannot drive', { plannerCompatible: false }, {
  priority: 'MAY',
  intent: 'HOLD',
  triggerSource: 'NONE',
  'planner.plannerTeslaDeadlineSlot': false,
});

check('B1 MUST catch-up overrides planner', { nowMs: LATEST }, {
  priority: 'MUST',
  intent: 'TESLA_CHARGE_DEADLINE',
  triggerSource: 'LATEST_START_MUST',
});

check('B2 MUST catch-up disconnected', { nowMs: LATEST, plugged: false }, {
  priority: 'MUST',
  intent: 'TESLA_DEADLINE_BLOCKED_NOT_CONNECTED',
  triggerSource: 'LATEST_START_MUST',
});

check('B3 MUST remains MUST even low budget', { nowMs: LATEST, discretionaryImportBudgetW: 0 }, {
  priority: 'MUST',
  intent: 'TESLA_CHARGE_DEADLINE',
  triggerSource: 'LATEST_START_MUST',
});

check('C1 existing PV opportunity unchanged when no planner slot', {
  plannerTesla: 'HOLD',
  flexExportBudgetW: 1200,
}, {
  priority: 'SHOULD',
  intent: 'TESLA_CHARGE_OPPORTUNITY',
  triggerSource: 'REALTIME_OPPORTUNITY',
});

check('C2 existing negative-price opportunity unchanged', {
  plannerTesla: 'HOLD',
  priceNegative: true,
}, {
  priority: 'SHOULD',
  intent: 'TESLA_CHARGE_OPPORTUNITY',
  triggerSource: 'REALTIME_OPPORTUNITY',
});

check('C3 existing cheap-price opportunity unchanged', {
  plannerTesla: 'HOLD',
  priceCheapNext4h: true,
  teslaPriceBudgetOk: true,
}, {
  priority: 'SHOULD',
  intent: 'TESLA_CHARGE_OPPORTUNITY',
  triggerSource: 'REALTIME_OPPORTUNITY',
});

check('C4 no-deadline buffer export unchanged', {
  deadlineActive: false,
  plannerTesla: 'HOLD',
  flexExportBudgetW: 1600,
}, {
  priority: 'MAY',
  intent: 'TESLA_BUFFER_EXPORT',
  triggerSource: 'REALTIME_OPPORTUNITY',
});

check('C5 idle remains HOLD', {
  deadlineActive: false,
  plannerTesla: 'HOLD',
  flexExportBudgetW: 0,
}, {
  priority: 'MAY',
  intent: 'HOLD',
  triggerSource: 'NONE',
});

console.log('All Core v0.11e Planner Tesla decision regressions PASS');
