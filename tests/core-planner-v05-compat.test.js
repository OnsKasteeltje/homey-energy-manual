'use strict';

const assert = require('assert');
const { parsePlannerForCore } = require('../src/homey/core/core-planner-v05-compat');

const NOW = Date.parse('2026-09-01T10:07:00.000Z'); // 12:07 Europe/Amsterdam

function snap(schema, slot, generatedAt = '2026-09-01T10:00:45.000Z') {
  return {
    generatedAt,
    plan: {
      schema,
      generatedAt,
      plan: { actions: [slot] },
    },
  };
}

function slot(overrides = {}) {
  return {
    start: '2026-09-01T10:00:00.000Z',
    end: '2026-09-01T10:15:00.000Z',
    localDate: '2026-09-01',
    warmWaterDayRelation: 'CURRENT_DAY',
    warmWater: 'HOLD',
    targets: { wwTargetW: 0 },
    ...overrides,
  };
}

{
  const r = parsePlannerForCore(snap('EM2_ENERGY_PLAN_24H_V0.5.0', slot({
    warmWater: 'PV_PREFERRED',
    targets: { wwTargetW: 1900 },
    warmWaterReason: 'PV_SURPLUS_FULL',
  })), { nowMs: NOW });
  assert.equal(r.compatible, true);
  assert.equal(r.plannerPvSlot, true);
  assert.equal(r.plannerGridSlot, false);
  assert.equal(r.wwTargetW, 1900);
}

{
  const r = parsePlannerForCore(snap('EM2_ENERGY_PLAN_24H_V0.5.0', slot({
    warmWater: 'DEADLINE_REQUIRED',
    targets: { wwTargetW: 1900 },
  })), { nowMs: NOW });
  assert.equal(r.compatible, true);
  assert.equal(r.plannerGridSlot, true);
}

{
  const r = parsePlannerForCore(snap('EM2_ENERGY_PLAN_24H_V0.5.0', slot()), { nowMs: NOW });
  assert.equal(r.compatible, true);
  assert.equal(r.plannerWW, 'HOLD');
  assert.equal(r.wwTargetW, 0);
}

{
  const r = parsePlannerForCore(snap('EM2_ENERGY_PLAN_24H_V0.5.0', slot({
    warmWater: 'PV_PREFERRED',
    targets: { wwTargetW: 807 },
  })), { nowMs: NOW });
  assert.equal(r.compatible, false);
  assert.equal(r.compatibilityReason, 'INVALID_WW_TARGET');
}

{
  const r = parsePlannerForCore(snap('EM2_ENERGY_PLAN_24H_V0.5.0', slot({
    localDate: '2026-09-02',
    warmWaterDayRelation: 'FUTURE_DAY',
    warmWater: 'PV_PREFERRED',
    targets: { wwTargetW: 1900 },
  })), { nowMs: NOW });
  assert.equal(r.compatible, false);
  assert.equal(r.compatibilityReason, 'NON_CURRENT_DAY_SLOT');
}

{
  const r = parsePlannerForCore(snap('EM2_ENERGY_PLAN_24H_V0.5.0', slot({
    warmWater: 'HOLD',
    targets: { wwTargetW: 1900 },
  })), { nowMs: NOW });
  assert.equal(r.compatible, false);
  assert.equal(r.compatibilityReason, 'TARGET_ACTION_MISMATCH');
}

{
  const r = parsePlannerForCore(snap('EM2_ENERGY_PLAN_24H_V0.5.0', slot(), '2026-09-01T09:00:00.000Z'), {
    nowMs: NOW,
    freshMs: 35 * 60 * 1000,
  });
  assert.equal(r.compatible, false);
  assert.equal(r.compatibilityReason, 'PLANNER_STALE');
}

{
  const r = parsePlannerForCore(snap('EM2_ENERGY_PLAN_24H_V0.4.9', {
    start: '2026-09-01T10:00:00.000Z',
    end: '2026-09-01T10:15:00.000Z',
    warmWater: 'PV_PREFERRED',
  }), { nowMs: NOW });
  assert.equal(r.compatible, true);
  assert.equal(r.plannerPvSlot, true);
  assert.equal(r.wwTargetW, 1900);
}

console.log('PASS core-planner-v05-compat');
