// EV Phase + Current Controller v0.1 — reference model
// Pure Homey-side realtime opportunity controller.
// No Homey API calls, no Logic writes, no device writes.
//
// Separation of concerns:
//   1. slow physical mode selector: OFF | 1P | 3P
//   2. faster phase-aware current regulator: 6..16 A within 1P or 3P
//
// Deadline charging is explicitly outside this controller.

export const SCHEMA = 'EM2_EV_PHASE_CURRENT_CONTROLLER_V0.1';

export const CONFIG = Object.freeze({
  voltageV: 230,
  minA: 6,
  maxA: 16,

  start1pW: 1500,
  stop1pW: 1100,
  enter3pW: 4400,
  leave3pW: 3600,

  rollingWindowMs: 120000,
  rollingMinCoverageMs: 90000,

  // Slow/re-entry dwell. Sustained downward transitions are allowed after the
  // rolling confirmation even when this dwell has not elapsed; otherwise a
  // cloud dip immediately after an upshift could trap 3P at its 6 A minimum
  // and intentionally import for several minutes.
  upwardModeDwellMs: 300000,

  upscaleConfirm1pMs: 20000,
  upscaleConfirm3pMs: 30000,
  // Prefer using a little grid import over leaving several hundred watts of
  // PV export unused. This threshold applies only to +1 A decisions; the
  // existing importDeadbandW remains the fast-down safety boundary.
  upscaleImportTargetW: 200,
  importDeadbandW: 250,

  maxRollingSamples: 240,
});

const finite = value => Number.isFinite(Number(value));
const num = value => finite(value) ? Number(value) : null;
const clamp = (n, low, high) => Math.max(low, Math.min(high, n));

function normalizeMode(value) {
  return ['OFF', '1P', '3P'].includes(String(value)) ? String(value) : 'OFF';
}

function sampleMs(value) {
  if (finite(value)) return Number(value);
  const parsed = Date.parse(String(value ?? ''));
  return Number.isFinite(parsed) ? parsed : null;
}

export function wattsPerAmp(mode, cfg = CONFIG) {
  if (mode === '1P') return cfg.voltageV;
  if (mode === '3P') return 3 * cfg.voltageV;
  return 0;
}

export function reconstructAvailableTotalW({p1W, evActualW}) {
  const p1 = num(p1W);
  const ev = num(evActualW);
  if (p1 === null || ev === null || ev < 0) return null;
  // Homey P1 convention: import positive, export negative.
  return Math.max(0, -p1 + ev);
}

function normalizeSamples(samples, nowMs, cfg) {
  const out = [];
  for (const raw of Array.isArray(samples) ? samples : []) {
    const at = sampleMs(raw?.atMs ?? raw?.at);
    const w = num(raw?.w ?? raw?.availableTotalW);
    if (at === null || w === null || w < 0 || at >= nowMs) continue;
    out.push({atMs: at, w});
  }
  out.sort((a, b) => a.atMs - b.atMs);

  // De-duplicate timestamps; newest value wins.
  const dedup = [];
  for (const s of out) {
    if (dedup.length && dedup[dedup.length - 1].atMs === s.atMs) {
      dedup[dedup.length - 1] = s;
    } else {
      dedup.push(s);
    }
  }

  // Keep at most one anchor sample before the rolling window and all samples
  // inside it. The anchor lets us time-weight from the exact window boundary.
  const windowStart = nowMs - cfg.rollingWindowMs;
  let anchor = null;
  const inside = [];
  for (const s of dedup) {
    if (s.atMs < windowStart) anchor = s;
    else inside.push(s);
  }
  const kept = anchor ? [anchor, ...inside] : inside;
  return kept.slice(-cfg.maxRollingSamples);
}

export function appendAvailableSample(previousSamples, nowMs, availableTotalW, cfg = CONFIG) {
  const samples = normalizeSamples(previousSamples, nowMs, cfg);
  const current = {atMs: nowMs, w: Math.max(0, Number(availableTotalW))};
  if (samples.length && samples[samples.length - 1].atMs === nowMs) {
    samples[samples.length - 1] = current;
  } else {
    samples.push(current);
  }
  return samples.slice(-cfg.maxRollingSamples);
}

export function rollingAvailable(samples, nowMs, cfg = CONFIG) {
  const clean = normalizeSamples(samples, nowMs + 1, cfg)
    .filter(s => s.atMs <= nowMs);

  if (!clean.length) {
    return {avgW: null, coverageMs: 0, ready: false, sampleCount: 0};
  }

  const windowStart = nowMs - cfg.rollingWindowMs;
  let weighted = 0;
  let covered = 0;

  for (let i = 0; i < clean.length; i += 1) {
    const s = clean[i];
    const nextAt = i + 1 < clean.length ? clean[i + 1].atMs : nowMs;
    const from = Math.max(windowStart, s.atMs);
    const to = Math.min(nowMs, nextAt);
    if (to <= from) continue;
    const dt = to - from;
    weighted += s.w * dt;
    covered += dt;
  }

  const avgW = covered > 0 ? weighted / covered : clean[clean.length - 1].w;
  const distinctInside = clean.filter(s => s.atMs >= windowStart && s.atMs <= nowMs).length;
  const ready =
    covered >= cfg.rollingMinCoverageMs &&
    distinctInside >= 1 &&
    clean.length >= 2;

  return {
    avgW,
    coverageMs: covered,
    ready,
    sampleCount: clean.length,
  };
}

function baseState(previous, nowMs, cfg) {
  const mode = normalizeMode(previous?.mode);
  const modeSinceMs = sampleMs(previous?.modeSinceMs ?? previous?.modeSinceAt);
  const requestedRaw = Math.floor(num(previous?.requestedA) ?? 0);
  const requestedA = mode === 'OFF'
    ? 0
    : clamp(requestedRaw, 0, cfg.maxA);
  const upscaleSinceMs = sampleMs(previous?.upscaleSinceMs ?? previous?.upscaleSinceAt);

  return {
    mode,
    modeSinceMs,
    requestedA,
    upscaleSinceMs,
    availableSamples: Array.isArray(previous?.availableSamples)
      ? previous.availableSamples
      : [],
  };
}

function blocked(reason, previous, nowMs, cfg, extra = {}) {
  const state = baseState(previous, nowMs, cfg);
  return {
    schema: SCHEMA,
    generatedAt: new Date(nowMs).toISOString(),
    applicable: true,
    quality: 'BLOCKED',
    reason,
    mode: 'OFF',
    requestedA: 0,
    requestedW: 0,
    phaseChanged: state.mode !== 'OFF',
    currentChanged: state.requestedA !== 0,
    requiresPhysicalPhaseTransition: state.mode !== 'OFF',
    availableTotalW: extra.availableTotalW ?? null,
    rollingAvailableW: extra.rollingAvailableW ?? null,
    rollingCoverageMs: extra.rollingCoverageMs ?? 0,
    rollingReady: extra.rollingReady ?? false,
    syntheticP1W: null,
    nextState: {
      mode: 'OFF',
      modeSinceMs: state.mode === 'OFF' ? state.modeSinceMs : nowMs,
      requestedA: 0,
      upscaleSinceMs: null,
      availableSamples: extra.availableSamples ?? state.availableSamples,
    },
    deviceWrites: false,
    logicWrites: false,
    shadow: true,
  };
}

function bypassDeadline(previous, nowMs, cfg) {
  const state = baseState(previous, nowMs, cfg);
  return {
    schema: SCHEMA,
    generatedAt: new Date(nowMs).toISOString(),
    applicable: false,
    quality: 'BYPASS',
    reason: 'DEADLINE_PATH_OWNED_ELSEWHERE',
    mode: state.mode,
    requestedA: state.requestedA,
    requestedW: state.requestedA * wattsPerAmp(state.mode, cfg),
    phaseChanged: false,
    currentChanged: false,
    requiresPhysicalPhaseTransition: false,
    nextState: state,
    deviceWrites: false,
    logicWrites: false,
    shadow: true,
  };
}

function canSustainMin(mode, availableTotalW, cfg) {
  const minTarget = cfg.minA * wattsPerAmp(mode, cfg);
  return availableTotalW + cfg.importDeadbandW >= minTarget;
}

function initialA(mode, availableTotalW, maxA, cfg) {
  const wpa = wattsPerAmp(mode, cfg);
  if (!wpa) return 0;
  const feasible = Math.floor((availableTotalW + cfg.importDeadbandW) / wpa);
  return clamp(feasible, cfg.minA, maxA);
}

function selectMode({
  previousMode,
  rollingW,
  rollingReady,
  availableTotalW,
  maxA,
  modeSinceMs,
  nowMs,
  cfg,
}) {
  const upwardDwellOK =
    !finite(modeSinceMs) ||
    nowMs - Number(modeSinceMs) >= cfg.upwardModeDwellMs;

  let mode = previousMode;
  let reason = 'HOLD_MODE';

  if (!rollingReady) {
    return {mode, reason: 'ROLLING_NOT_READY', upwardDwellOK};
  }

  if (previousMode === '3P') {
    // Downward transitions use the sustained rolling signal but are not delayed
    // by the 300 s upward/re-entry dwell.
    if (rollingW < cfg.start1pW) {
      mode = 'OFF';
      reason = '3P_TO_OFF_ROLLING_LOW';
    } else if (rollingW < cfg.leave3pW) {
      mode = '1P';
      reason = '3P_TO_1P_ROLLING_LOW';
    }
  } else if (previousMode === '1P') {
    if (rollingW < cfg.stop1pW) {
      mode = 'OFF';
      reason = '1P_TO_OFF_ROLLING_LOW';
    } else if (
      rollingW >= cfg.enter3pW &&
      upwardDwellOK &&
      canSustainMin('3P', availableTotalW, cfg)
    ) {
      mode = '3P';
      reason = '1P_TO_3P_ROLLING_HIGH';
    }
  } else if (upwardDwellOK) {
    if (
      rollingW >= cfg.enter3pW &&
      canSustainMin('3P', availableTotalW, cfg)
    ) {
      mode = '3P';
      reason = 'OFF_TO_3P_ROLLING_HIGH';
    } else if (
      rollingW >= cfg.start1pW &&
      canSustainMin('1P', availableTotalW, cfg)
    ) {
      mode = '1P';
      reason = 'OFF_TO_1P_ROLLING_HIGH';
    }
  }

  // Envelope may shrink below a usable active range.
  if (maxA < cfg.minA) {
    mode = 'OFF';
    reason = 'MAX_A_BELOW_MIN';
  }

  return {mode, reason, upwardDwellOK};
}

function regulateCurrent({
  mode,
  previousMode,
  previousA,
  previousUpscaleSinceMs,
  availableTotalW,
  maxA,
  nowMs,
  cfg,
}) {
  if (mode === 'OFF') {
    return {requestedA: 0, upscaleSinceMs: null, reason: 'MODE_OFF'};
  }

  const wpa = wattsPerAmp(mode, cfg);
  const modeChanged = mode !== previousMode;

  if (modeChanged || previousA < cfg.minA) {
    return {
      requestedA: initialA(mode, availableTotalW, maxA, cfg),
      upscaleSinceMs: null,
      reason: modeChanged ? 'MODE_ENTRY_INITIAL_A' : 'INITIAL_A',
    };
  }

  let requestedA = clamp(previousA, cfg.minA, maxA);
  if (requestedA !== previousA) {
    return {
      requestedA,
      upscaleSinceMs: null,
      reason: 'ENVELOPE_CAP_DOWN',
    };
  }

  const targetW = requestedA * wpa;
  const syntheticP1W = targetW - availableTotalW;

  if (syntheticP1W > cfg.importDeadbandW) {
    const excessImportW = syntheticP1W - cfg.importDeadbandW;
    const reductionA = Math.max(1, Math.ceil(excessImportW / wpa));
    requestedA = Math.max(cfg.minA, requestedA - reductionA);
    return {
      requestedA,
      upscaleSinceMs: null,
      reason: 'FAST_IMPORT_DOWN',
    };
  }

  if (syntheticP1W + wpa <= cfg.upscaleImportTargetW && requestedA < maxA) {
    const since = finite(previousUpscaleSinceMs)
      ? Number(previousUpscaleSinceMs)
      : nowMs;

    const confirmMs = mode === '1P' ? cfg.upscaleConfirm1pMs : cfg.upscaleConfirm3pMs;

    if (nowMs - since >= confirmMs) {
      return {
        requestedA: requestedA + 1,
        upscaleSinceMs: nowMs,
        reason: 'SLOW_PLUS_1A',
      };
    }

    return {
      requestedA,
      upscaleSinceMs: since,
      reason: 'UPSCALE_CONFIRMING',
    };
  }

  return {
    requestedA,
    upscaleSinceMs: null,
    reason: 'HOLD_A',
  };
}

export function evaluateEvPhaseCurrentCandidate(
  input,
  previous = {},
  nowMs = Date.now(),
  cfg = CONFIG,
) {
  if (input?.deadlineForceActive === true) {
    return bypassDeadline(previous, nowMs, cfg);
  }

  const state = baseState(previous, nowMs, cfg);

  if (input?.opportunityAllowed !== true) {
    return blocked('OPPORTUNITY_BLOCKED', previous, nowMs, cfg);
  }
  if (input?.p1Fresh !== true) {
    return blocked('P1_STALE', previous, nowMs, cfg);
  }
  if (input?.evActualFresh !== true) {
    return blocked('EV_ACTUAL_STALE', previous, nowMs, cfg);
  }

  const availableTotalW = reconstructAvailableTotalW(input);
  if (availableTotalW === null) {
    return blocked('INVALID_POWER_INPUT', previous, nowMs, cfg);
  }

  const maxA = clamp(
    Math.floor(num(input?.maxA) ?? cfg.maxA),
    0,
    cfg.maxA,
  );

  const availableSamples = appendAvailableSample(
    state.availableSamples,
    nowMs,
    availableTotalW,
    cfg,
  );
  const rolling = rollingAvailable(availableSamples, nowMs, cfg);

  if (maxA < cfg.minA) {
    return blocked('MAX_A_BELOW_MIN', previous, nowMs, cfg, {
      availableTotalW,
      rollingAvailableW: rolling.avgW,
      rollingCoverageMs: rolling.coverageMs,
      rollingReady: rolling.ready,
      availableSamples,
    });
  }

  const phase = selectMode({
    previousMode: state.mode,
    rollingW: rolling.avgW,
    rollingReady: rolling.ready,
    availableTotalW,
    maxA,
    modeSinceMs: state.modeSinceMs,
    nowMs,
    cfg,
  });

  const phaseChanged = phase.mode !== state.mode;

  const current = regulateCurrent({
    mode: phase.mode,
    previousMode: state.mode,
    previousA: state.requestedA,
    previousUpscaleSinceMs: state.upscaleSinceMs,
    availableTotalW,
    maxA,
    nowMs,
    cfg,
  });

  const requestedW = current.requestedA * wattsPerAmp(phase.mode, cfg);
  const syntheticP1W = requestedW - availableTotalW;
  const currentChanged = current.requestedA !== state.requestedA;

  const nextState = {
    mode: phase.mode,
    modeSinceMs: phaseChanged ? nowMs : state.modeSinceMs,
    requestedA: current.requestedA,
    upscaleSinceMs: current.upscaleSinceMs,
    availableSamples,
  };

  return {
    schema: SCHEMA,
    generatedAt: new Date(nowMs).toISOString(),
    applicable: true,
    quality: 'GOOD',
    reason: phase.reason,
    mode: phase.mode,
    requestedA: current.requestedA,
    requestedW,
    phaseChanged,
    currentChanged,
    requiresPhysicalPhaseTransition: phaseChanged,
    phaseReason: phase.reason,
    currentReason: current.reason,
    upwardModeDwellOK: phase.upwardDwellOK,
    availableTotalW: Math.round(availableTotalW),
    rollingAvailableW: rolling.avgW === null ? null : Math.round(rolling.avgW),
    rollingCoverageMs: Math.round(rolling.coverageMs),
    rollingReady: rolling.ready,
    rollingSampleCount: rolling.sampleCount,
    syntheticP1W: Math.round(syntheticP1W),
    maxA,
    mappingWPerA: wattsPerAmp(phase.mode, cfg),
    selfLoadCorrection: 'P1_NET_PLUS_EV_ACTUAL',
    currentOnlyChange: currentChanged && !phaseChanged,
    nextState,
    deviceWrites: false,
    logicWrites: false,
    shadow: true,
  };
}
