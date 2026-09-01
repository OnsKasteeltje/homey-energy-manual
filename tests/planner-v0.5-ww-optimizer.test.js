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
    slot(0, 11, 0, { pv: 600, base: 500, price: 0.10 }),
    slot(1, 11, 15, { pv: 1200, base: 500, price: 0.35 }),
    slot(2, 11, 30, { pv: 1200, base: 500, price: 0.20 }),
  ];
  const result = optimizeWarmWater({
    slots,
    wwRemainingEnergyKWh: 0.475,
    deadlineMs: Date.parse('2026-08-31T11:45:00.000Z'),
    contract: 'DYNAMIC',
  });
  const chosen = result.actions.find((x) => x.targets.wwTargetW > 0);
  assert.equal(result.deadlineUrgent, true);
  assert.equal(chosen.i, 2);
  assert.equal(chosen.score.marginalImportW, 1200);
});

test('defers grid fallback while deadline still has spare quarters', () => {
  const slots = [
    slot(0, 14, 0, { pv: 500, base: 500, price: 0.01 }),
    slot(1, 14, 15, { pv: 500, base: 500, price: 0.02 }),
    slot(2, 14, 30, { pv: 500, base: 500, price: 0.03 }),
    slot(3, 14, 45, { pv: 500, base: 500, price: 0.04 }),
  ];
  const result = optimizeWarmWater({
    slots,
    wwRemainingEnergyKWh: 0.475,
    deadlineMs: Date.parse('2026-08-31T15:00:00.000Z'),
    contract: 'DYNAMIC',
    gridFallbackSafetySlots: 2,
  });
  assert.equal(result.gridSlotsNeeded, 1);
  assert.equal(result.deadlineUrgent, false);
  assert.equal(result.gridFallbackActive, false);
  assert.equal(result.selectedSlots, 0);
  assert.equal(result.unallocatedEnergyKWh, 0.475);
});

test('activates only minimum grid fallback when deadline feasibility becomes tight', () => {
  const slots = [
    slot(0, 14, 15, { pv: 500, base: 500, price: 0.30 }),
    slot(1, 14, 30, { pv: 500, base: 500, price: 0.10 }),
    slot(2, 14, 45, { pv: 500, base: 500, price: 0.20 }),
  ];
  const result = optimizeWarmWater({
    slots,
    wwRemainingEnergyKWh: 0.475,
    deadlineMs: Date.parse('2026-08-31T15:00:00.000Z'),
    contract: 'DYNAMIC',
    gridFallbackSafetySlots: 2,
  });
  assert.equal(result.deadlineUrgent, true);
  assert.equal(result.gridFallbackActive, true);
  assert.equal(result.selectedSlots, 1);
  const chosen = result.actions.find((x) => x.targets.wwTargetW > 0);
  assert.equal(chosen.i, 1);
});

test('already allocated flexible load is subtracted from residual PV', () => {
  const slots = [
    slot(0, 12, 0, { pv: 4000, base: 500, flex: 2500 }),
    slot(1, 12, 15, { pv: 3000, base: 500, flex: 0 }),
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

test('partial final demand is accounted without inflating analyzed energy', () => {
  const slots = [slot(0, 15, 0, { pv: 3000, base: 500 })];
  const result = optimizeWarmWater({ slots, wwRemainingEnergyKWh: 0.202, contract: 'DYNAMIC' });
  assert.equal(result.selectedSlots, 1);
  assert.equal(result.allocatedDemandKWh, 0.202);
  assert.equal(result.scheduledEnergyKWh, 0.475);
  assert.equal(result.plannedExcessEnergyKWh, 0.273);
  assert.equal(result.estimatedPvEnergyKWh, 0.202);
});

test('candidate stays SHADOW-only and never claims physical writes', () => {
  const result = optimizeWarmWater({ slots: [], wwRemainingEnergyKWh: 0 });
  assert.equal(result.shadowOnly, true);
  assert.equal(result.physicalWritePerformed, false);
});
