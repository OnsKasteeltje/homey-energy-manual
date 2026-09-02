// PBTH Market Basis Policy v0.1 — SHADOW ONLY / NO PRODUCTION CUTOVER
//
// Purpose: make the semantic promotion from PBTH importPrice to normalized
// MARKET_EX_VAT explicit, evidence-based and fail-closed. The normalizer remains
// conservative; only this policy may promote a PBTH source after an exact live
// comparison against a trusted MARKET_EX_VAT reference series.

const REQUIRED_SOURCE = 'PBTH_INTERAPP_DAP_PRICES';
const REQUIRED_REFERENCE_BASIS = 'MARKET_EX_VAT';
const DEFAULT_TOLERANCE = 1e-12;

function byStart(slots = []) {
  return new Map(slots.map((slot) => [slot.start, slot]));
}

export function promotePbthToMarketExVat(pbth, reference, options = {}) {
  const tolerance = options.tolerance ?? DEFAULT_TOLERANCE;
  const reasons = [];

  if (!pbth || pbth.source !== REQUIRED_SOURCE) reasons.push('BAD_PBTH_SOURCE');
  if (!reference || reference.priceBasis !== REQUIRED_REFERENCE_BASIS) reasons.push('BAD_REFERENCE_BASIS');
  if (pbth?.biddingZone !== reference?.biddingZone) reasons.push('BIDDING_ZONE_MISMATCH');
  if (pbth?.currency !== reference?.currency) reasons.push('CURRENCY_MISMATCH');
  if (pbth?.resolutionMinutes !== 15 || reference?.resolutionMinutes !== 15) reasons.push('BAD_RESOLUTION');
  if (!Array.isArray(pbth?.slots) || pbth.slots.length === 0) reasons.push('NO_PBTH_SLOTS');
  if (!Array.isArray(reference?.slots) || reference.slots.length === 0) reasons.push('NO_REFERENCE_SLOTS');

  let overlapSlots = 0;
  let exactMatchSlots = 0;
  let maxAbsDelta = 0;

  if (reasons.length === 0) {
    const referenceMap = byStart(reference.slots);
    for (const slot of pbth.slots) {
      const ref = referenceMap.get(slot.start);
      if (!ref) continue;
      overlapSlots += 1;
      const pbthPrice = slot.importPriceEurPerKwh;
      const refPrice = ref.marketPriceEurPerKwh;
      if (!Number.isFinite(pbthPrice) || !Number.isFinite(refPrice)) {
        reasons.push('NON_FINITE_OVERLAP_PRICE');
        break;
      }
      const delta = Math.abs(pbthPrice - refPrice);
      maxAbsDelta = Math.max(maxAbsDelta, delta);
      if (delta <= tolerance) exactMatchSlots += 1;
    }
    if (overlapSlots === 0) reasons.push('NO_OVERLAP');
    if (overlapSlots > 0 && exactMatchSlots !== overlapSlots) reasons.push('SEMANTIC_MISMATCH');
  }

  const confirmed = reasons.length === 0;
  if (!confirmed) {
    return {
      confirmed: false,
      reasons,
      overlapSlots,
      exactMatchSlots,
      maxAbsDelta,
      source: pbth,
    };
  }

  return {
    confirmed: true,
    reasons: [],
    overlapSlots,
    exactMatchSlots,
    maxAbsDelta,
    source: {
      ...pbth,
      priceBasis: 'MARKET_EX_VAT',
      slots: pbth.slots.map((slot) => ({
        ...slot,
        marketPriceEurPerKwh: slot.importPriceEurPerKwh,
      })),
      sourceMeta: {
        ...(pbth.sourceMeta || {}),
        marketBasisPolicy: 'PBTH_MARKET_BASIS_POLICY_V0.1',
        marketBasisEvidence: {
          referenceSource: reference.source ?? null,
          overlapSlots,
          exactMatchSlots,
          maxAbsDelta,
          tolerance,
        },
      },
    },
  };
}
