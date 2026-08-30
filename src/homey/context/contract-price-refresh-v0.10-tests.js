// Offline acceptance tests for Contract Price Adapter v0.10 short-horizon refresh.
// Run with Node.js only; no Homey connection required.

const assert = require('assert');
const logic = require('./contract-price-refresh-v0.10-logic');

const now = Date.parse('2026-08-30T12:00:00Z');
const iso = ms => new Date(ms).toISOString();
const prices = n => Array.from({ length: n }, (_, i) => 0.20 + i / 10000);

// A. Horizon >= 12h => event does not request PBTH.
{
  const r = logic.refreshEligibility({ contract: 'DYNAMIC', currentHorizonHours: 12, state: {}, nowMs: now });
  assert.deepStrictEqual(r, { eligible: false, reason: 'SKIP_HORIZON_OK' });
}

// B. Horizon < 12h, cooldown clear => exactly one refresh may be admitted by topology.
{
  const r = logic.refreshEligibility({ contract: 'DYNAMIC', currentHorizonHours: 11.75, state: {}, nowMs: now });
  assert.deepStrictEqual(r, { eligible: true, reason: 'REFRESH_ALLOWED' });
  const update = logic.applyRefreshResult({ previousPrices: prices(47), nextPrices: prices(60), nowIso: iso(now) });
  assert.strictEqual(update.publish, true);
  assert.strictEqual(update.outcome, 'UPDATED');
  assert.strictEqual(update.state.lastNoChangeAt, null);
}

// C. No new price information => no publication and cooldown starts.
{
  const p = prices(47);
  const r = logic.applyRefreshResult({ previousPrices: p, nextPrices: p, nowIso: iso(now) });
  assert.strictEqual(r.publish, false);
  assert.strictEqual(r.outcome, 'NO_CHANGE_COOLDOWN_STARTED');
  assert.strictEqual(r.state.lastNoChangeAt, iso(now));
}

// D. Repeated event during cooldown => blocked before PBTH request.
{
  const state = { lastNoChangeAt: iso(now) };
  const r = logic.refreshEligibility({ contract: 'DYNAMIC', currentHorizonHours: 8, state, nowMs: now + 30 * 60 * 1000 });
  assert.deepStrictEqual(r, { eligible: false, reason: 'SKIP_COOLDOWN' });
}

// E. After 60 minutes, still short => one new attempt may be admitted.
{
  const state = { lastNoChangeAt: iso(now) };
  const r = logic.refreshEligibility({ contract: 'DYNAMIC', currentHorizonHours: 8, state, nowMs: now + 60 * 60 * 1000 });
  assert.deepStrictEqual(r, { eligible: true, reason: 'REFRESH_ALLOWED' });
}

// F. Successful update clears prior cooldown.
{
  const state = { lastNoChangeAt: iso(now - 2 * 60 * 60 * 1000) };
  const next = prices(48); next[4] += 0.01;
  const r = logic.applyRefreshResult({ previousPrices: prices(48), nextPrices: next, state, nowIso: iso(now) });
  assert.strictEqual(r.publish, true);
  assert.strictEqual(r.state.lastNoChangeAt, null);
  assert.strictEqual(r.state.lastSuccessAt, iso(now));
}

// G. FIXED never enters event refresh path.
{
  const r = logic.refreshEligibility({ contract: 'FIXED', currentHorizonHours: 0, state: {}, nowMs: now });
  assert.deepStrictEqual(r, { eligible: false, reason: 'SKIP_NOT_DYNAMIC' });
}

// Guard: degraded/short invalid response never replaces the prior accepted series.
{
  const prev = prices(40);
  const r = logic.applyRefreshResult({ previousPrices: prev, nextPrices: [0.2, 0.21], nowIso: iso(now) });
  assert.strictEqual(r.publish, false);
  assert.strictEqual(r.outcome, 'DEGRADED_KEEP_PRIOR_CONTEXT');
  assert.deepStrictEqual(r.acceptedPrices, prev);
}

console.log('PASS: Contract Price Adapter v0.10 offline acceptance suite');
