'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { optimizeWarmWater } = require('../src/homey/planner/planner-v0.5-ww-optimizer');

function slot(i, hour, minute, { pv = 0, base = 500, price = 0.20, flex = 0 } = {}) {
  const hh = String(hour).padStart(2, '0');
  const mm = String(minute).padStart(2, '0');
  const start = `2026-08-31T${hh}:${mm}:00.000Z`;
  const endMs = Date.parse(start) + 15 * 60 * 1000;
  return {
    i,
    start,
    end: new Date(endMs).toISOString(),
    pvForecastW: pv,
    baseLoadForecastW: base,
    price_eur_kwh: price,
    alreadyAllocatedFlexibleLoadW: flex,
  };
}

test('selects separated high-PV slots: no artificial contiguous WW window', () => {
  const slots = [
    slot(0, 9, 0, { pv: 2600, base: 500 }),
    slot(1, 9, 15, { pv: 700, base: 500, price: 0.05 }),
    slot(2, 9, 30, { pv: 2800, base: 500 }),
    slot(3, 9, 45, { pv: 650, base: 500, price: 0.01 }),
  ];
  const result = optimizeWarmWater({
    slots,
    wwRemainingEnergyKWh: 0.95,
    contract: 'DYNAMIC',
  });
  const chosen = result.actions.filter((x) => x.targets.wwTargetW > 0).map((x) => x.i);
  assert.deepEqual(chosen, [0, 2]);
  assert.equal(result.estimatedGridEnergyKWh, 0);
});

test('PV-first beats cheaper imported electricity', () => {
  const slots = [
    slot(0, 10, 0, { pv: 2600, base: 500, price: 0.30 }),
    slot(1, 10, 15, { pv: 500, base: 500, price: -0.05 }),
  ];
  const result = optimizeWarmWater({
    slots,
    wwRemainingEnergyKWh: 0.475,
    contract: 'DYNAMIC',
  });
  const chosen = result.actions.find((x) => x.targets.wwTargetW > 0);
  assert.equal(chosen.i, 0);
  assert.equal(chosen.allocationReason, 'PV_FULL');
});

test('deadline fallback uses lowest marginal import then price', () => {
  const slots = [
    slot(0, 11, 0, { pv: 600, base: 500, price: 0.10 }), // 1800 W grid
    slot(1, 11, 15, { pv: 1200, base: 500, price: 0.35 }), // 1200 W grid
    slot(2, 11, 30, { pv: 1200, base: 500, price: 0.20 }), // 1200 W grid, cheaper tie
  ];
  const result = optimizeWarmWater({
    slots,
    wwRemainingEnergyKWh: 0.475,
    contract: 'DYNAMIC',
  });
  const chosen = result.actions.find((x) => x.targets.wwTargetW > 0);
  assert.equal(chosen.i, 2);
  assert.equal(chosen.score.marginalImportW, 1200);
});

test('already allocated flexible load is subtracted from residual PV', () => {
  const slots = [
    slot(0, 12, 0, { pv: 4000, base: 500, flex: 2500 }), // only 1000 W residual
    slot(1, 12, 15, { pv: 3000, base: 500, flex: 0 }), // 2500 W residual -> full WW
  ];
  const result = optimizeWarmWater({ slots, wwRemainingEnergyKWh: 0.475, contract: 'DYNAMIC' });
  const chosen = result.actions.find((x) => x.targets.wwTargetW > 0);
  assert.equal(chosen.i, 1);
  assert.equal(result.actions[0].availableSurplusW, 1000);
});

test('goalReachedToday suppresses mandatory same-day WW', () => {
  const slots = [slot(0, 13, 0, { pv: 5000, base: 500 })];
  const result = optimizeWarmWater({
    slots,
    wwRemainingEnergyKWh: 7.6,
    goalReachedToday: true,
    contract: 'DYNAMIC',
  });
  assert.equal(result.requestedEnergyKWh, 0);
  assert.equal(result.selectedSlots, 0);
  assert.equal(result.actions[0].targets.wwTargetW, 0);
});

test('deadline excludes slots starting at or after the deadline', () => {
  const slots = [
    slot(0, 16, 30, { pv: 500, base: 500, price: 0.20 }),
    slot(1, 17, 0, { pv: 5000, base: 500, price: 0.05 }),
  ];
  const deadlineMs = Date.parse('2026-08-31T17:00:00.000Z');
  const result = optimizeWarmWater({
    slots,
    wwRemainingEnergyKWh: 0.475,
    deadlineMs,
    contract: 'DYNAMIC',
  });
  const chosen = result.actions.find((x) => x.targets.wwTargetW > 0);
  assert.equal(chosen.i, 0);
});

test('candidate stays SHADOW-only and never claims physical writes', () => {
  const result = optimizeWarmWater({ slots: [], wwRemainingEnergyKWh: 0 });
  assert.equal(result.shadowOnly, true);
  assert.equal(result.physicalWritePerformed, false);
});
