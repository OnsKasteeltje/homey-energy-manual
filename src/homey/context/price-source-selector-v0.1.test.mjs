import assert from 'node:assert/strict';
import { evaluatePriceSource, selectPriceSourceShadow } from './price-source-selector-v0.1.mjs';

const now = '2026-09-01T18:45:00.000Z';
const requiredHorizonStart = '2026-09-01T18:45:00.000Z';
const requiredHorizonEnd = '2026-09-02T22:00:00.000Z';

function makeSlots(count = 4, start = '2026-09-01T18:45:00.000Z', field = 'marketPriceEurPerKwh') {
  const base = Date.parse(start);
  return Array.from({ length: count }, (_, i) => ({
    start: new Date(base + i * 900000).toISOString(),
    end: new Date(base + (i + 1) * 900000).toISOString(),
    [field]: 0.1 + i / 1000,
  }));
}

function makeSource(source, overrides = {}) {
  return {
    schemaVersion: 'price-source-v0.1',
    source,
    biddingZone: '10YNL----------L',
    currency: 'EUR',
    resolutionMinutes: 15,
    retrievedAt: '2026-09-01T18:44:00.000Z',
    priceBasis: 'MARKET_EX_VAT',
    slots: makeSlots(),
    health: {
      valid: true,
      complete: true,
      stale: false,
      horizonEnd: '2026-09-02T22:00:00.000Z',
    },
    ...overrides,
  };
}

const options = { now, requiredHorizonStart, requiredHorizonEnd };
const ez = makeSource('ENERGYZERO_PUBLIC_REST');
const pbth = makeSource('PBTH_INTERAPP_DAP_PRICES');

assert.equal(evaluatePriceSource(ez, options).eligible, true);

{
  const result = selectPriceSourceShadow([pbth, ez], options);
  assert.equal(result.status, 'OK');
  assert.equal(result.selectedSource, 'ENERGYZERO_PUBLIC_REST');
  assert.equal(result.productionSwitchAllowed, false);
}

{
  const badEz = makeSource('ENERGYZERO_PUBLIC_REST', {
    health: { valid: true, complete: false, stale: false, horizonEnd: '2026-09-02T12:00:00.000Z' },
  });
  const result = selectPriceSourceShadow([badEz, pbth], options);
  assert.equal(result.selectedSource, 'PBTH_INTERAPP_DAP_PRICES');
  assert.ok(result.evaluations.find(x => x.source === 'ENERGYZERO_PUBLIC_REST').reasons.includes('HORIZON_TOO_SHORT'));
}

{
  const lateStart = makeSource('ENERGYZERO_PUBLIC_REST', {
    slots: makeSlots(4, '2026-09-01T19:00:00.000Z'),
  });
  const evaluation = evaluatePriceSource(lateStart, options);
  assert.equal(evaluation.eligible, false);
  assert.ok(evaluation.reasons.includes('HORIZON_START_TOO_LATE'));
}

{
  const badBasis = makeSource('ENERGYZERO_PUBLIC_REST', { priceBasis: 'ALL_IN_WITH_VAT' });
  const evaluation = evaluatePriceSource(badBasis, options);
  assert.equal(evaluation.eligible, false);
  assert.ok(evaluation.reasons.includes('BAD_PRICE_BASIS'));
}

{
  const stale = makeSource('ENERGYZERO_PUBLIC_REST', { retrievedAt: '2026-09-01T17:00:00.000Z' });
  const evaluation = evaluatePriceSource(stale, { ...options, maxAgeMinutes: 30 });
  assert.equal(evaluation.eligible, false);
  assert.ok(evaluation.reasons.includes('RETRIEVAL_TOO_OLD'));
}

{
  const gap = makeSource('ENERGYZERO_PUBLIC_REST');
  gap.slots[2].start = new Date(Date.parse(gap.slots[2].start) + 900000).toISOString();
  gap.slots[2].end = new Date(Date.parse(gap.slots[2].end) + 900000).toISOString();
  const evaluation = evaluatePriceSource(gap, options);
  assert.equal(evaluation.eligible, false);
  assert.ok(evaluation.reasons.includes('SLOT_GAP_OR_DUPLICATE'));
}

{
  const none = selectPriceSourceShadow([
    makeSource('ENERGYZERO_PUBLIC_REST', { priceBasis: 'ALL_IN_WITH_VAT' }),
    makeSource('PBTH_INTERAPP_DAP_PRICES', { health: { valid: false, stale: false, horizonEnd: requiredHorizonEnd } }),
  ], options);
  assert.equal(none.status, 'NO_ELIGIBLE_SOURCE');
  assert.equal(none.selectedSource, null);
}

console.log('price-source-selector-v0.1: 7/7 PASS');
