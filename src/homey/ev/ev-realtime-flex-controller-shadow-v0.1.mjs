// EV Realtime Flex Controller v0.1 — SHADOW evaluator
// Pure function only: no Homey API calls, no Logic writes, no device writes.
// Intended to be called from a Homey Advanced Flow/HomeyScript wrapper later.

export const SCHEMA = 'EM2_EV_REALTIME_FLEX_SHADOW_V0.1';
export const ENVELOPE_SCHEMA = 'EMS_PI_EV_REALTIME_ENVELOPE_V0.2';
export const EV_W_PER_A = 690;
export const MIN_A = 6;
export const MAX_A = 16;

function finiteNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

function blocked(reason, input = {}) {
  return {
    schema: SCHEMA,
    generatedAt: new Date().toISOString(),
    mode: 'SHADOW',
    quality: 'BLOCKED',
    reason,
    piSlotTargetA: finiteNumber(input.piSlotTargetA) ?? 0,
    piSlotTargetW: finiteNumber(input.piSlotTargetW) ?? 0,
    envelopeAllowed: false,
    envelopeMinA: 0,
    envelopeMaxA: 0,
    p1W: finiteNumber(input.p1W),
    evActualW: finiteNumber(input.evActualW),
    counterfactualSurplusW: 0,
    smoothedSurplusW: 0,
    candidateA: 0,
    candidateW: 0,
    deviceWrites: false,
    logicWrites: false,
  };
}

export function evaluateEvRealtimeFlexShadow(input) {
  const envelope = input?.envelope || {};

  if (input?.plannerAuthority !== 'PI') return blocked('PLANNER_AUTHORITY_NOT_PI', input);
  if (input?.controlStatus !== 'READY') return blocked('PI_CONTROL_NOT_READY', input);
  if (input?.contractMode !== 'FIXED' || input?.contractId !== 'ENGIE_3Y_2026_2029') {
    return blocked('CONTRACT_POLICY_MISMATCH', input);
  }
  if (envelope.schema !== ENVELOPE_SCHEMA) return blocked('ENVELOPE_SCHEMA_MISMATCH', input);
  if (envelope.shadowOnly !== true || envelope.productionConsumerAllowed !== false) {
    return blocked('ENVELOPE_NOT_SHADOW_SAFE', input);
  }
  if (envelope.allowed !== true || envelope.mode !== 'PV_OPPORTUNITY') {
    return blocked(envelope.blockReason || 'ENVELOPE_BLOCKED', input);
  }
  if (input?.teslaConnected !== true) return blocked('TESLA_DISCONNECTED', input);
  if (input?.p1Fresh !== true) return blocked('P1_STALE', input);
  if (input?.evActualFresh !== true) return blocked('EV_ACTUAL_POWER_STALE', input);

  const p1W = finiteNumber(input.p1W);
  const evActualW = finiteNumber(input.evActualW);
  if (p1W === null) return blocked('P1_INVALID', input);
  if (evActualW === null || evActualW < 0) return blocked('EV_ACTUAL_POWER_INVALID', input);

  const minA = Math.round(finiteNumber(envelope.min_A) ?? 0);
  const maxA = Math.round(finiteNumber(envelope.max_A) ?? 0);
  if (minA !== MIN_A || maxA < minA || maxA > MAX_A) {
    return blocked('ENVELOPE_BOUNDS_INVALID', input);
  }
  if (envelope.deadlineActive === true) {
    const deadlineMaxA = Math.round(finiteNumber(envelope.deadlineMax_A) ?? 0);
    if (deadlineMaxA < minA || maxA > deadlineMaxA) {
      return blocked('DEADLINE_CAP_INVALID', input);
    }
  }
  if (envelope.deadlineRequiredSlot === true) return blocked('DEADLINE_REQUIRED_SLOT', input);

  // P1 sign convention: negative = export, positive = import.
  // Add EV actual power back so the controller does not see its own charging
  // load as disappearance of PV surplus. WW is intentionally NOT added back.
  const counterfactualSurplusW = Math.max(0, -p1W + evActualW);

  // Wrapper may supply a 120 s smoothed counterfactual surplus. Until that
  // signal exists, raw counterfactual surplus is used for SHADOW calculation.
  const smoothedInput = finiteNumber(input.smoothedSurplusW);
  const smoothedSurplusW = smoothedInput === null
    ? counterfactualSurplusW
    : Math.max(0, smoothedInput);

  const rawCandidateA = Math.floor(smoothedSurplusW / EV_W_PER_A);
  const candidateA = rawCandidateA < minA ? 0 : clamp(rawCandidateA, minA, maxA);
  const candidateW = candidateA * EV_W_PER_A;

  return {
    schema: SCHEMA,
    generatedAt: new Date().toISOString(),
    mode: 'SHADOW',
    quality: 'GOOD',
    reason: candidateA === 0 ? 'SURPLUS_BELOW_START6' : 'BOUNDED_PV_OPPORTUNITY',
    piSlotTargetA: Math.max(0, Math.round(finiteNumber(input.piSlotTargetA) ?? 0)),
    piSlotTargetW: Math.max(0, Math.round(finiteNumber(input.piSlotTargetW) ?? 0)),
    envelopeAllowed: true,
    envelopeMinA: minA,
    envelopeMaxA: maxA,
    p1W: Math.round(p1W),
    evActualW: Math.round(evActualW),
    counterfactualSurplusW: Math.round(counterfactualSurplusW),
    smoothedSurplusW: Math.round(smoothedSurplusW),
    candidateA,
    candidateW,
    wwReservedW: Math.max(0, Math.round(finiteNumber(envelope.wwReserved_W) ?? 0)),
    selfLoadCorrection: 'P1_NET_EXPORT_PLUS_EV_ACTUAL_W',
    wwSelfLoadCorrection: false,
    deviceWrites: false,
    logicWrites: false,
  };
}

// Minimal deterministic smoke cases for `node` on the Pi.
if (import.meta.url === `file://${process.argv[1]}`) {
  const envelope = {
    schema: ENVELOPE_SCHEMA,
    shadowOnly: true,
    productionConsumerAllowed: false,
    allowed: true,
    mode: 'PV_OPPORTUNITY',
    min_A: 6,
    max_A: 8,
    wwReserved_W: 1900,
    deadlineActive: true,
    deadlineMax_A: 8,
    deadlineRequiredSlot: false,
  };
  const base = {
    plannerAuthority: 'PI',
    controlStatus: 'READY',
    contractMode: 'FIXED',
    contractId: 'ENGIE_3Y_2026_2029',
    teslaConnected: true,
    p1Fresh: true,
    evActualFresh: true,
    piSlotTargetA: 0,
    piSlotTargetW: 0,
    envelope,
  };

  const cases = [
    ['export-4487-stopped', { ...base, p1W: -4487, evActualW: 0 }, 6],
    ['export-1500-running-6A', { ...base, p1W: -1500, evActualW: 4140 }, 8],
    ['below-start6', { ...base, p1W: -4000, evActualW: 0 }, 0],
    ['cap-at-8A', { ...base, p1W: -9000, evActualW: 0 }, 8],
  ];

  let failed = 0;
  for (const [name, args, expectedA] of cases) {
    const out = evaluateEvRealtimeFlexShadow(args);
    const pass = out.candidateA === expectedA && out.deviceWrites === false && out.logicWrites === false;
    console.log(`${pass ? 'PASS' : 'FAIL'} ${name}: candidateA=${out.candidateA} expected=${expectedA}`);
    if (!pass) failed += 1;
  }
  if (failed) process.exitCode = 1;
}
