import test from 'node:test';
import assert from 'node:assert/strict';
import { expectedQuarterHourSlotsForLocalDate, validateLocalDaySlots } from './price-source-dst-v0.1.mjs';

function makeSlots(startIso, count) {
  const startMs = Date.parse(startIso);
  return Array.from({ length: count }, (_, i) => ({
    start: new Date(startMs + i * 15 * 60 * 1000).toISOString(),
    end: new Date(startMs + (i + 1) * 15 * 60 * 1000).toISOString(),
    marketPriceEurPerKwh: 0.1,
  }));
}

test('normal CET/CEST day expects 96 quarter-hours', () => {
  assert.equal(expectedQuarterHourSlotsForLocalDate('2026-09-03'), 96);
});

test('spring DST transition day expects 92 quarter-hours', () => {
  assert.equal(expectedQuarterHourSlotsForLocalDate('2026-03-29'), 92);
  const result = validateLocalDaySlots(makeSlots('2026-03-28T23:00:00.000Z', 92), '2026-03-29');
  assert.equal(result.complete, true);
  assert.equal(result.expectedSlotCount, 92);
});

test('fall DST transition day expects 100 quarter-hours', () => {
  assert.equal(expectedQuarterHourSlotsForLocalDate('2026-10-25'), 100);
  const result = validateLocalDaySlots(makeSlots('2026-10-24T22:00:00.000Z', 100), '2026-10-25');
  assert.equal(result.complete, true);
  assert.equal(result.expectedSlotCount, 100);
});

test('wrong slot count fails closed on DST day', () => {
  const result = validateLocalDaySlots(makeSlots('2026-03-28T23:00:00.000Z', 96), '2026-03-29');
  assert.equal(result.complete, false);
  assert.equal(result.expectedSlotCount, 92);
  assert.equal(result.actualSlotCount, 96);
});
