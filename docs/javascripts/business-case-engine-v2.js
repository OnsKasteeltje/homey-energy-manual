/**
 * EMS Business Case Engine v2 — read-only / SHADOW
 *
 * Historical counterfactual replay for battery/EMS economics.
 * No Homey/device/network writes. The engine consumes normalized time-series
 * samples and explicit scenario assumptions, and returns auditable metrics.
 */

export const BC_ENGINE_SCHEMA = "EMS_BUSINESS_CASE_ENGINE_V2";
export const BC_STRATEGIES = Object.freeze({
  BASELINE: "BASELINE_NO_BATTERY",
  SELF_CONSUMPTION: "BATTERY_SELF_CONSUMPTION",
  EMS_REPLAY: "BATTERY_EMS_REPLAY",
});

const EPS = 1e-9;
const finite = v => typeof v === "number" && Number.isFinite(v);
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const r = (v, n = 6) => Number(Number(v).toFixed(n));

function validateScenario(s) {
  const required = [
    "capacityKWh", "minSocPct", "maxSocPct", "initialSocPct",
    "maxChargeKW", "maxDischargeKW", "chargeEfficiency", "dischargeEfficiency",
    "standbyW", "capexEuro", "lifetimeYears", "discountRate",
    "degradationEuroPerThroughputKWh"
  ];
  for (const k of required) if (!finite(s?.[k])) throw new Error(`INVALID_SCENARIO_${k}`);
  if (s.capacityKWh <= 0 || s.maxChargeKW < 0 || s.maxDischargeKW < 0) throw new Error("INVALID_SCENARIO_POWER_OR_CAPACITY");
  if (!(s.minSocPct >= 0 && s.minSocPct < s.maxSocPct && s.maxSocPct <= 100)) throw new Error("INVALID_SOC_BAND");
  if (!(s.initialSocPct >= s.minSocPct && s.initialSocPct <= s.maxSocPct)) throw new Error("INVALID_INITIAL_SOC");
  if (!(s.chargeEfficiency > 0 && s.chargeEfficiency <= 1 && s.dischargeEfficiency > 0 && s.dischargeEfficiency <= 1)) throw new Error("INVALID_EFFICIENCY");
  if (s.lifetimeYears <= 0 || s.discountRate <= -1) throw new Error("INVALID_FINANCIAL_ASSUMPTIONS");
}

function normalizeSamples(samples, defaultIntervalMinutes = 5) {
  if (!Array.isArray(samples)) throw new Error("SAMPLES_MUST_BE_ARRAY");
  let valid = 0, invalid = 0;
  const normalized = [];
  for (let i = 0; i < samples.length; i++) {
    const x = samples[i] || {};
    const intervalMinutes = finite(x.intervalMinutes) && x.intervalMinutes > 0 ? x.intervalMinutes : defaultIntervalMinutes;
    const gridW = finite(x.gridW) ? x.gridW : finite(x.p1W) ? x.p1W : null;
    const importPrice = finite(x.importPriceEuroPerKWh) ? x.importPriceEuroPerKWh : null;
    const exportPrice = finite(x.exportPriceEuroPerKWh) ? x.exportPriceEuroPerKWh : null;
    const measurementValid = x.measurementValid !== false && x.p1Valid !== false && finite(gridW);
    const tariffValid = finite(importPrice) && finite(exportPrice);
    if (!measurementValid || !tariffValid) { invalid++; continue; }
    valid++;
    normalized.push({
      ts: x.ts ?? null,
      intervalHours: intervalMinutes / 60,
      gridW,
      importPrice,
      exportPrice,
      emsBatteryTargetW: finite(x.emsBatteryTargetW) ? x.emsBatteryTargetW : null,
      forecastQuality: x.forecastQuality ?? null,
    });
  }
  return { normalized, valid, invalid, total: samples.length };
}

function baselineIntervalCost(gridW, h, importPrice, exportPrice) {
  const importKWh = Math.max(0, gridW) / 1000 * h;
  const exportKWh = Math.max(0, -gridW) / 1000 * h;
  return { importKWh, exportKWh, costEuro: importKWh * importPrice - exportKWh * exportPrice };
}

function chooseAcBatteryPowerW(strategy, sample, limits) {
  // Sign convention at AC bus: +W = battery charging (extra load), -W = discharging (supply).
  if (strategy === BC_STRATEGIES.BASELINE) return 0;
  if (strategy === BC_STRATEGIES.SELF_CONSUMPTION) {
    if (sample.gridW < 0) return Math.min(-sample.gridW, limits.maxChargeW);
    if (sample.gridW > 0) return -Math.min(sample.gridW, limits.maxDischargeW);
    return 0;
  }
  if (strategy === BC_STRATEGIES.EMS_REPLAY) {
    return finite(sample.emsBatteryTargetW) ? clamp(sample.emsBatteryTargetW, -limits.maxDischargeW, limits.maxChargeW) : 0;
  }
  throw new Error(`UNSUPPORTED_STRATEGY_${strategy}`);
}

export function replayBusinessCase({ samples, scenario, strategy = BC_STRATEGIES.SELF_CONSUMPTION, defaultIntervalMinutes = 5 }) {
  validateScenario(scenario);
  const q = normalizeSamples(samples, defaultIntervalMinutes);
  const minEnergy = scenario.capacityKWh * scenario.minSocPct / 100;
  const maxEnergy = scenario.capacityKWh * scenario.maxSocPct / 100;
  let energy = scenario.capacityKWh * scenario.initialSocPct / 100;
  const limits = { maxChargeW: scenario.maxChargeKW * 1000, maxDischargeW: scenario.maxDischargeKW * 1000 };

  let baselineCost = 0, scenarioCost = 0, importKWh = 0, exportKWh = 0;
  let baselineImportKWh = 0, baselineExportKWh = 0, chargeAcKWh = 0, dischargeAcKWh = 0;
  let throughputKWh = 0, conversionLossKWh = 0, standbyKWh = 0, curtailedChargeKWh = 0, curtailedDischargeKWh = 0;
  const trace = [];

  for (const s of q.normalized) {
    const b = baselineIntervalCost(s.gridW, s.intervalHours, s.importPrice, s.exportPrice);
    baselineCost += b.costEuro; baselineImportKWh += b.importKWh; baselineExportKWh += b.exportKWh;

    const standbyAcKWh = scenario.standbyW / 1000 * s.intervalHours;
    standbyKWh += standbyAcKWh;
    let desiredW = chooseAcBatteryPowerW(strategy, s, limits);
    let actualW = 0;

    if (desiredW > EPS) {
      const desiredAcKWh = desiredW / 1000 * s.intervalHours;
      const maxAcBySoc = Math.max(0, maxEnergy - energy) / scenario.chargeEfficiency;
      const actualAcKWh = Math.min(desiredAcKWh, maxAcBySoc);
      actualW = actualAcKWh / s.intervalHours * 1000;
      energy += actualAcKWh * scenario.chargeEfficiency;
      chargeAcKWh += actualAcKWh;
      throughputKWh += actualAcKWh * scenario.chargeEfficiency;
      conversionLossKWh += actualAcKWh * (1 - scenario.chargeEfficiency);
      curtailedChargeKWh += desiredAcKWh - actualAcKWh;
    } else if (desiredW < -EPS) {
      const desiredAcKWh = -desiredW / 1000 * s.intervalHours;
      const maxAcBySoc = Math.max(0, energy - minEnergy) * scenario.dischargeEfficiency;
      const actualAcKWh = Math.min(desiredAcKWh, maxAcBySoc);
      actualW = -actualAcKWh / s.intervalHours * 1000;
      const dcRemoved = actualAcKWh / scenario.dischargeEfficiency;
      energy -= dcRemoved;
      dischargeAcKWh += actualAcKWh;
      throughputKWh += dcRemoved;
      conversionLossKWh += dcRemoved - actualAcKWh;
      curtailedDischargeKWh += desiredAcKWh - actualAcKWh;
    }

    // Standby is an AC-side load and therefore remains visible even when idle.
    const scenarioGridW = s.gridW + actualW + scenario.standbyW;
    const e = baselineIntervalCost(scenarioGridW, s.intervalHours, s.importPrice, s.exportPrice);
    scenarioCost += e.costEuro; importKWh += e.importKWh; exportKWh += e.exportKWh;

    trace.push({ ts: s.ts, gridW: s.gridW, batteryAcW: r(actualW, 3), scenarioGridW: r(scenarioGridW, 3), socPct: r(energy / scenario.capacityKWh * 100, 3) });
  }

  const degradationEuro = throughputKWh * scenario.degradationEuroPerThroughputKWh;
  const grossOperationalSavingEuro = baselineCost - scenarioCost;
  const netOperationalSavingEuro = grossOperationalSavingEuro - degradationEuro;
  const efc = throughputKWh / (2 * scenario.capacityKWh);
  const selfConsumptionDeltaKWh = baselineExportKWh - exportKWh;
  const avoidedImportKWh = baselineImportKWh - importKWh;
  const evidenceCoverage = q.total ? q.valid / q.total : 0;

  return {
    schema: BC_ENGINE_SCHEMA,
    readOnly: true,
    controlImpact: false,
    strategy,
    scenarioId: scenario.id ?? null,
    evidence: { totalSamples: q.total, validSamples: q.valid, invalidSamples: q.invalid, coverage: r(evidenceCoverage, 4), quality: evidenceCoverage >= 0.98 ? "HIGH" : evidenceCoverage >= 0.90 ? "MEDIUM" : "LOW" },
    energy: {
      baselineImportKWh: r(baselineImportKWh), baselineExportKWh: r(baselineExportKWh), importKWh: r(importKWh), exportKWh: r(exportKWh),
      chargeAcKWh: r(chargeAcKWh), dischargeAcKWh: r(dischargeAcKWh), throughputKWh: r(throughputKWh), equivalentFullCycles: r(efc, 4),
      conversionLossKWh: r(conversionLossKWh), standbyKWh: r(standbyKWh), curtailedChargeKWh: r(curtailedChargeKWh), curtailedDischargeKWh: r(curtailedDischargeKWh),
      selfConsumptionDeltaKWh: r(selfConsumptionDeltaKWh), avoidedImportKWh: r(avoidedImportKWh), terminalSocPct: r(energy / scenario.capacityKWh * 100, 3)
    },
    economics: {
      baselineEnergyCostEuro: r(baselineCost, 4), scenarioEnergyCostEuro: r(scenarioCost, 4), grossOperationalSavingEuro: r(grossOperationalSavingEuro, 4),
      degradationEuro: r(degradationEuro, 4), netOperationalSavingEuro: r(netOperationalSavingEuro, 4)
    },
    trace
  };
}

export function annualizeReplay(result, observedDays) {
  if (!finite(observedDays) || observedDays <= 0) throw new Error("INVALID_OBSERVED_DAYS");
  const f = 365.2425 / observedDays;
  return {
    annualizationFactor: r(f, 6),
    annualNetOperationalSavingEuro: r(result.economics.netOperationalSavingEuro * f, 2),
    annualGrossOperationalSavingEuro: r(result.economics.grossOperationalSavingEuro * f, 2),
    annualThroughputKWh: r(result.energy.throughputKWh * f, 2),
    annualEquivalentFullCycles: r(result.energy.equivalentFullCycles * f, 3),
    warning: observedDays < 90 ? "SHORT_EVIDENCE_WINDOW" : null,
  };
}

export function financialCase({ capexEuro, annualNetSavingEuro, lifetimeYears, discountRate, residualValueEuro = 0, annualMaintenanceEuro = 0 }) {
  for (const [k, v] of Object.entries({ capexEuro, annualNetSavingEuro, lifetimeYears, discountRate, residualValueEuro, annualMaintenanceEuro })) if (!finite(v)) throw new Error(`INVALID_FINANCIAL_${k}`);
  let npv = -capexEuro;
  const annualCash = annualNetSavingEuro - annualMaintenanceEuro;
  for (let y = 1; y <= lifetimeYears; y++) npv += annualCash / ((1 + discountRate) ** y);
  npv += residualValueEuro / ((1 + discountRate) ** lifetimeYears);
  const simplePaybackYears = annualCash > 0 ? capexEuro / annualCash : null;
  return { npvEuro: r(npv, 2), simplePaybackYears: simplePaybackYears == null ? null : r(simplePaybackYears, 2), annualCashEuro: r(annualCash, 2) };
}

export function compareBusinessCases({ baseline, ems, oracle }) {
  const base = baseline?.economics?.netOperationalSavingEuro ?? 0;
  const e = ems?.economics?.netOperationalSavingEuro;
  const o = oracle?.economics?.netOperationalSavingEuro;
  const denom = finite(o) ? o - base : NaN;
  const capture = finite(e) && finite(denom) && Math.abs(denom) > EPS ? (e - base) / denom : null;
  return {
    emsCaptureRatio: capture == null ? null : r(capture, 4),
    emsGapToOracleEuro: finite(e) && finite(o) ? r(o - e, 4) : null,
    note: "Oracle input must come from an independently validated perfect-information optimizer; this replay kernel does not label a heuristic as oracle."
  };
}
