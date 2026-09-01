import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeEnergyZero, normalizeEnergyZeroRest, normalizePbthInterApp, compareByTimestamp, PriceSourceError } from './price-source-normalizer-v0.1.mjs';

const t0 = '2026-09-01T10:00:00Z';
const t1 = '2026-09-01T10:15:00Z';
const t2 = '2026-09-01T10:30:00Z';

function ez(prices = [[t0, 0.1], [t1, 0.2], [t2, 0.3]]) {
  return { intervalType: 3, Prices: prices.map(([readingDate, price]) => ({ readingDate, price })) };
}

function restRows(startIso, count, startPrice = 0.1) {
  const startMs = Date.parse(startIso);
  return Array.from({ length: count }, (_, i) => ({
    start: new Date(startMs + i * 15 * 60 * 1000).toISOString().replace('.000Z', 'Z'),
    end: new Date(startMs + (i + 1) * 15 * 60 * 1000).toISOString().replace('.000Z', 'Z'),
    price: { value: startPrice + i / 10000 },
  }));
}

test('normalizes current EnergyZero REST market stream and filters Amsterdam local date', () => {
  const payload = { base: restRows('2026-08-30T22:00:00Z', 288) };
  const out = normalizeEnergyZeroRest(payload, {
    localDate: '2026-09-01',
    retrievedAt: '2026-09-01T18:30:00Z',
  });
  assert.equal(out.source, 'ENERGYZERO_PUBLIC_REST');
  assert.equal(out.priceBasis, 'MARKET_EX_VAT');
  assert.equal(out.slots.length, 96);
  assert.equal(out.slots[0].start, '2026-08-31T22:00:00.000Z');
  assert.equal(out.slots.at(-1).end, '2026-09-01T22:00:00.000Z');
  assert.equal(out.health.complete, true);
  assert.equal(out.sourceMeta.rawStreamCount, 288);
});

test('current EnergyZero REST rejects malformed or non-quarter-hour slots', () => {
  assert.throws(() => normalizeEnergyZeroRest({ base: [{ start: t0, end: t1, price: { value: null } }] }), e => e instanceof PriceSourceError && e.code === 'BAD_PRICE');
  assert.throws(() => normalizeEnergyZeroRest({ base: [{ start: t0, end: t2, price: { value: 0.1 } }] }), e => e instanceof PriceSourceError && e.code === 'WRONG_RESOLUTION');
});

test('legacy EnergyZero normalizer now fails closed on price basis', () => {
  const out = normalizeEnergyZero(ez(), { retrievedAt: '2026-09-01T11:00:00Z' });
  assert.equal(out.source, 'ENERGYZERO_LEGACY');
  assert.equal(out.priceBasis, 'SOURCE_PRICE_UNKNOWN');
  assert.equal(out.slots.length, 3);
});

test('rejects legacy EnergyZero gaps and duplicates', () => {
  assert.throws(() => normalizeEnergyZero(ez([[t0, 0.1], [t2, 0.3]])), e => e instanceof PriceSourceError && e.code === 'SLOT_GAP');
  assert.throws(() => normalizeEnergyZero(ez([[t0, 0.1], [t0, 0.2]])), e => e instanceof PriceSourceError && e.code === 'DUPLICATE_TIMESTAMP');
});

test('normalizes exactly one NL PBTH dap15 device', () => {
  const out = normalizePbthInterApp({
    generatedAt: '2026-09-01T09:59:00Z',
    prices: [{
      deviceId: 'nl', deviceName: 'NL', driverType: 'dap15', biddingZone: '10YNL----------L', currency: 'EUR', priceInterval: 15,
      slots: [
        { time: t0, importPrice: 0.30, exportPrice: 0.25, isForecast: false },
        { time: t1, importPrice: 0.31, exportPrice: 0.26, isForecast: true },
      ],
    }],
  }, { retrievedAt: '2026-09-01T10:01:00Z' });
  assert.equal(out.sourceMeta.deviceId, 'nl');
  assert.equal(out.slots[1].isForecast, true);
  assert.equal(out.priceBasis, 'CONTRACT_IMPORT_UNKNOWN');
});

test('A/B comparison aligns by timestamp, never array position', () => {
  const left = normalizeEnergyZero(ez([[t0, 0.1], [t1, 0.2], [t2, 0.3]]));
  const right = { slots: [
    { start: '2026-09-01T10:15:00.000Z', marketPriceEurPerKwh: 0.21 },
    { start: '2026-09-01T10:30:00.000Z', marketPriceEurPerKwh: 0.29 },
  ]};
  const cmp = compareByTimestamp(left, right);
  assert.equal(cmp.overlapCount, 2);
  assert.equal(cmp.rows[0].timestamp, '2026-09-01T10:15:00.000Z');
  assert.ok(Math.abs(cmp.rows[0].delta + 0.01) < 1e-12);
});
