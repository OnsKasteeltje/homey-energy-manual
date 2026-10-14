// Read-only L1 dishwasher diagnostic, adapted from historical fingerprint v1.0.2.
// Never assigns appliance wattage, writes to Homey or changes the EMS energy budget.
// Each unique canonical Pi sample counts once, regardless of 15-second UI polling.
export const FINGERPRINT_VERSION = "L1_DIAGNOSTIC_V1";
const HISTORY_MS = 3 * 60 * 60 * 1000;
const CONTEXT_MS = 45 * 60 * 1000;
const MAX_SAMPLE_AGE_MS = 10 * 60 * 1000;
const MAX_SAMPLES = 90;

const validNumber = (v) => typeof v === "number" && Number.isFinite(v);
const phase = (s, name) => s?.gridPhases?.find((p) => p.name === name)?.power;
const solarEdge = (s) => s?.pvSources?.find((p) => p.key === "solarEdge");
const heatBand = (w) => w >= 1750 && w <= 2600;
const edgeBand = (w) => w >= 1500 && w < 1750;
const pumpBand = (w) => w >= 220 && w <= 900;

export function diagnoseDishwasher(s, priorHistory = [], nowMs = Date.now()) {
  const base = {
    version: FINGERPRINT_VERSION, phase: "L1", source: "P1_PHASE_FINGERPRINT",
    powerW: null, // No per-appliance power attribution.
    status: "UNAVAILABLE", confidence: null, reason: "NO_VALID_L1_SAMPLE"
  };
  const history = (Array.isArray(priorHistory) ? priorHistory : [])
    .filter((p) => validNumber(p?.ts) && nowMs - p.ts >= 0 &&
      nowMs - p.ts <= HISTORY_MS && validNumber(p?.signalW))
    .slice(-MAX_SAMPLES);

  const ts = Date.parse(s?.generatedAt || "");
  const pv = solarEdge(s);
  const netL1 = phase(s, "L1");
  if (!s?.p1Valid || !validNumber(netL1) || !pv?.fresh ||
      !validNumber(pv.power) || !Number.isFinite(ts) ||
      ts > nowMs + 60_000 || nowMs - ts > MAX_SAMPLE_AGE_MS) {
    return { ...base, history, reason: !s?.p1Valid ? "P1_STALE" :
      !pv?.fresh || !validNumber(pv?.power) ? "SOLAREDGE_STALE" :
      "SOURCE_TIMESTAMP_INVALID" };
  }

  // L1 gross load: P1 signed net phase + *fresh* SolarEdge production on L1.
  const signalW = Math.max(0, netL1 + Math.max(0, pv.power));
  const teslaInterference = s.teslaCharging === true ||
    (validNumber(s.tesla) && s.tesla > 300);

  // Washer has validated L2 phase context; Quooker L3; neither masks L1.
  // Dryer phase is not validated: retain diagnostic but cap confidence.
  const dryerPhaseUnknown = s.loads?.dryer?.active === true;
  if (!history.some((p) => p.ts === ts)) {
    history.push({ts, signalW, excluded: teslaInterference});
  }
  const bounded = history.slice(-MAX_SAMPLES);
  if (teslaInterference) return {
    ...base, history: bounded, signalW, status: "SUSPENDED",
    reason: "TESLA_MULTIPHASE_INTERFERENCE"
  };

  const recent = bounded.filter((p) => !p.excluded && ts - p.ts >= 0 &&
    ts - p.ts <= CONTEXT_MS);
  const heat = recent.filter((p) => heatBand(p.signalW));
  const edge = recent.filter((p) => edgeBand(p.signalW));
  const pump = recent.filter((p) => pumpBand(p.signalW));
  const strong = heat.concat(edge).sort((a, b) => a.ts - b.ts);
  const lastStrong = strong.at(-1);
  const recentStrong = lastStrong && ts - lastStrong.ts <= CONTEXT_MS;

  const contextualSequence = strong.length >= 1 && pump.some((p) =>
    p.ts > strong[0].ts && p.ts - strong[0].ts <= CONTEXT_MS);
  const repeatedHeating = heat.length >= 2;
  const repeatedEdge = edge.length >= 2;
  const currentHeat = heatBand(signalW), currentEdge = edgeBand(signalW);
  const currentPump = pumpBand(signalW);
  let status = "NO_MATCH", confidence = 0, reason = "NO_SEQUENCE";

  if (recentStrong && contextualSequence &&
      (currentHeat || currentEdge || currentPump)) {
    status = "LIKELY";
    confidence = heat.length ? 0.78 : 0.70;
    reason = "HEAT_AND_PUMP_SEQUENCE";
  } else if ((currentHeat && repeatedHeating) ||
             (currentEdge && repeatedEdge)) {
    status = "CANDIDATE";
    confidence = currentHeat ? 0.63 : 0.50;
    reason = "REPEATED_L1_HEATING_NO_PUMP_YET";
  } else if (currentHeat || currentEdge) {
    // A kettle/oven can create one isolated ~2 kW L1 event.
    status = "UNCONFIRMED";
    reason = "ISOLATED_L1_HIGH_LOAD";
  }

  if (dryerPhaseUnknown && status === "LIKELY") {
    status = "CANDIDATE";
    confidence = Math.min(confidence, 0.60);
    reason = "DRYER_PHASE_UNVERIFIED";
  }
  return {
    ...base, history: bounded, signalW, status, confidence, reason,
    evidence: {heatSamples: heat.length, edgeSamples: edge.length,
      pumpSamples: pump.length, washerConfirmedL2: s.loads?.washer?.active === true,
      dryerActivePhaseUnknown: dryerPhaseUnknown}
  };
}
