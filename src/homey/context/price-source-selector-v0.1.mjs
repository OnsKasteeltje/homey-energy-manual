// Price Source Selector v0.1 — SHADOW ONLY / NO PRODUCTION CUTOVER
// Pure deterministic logic. No Homey calls, no writes, no network access.

const NL_ZONE = '10YNL----------L';
const REQUIRED_BASIS = 'MARKET_EX_VAT';
const REQUIRED_RESOLUTION = 15;

function isoMs(value) {
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : null;
}

function sourceRank(source) {
  if (source === 'ENERGYZERO_PUBLIC_REST') return 1;
  if (source === 'PBTH_INTERAPP_DAP_PRICES') return 2;
  if (source === 'ENTSOE') return 3;
  return 99;
}

export function evaluatePriceSource(source, options = {}) {
  const {
    now = new Date().toISOString(),
    requiredHorizonStart = null,
    requiredHorizonEnd = null,
    maxAgeMinutes = 30,
  } = options;

  const reasons = [];
  const nowMs = isoMs(now);
  if (nowMs === null) throw new Error(`invalid now: ${now}`);

  if (!source || typeof source !== 'object') {
    return { eligible: false, reasons: ['MISSING_SOURCE'] };
  }

  if (source.schemaVersion !== 'price-source-v0.1') reasons.push('BAD_SCHEMA_VERSION');
  if (source.biddingZone !== NL_ZONE) reasons.push('BAD_BIDDING_ZONE');
  if (source.currency !== 'EUR') reasons.push('BAD_CURRENCY');
  if (source.resolutionMinutes !== REQUIRED_RESOLUTION) reasons.push('BAD_RESOLUTION');
  if (source.priceBasis !== REQUIRED_BASIS) reasons.push('BAD_PRICE_BASIS');
  if (source.health?.valid !== true) reasons.push('SOURCE_INVALID');
  if (source.health?.stale === true) reasons.push('SOURCE_STALE');
  if (!Array.isArray(source.slots) || source.slots.length === 0) reasons.push('NO_SLOTS');

  const retrievedMs = isoMs(source.retrievedAt);
  if (retrievedMs === null) {
    reasons.push('BAD_RETRIEVED_AT');
  } else if (nowMs - retrievedMs > maxAgeMinutes * 60000) {
    reasons.push('RETRIEVAL_TOO_OLD');
  }

  const firstSlotMs = Array.isArray(source.slots) && source.slots.length > 0
    ? isoMs(source.slots[0]?.start)
    : null;

  if (requiredHorizonStart) {
    const requiredStartMs = isoMs(requiredHorizonStart);
    if (requiredStartMs === null) throw new Error(`invalid requiredHorizonStart: ${requiredHorizonStart}`);
    if (firstSlotMs === null) {
      reasons.push('BAD_HORIZON_START');
    } else if (firstSlotMs > requiredStartMs) {
      reasons.push('HORIZON_START_TOO_LATE');
    }
  }

  const horizonMs = isoMs(source.health?.horizonEnd);
  if (horizonMs === null) {
    reasons.push('BAD_HORIZON_END');
  } else if (requiredHorizonEnd) {
    const requiredMs = isoMs(requiredHorizonEnd);
    if (requiredMs === null) throw new Error(`invalid requiredHorizonEnd: ${requiredHorizonEnd}`);
    if (horizonMs < requiredMs) reasons.push('HORIZON_TOO_SHORT');
  }

  if (Array.isArray(source.slots) && source.slots.length > 0) {
    let previous = null;
    for (let i = 0; i < source.slots.length; i += 1) {
      const slot = source.slots[i];
      const startMs = isoMs(slot?.start);
      const endMs = isoMs(slot?.end);
      const price = slot?.marketPriceEurPerKwh;
      if (startMs === null || endMs === null) {
        reasons.push('BAD_SLOT_TIMESTAMP');
        break;
      }
      if (endMs - startMs !== 15 * 60 * 1000) {
        reasons.push('BAD_SLOT_DURATION');
        break;
      }
      if (previous !== null && startMs - previous !== 15 * 60 * 1000) {
        reasons.push('SLOT_GAP_OR_DUPLICATE');
        break;
      }
      if (typeof price !== 'number' || !Number.isFinite(price)) {
        reasons.push('BAD_MARKET_PRICE');
        break;
      }
      previous = startMs;
    }
  }

  return {
    eligible: reasons.length === 0,
    reasons,
    source: source.source ?? null,
    horizonStart: Array.isArray(source.slots) && source.slots.length > 0 ? source.slots[0]?.start ?? null : null,
    horizonEnd: source.health?.horizonEnd ?? null,
    retrievedAt: source.retrievedAt ?? null,
    slotCount: Array.isArray(source.slots) ? source.slots.length : 0,
    rank: sourceRank(source.source),
  };
}

export function selectPriceSourceShadow(sources, options = {}) {
  const evaluations = (sources || []).map((source) => ({
    source,
    evaluation: evaluatePriceSource(source, options),
  }));

  const eligible = evaluations
    .filter((item) => item.evaluation.eligible)
    .sort((a, b) => {
      const rankDelta = a.evaluation.rank - b.evaluation.rank;
      if (rankDelta !== 0) return rankDelta;
      return Date.parse(b.evaluation.horizonEnd) - Date.parse(a.evaluation.horizonEnd);
    });

  const selected = eligible[0] ?? null;

  return {
    schema: 'EM2_PRICE_SOURCE_SELECTOR_SHADOW_V0.1',
    status: selected ? 'OK' : 'NO_ELIGIBLE_SOURCE',
    mode: 'SHADOW_READ_ONLY',
    selectedSource: selected?.source?.source ?? null,
    selectedHorizonStart: selected?.evaluation?.horizonStart ?? null,
    selectedHorizonEnd: selected?.evaluation?.horizonEnd ?? null,
    productionSwitchAllowed: false,
    evaluations: evaluations.map(({ source, evaluation }) => ({
      source: source?.source ?? null,
      eligible: evaluation.eligible,
      reasons: evaluation.reasons,
      horizonStart: evaluation.horizonStart,
      horizonEnd: evaluation.horizonEnd,
      retrievedAt: evaluation.retrievedAt,
      slotCount: evaluation.slotCount,
      rank: evaluation.rank,
    })),
  };
}
