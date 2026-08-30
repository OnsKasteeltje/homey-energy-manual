// Contract Price Adapter v0.10 — pure short-horizon refresh logic
// PREPARED OUTSIDE HOMEY. No Homey API calls, no device writes, no PBTH calls.
// This module is intentionally pure so eligibility and semantic-change behavior can be tested before deployment.

const HORIZON_THRESHOLD_HOURS = 12;
const FAILED_REFRESH_COOLDOWN_MS = 60 * 60 * 1000;
const MIN_VALID_SLOTS = 4;
const SLOT_MINUTES = 15;

function finitePrice(value) {
  const n = Number(value);
  return Number.isFinite(n) && n > -2 && n < 5;
}

function normalizePrices(raw) {
  if (!Array.isArray(raw)) return [];
  const prices = [];
  for (const value of raw) {
    if (!finitePrice(value)) break;
    prices.push(Number(value));
  }
  return prices;
}

function priceFingerprint(prices) {
  return normalizePrices(prices).map(v => Number(v).toFixed(6)).join('|');
}

function horizonHours(prices) {
  return normalizePrices(prices).length * SLOT_MINUTES / 60;
}

function isCooldownActive(state, nowMs) {
  const ts = Date.parse(String(state?.lastNoChangeAt || ''));
  return Number.isFinite(ts) && nowMs - ts >= 0 && nowMs - ts < FAILED_REFRESH_COOLDOWN_MS;
}

function refreshEligibility({ contract, currentHorizonHours, state, nowMs = Date.now() }) {
  if (String(contract || '').toUpperCase() !== 'DYNAMIC') {
    return { eligible: false, reason: 'SKIP_NOT_DYNAMIC' };
  }
  if (Number(currentHorizonHours) >= HORIZON_THRESHOLD_HOURS) {
    return { eligible: false, reason: 'SKIP_HORIZON_OK' };
  }
  if (isCooldownActive(state, nowMs)) {
    return { eligible: false, reason: 'SKIP_COOLDOWN' };
  }
  return { eligible: true, reason: 'REFRESH_ALLOWED' };
}

function semanticPriceChange(previousRaw, nextRaw) {
  const previous = normalizePrices(previousRaw);
  const next = normalizePrices(nextRaw);
  if (next.length < MIN_VALID_SLOTS) {
    return { changed: false, acceptable: false, reason: 'NEXT_SERIES_DEGRADED', previous, next };
  }
  const previousFp = priceFingerprint(previous);
  const nextFp = priceFingerprint(next);
  const grew = next.length > previous.length;
  const differs = nextFp !== previousFp;
  return {
    changed: grew || differs,
    acceptable: true,
    reason: grew ? 'HORIZON_EXTENDED' : differs ? 'PRICE_SERIES_CHANGED' : 'NO_SEMANTIC_CHANGE',
    previous,
    next,
    previousFingerprint: previousFp,
    nextFingerprint: nextFp
  };
}

function applyRefreshResult({ previousPrices, nextPrices, state = {}, nowIso = new Date().toISOString() }) {
  const comparison = semanticPriceChange(previousPrices, nextPrices);
  const nextState = {
    schema: 'EM2_PRICE_EVENT_REFRESH_STATE_V0.1',
    lastAttemptAt: nowIso,
    lastNoChangeAt: state.lastNoChangeAt ?? null,
    lastSuccessAt: state.lastSuccessAt ?? null,
    lastAcceptedSlots: state.lastAcceptedSlots ?? null,
    lastAcceptedFingerprint: state.lastAcceptedFingerprint ?? null
  };

  if (!comparison.acceptable || !comparison.changed) {
    nextState.lastNoChangeAt = nowIso;
    return {
      outcome: comparison.acceptable ? 'NO_CHANGE_COOLDOWN_STARTED' : 'DEGRADED_KEEP_PRIOR_CONTEXT',
      publish: false,
      acceptedPrices: comparison.previous,
      state: nextState,
      comparison
    };
  }

  nextState.lastSuccessAt = nowIso;
  nextState.lastNoChangeAt = null;
  nextState.lastAcceptedSlots = comparison.next.length;
  nextState.lastAcceptedFingerprint = comparison.nextFingerprint;
  return {
    outcome: 'UPDATED',
    publish: true,
    acceptedPrices: comparison.next,
    state: nextState,
    comparison
  };
}

module.exports = {
  HORIZON_THRESHOLD_HOURS,
  FAILED_REFRESH_COOLDOWN_MS,
  MIN_VALID_SLOTS,
  SLOT_MINUTES,
  normalizePrices,
  priceFingerprint,
  horizonHours,
  isCooldownActive,
  refreshEligibility,
  semanticPriceChange,
  applyRefreshResult
};
