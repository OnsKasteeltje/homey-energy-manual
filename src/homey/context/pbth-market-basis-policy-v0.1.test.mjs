import test from 'node:test';
import assert from 'node:assert/strict';
import { promotePbthToMarketExVat } from './pbth-market-basis-policy-v0.1.mjs';

function slots(field, values = [0.1, 0.2, 0.3], start = '2026-09-02T18:45:00.000Z') {
  const base = Date.parse(start);
  return values.map((value, i) => ({
    start: new Date(base + i * 900000).toISOString(),
    end: new Date(base + (i + 1) * 900000).toISOString(),
    [field]: value,
  }));
}

function pbth(overrides = {}) {
  return {
    schemaVersion: 'price-source-v0.1',
    source: 'PBTH_INTERAPP_DAP_PRICES',
    biddingZone: '10YNL----------L',
    currency: 'EUR',
    resolutionMinutes: 15,
    priceBasis: 'CONTRACT_IMPORT_UNKNOWN',
    slots: slots('importPriceEurPerKwh'),
    sourceMeta: { deviceId: 'nl' },
    ...overrides,
  };
}

function reference(overrides = {}) {
  return {
    schemaVersion: 'price-source-v0.1',
    source: 'ENERGYZERO_PUBLIC_REST',
    biddingZone: '10YNL----------L',
    currency: 'EUR',
    resolutionMinutes: 15,
    priceBasis: 'MARKET_EX_VAT',
    slots: slots('marketPriceEurPerKwh'),
    ...overrides,
  };
}

test('promotes exact overlapping PBTH prices to MARKET_EX_VAT', () => {
  const result = promotePbthToMarketExVat(pbth(), reference());
  assert.equal(result.confirmed, true);
  assert.equal(result.overlapSlots, 3);
  assert.equal(result.exactMatchSlots, 3);
  assert.equal(result.source.priceBasis, 'MARKET_EX_VAT');
  assert.equal(result.source.slots[1].marketPriceEurPerKwh, 0.2);
  assert.equal(result.source.sourceMeta.marketBasisPolicy, 'PBTH_MARKET_BASIS_POLICY_V0.1');
});

test('accepts only machine-level differences within tolerance', () => {
  const ref = reference({ slots: slots('marketPriceEurPerKwh', [0.1 + 2e-17, 0.2, 0.3]) });
  const result = promotePbthToMarketExVat(pbth(), ref);
  assert.equal(result.confirmed, true);
  assert.ok(result.maxAbsDelta <= 1e-12);
});

test('fails closed on semantic price mismatch', () => {
  const ref = reference({ slots: slots('marketPriceEurPerKwh', [0.1, 0.25, 0.3]) });
  const result = promotePbthToMarketExVat(pbth(), ref);
  assert.equal(result.confirmed, false);
  assert.ok(result.reasons.includes('SEMANTIC_MISMATCH'));
  assert.equal(result.source.priceBasis, 'CONTRACT_IMPORT_UNKNOWN');
});

test('fails closed when no timestamps overlap', () => {
  const ref = reference({ slots: slots('marketPriceEurPerKwh', [0.1, 0.2], '2026-09-03T18:45:00.000Z') });
  const result = promotePbthToMarketExVat(pbth(), ref);
  assert.equal(result.confirmed, false);
  assert.ok(result.reasons.includes('NO_OVERLAP'));
});

test('fails closed on wrong reference basis', () => {
  const result = promotePbthToMarketExVat(pbth(), reference({ priceBasis: 'ALL_IN_WITH_VAT' }));
  assert.equal(result.confirmed, false);
  assert.ok(result.reasons.includes('BAD_REFERENCE_BASIS'));
});

test('fails closed on bidding-zone mismatch', () => {
  const result = promotePbthToMarketExVat(pbth(), reference({ biddingZone: 'OTHER' }));
  assert.equal(result.confirmed, false);
  assert.ok(result.reasons.includes('BIDDING_ZONE_MISMATCH'));
});
