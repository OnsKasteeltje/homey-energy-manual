'use strict';

/**
 * Planner v0.5 WW optimizer candidate.
 *
 * Pure function module: no Homey API access, no network access, no physical writes.
 * Intended for synthetic validation before any HomeyScript integration.
 */

const DEFAULT_BOILER_W = 1900;
const DEFAULT_SLOT_MINUTES = 15;

function finiteNumber(value) {
  return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
}

function round(value, digits = 3) {
  if (!finiteNumber(value)) return null;
  return Number(Number(value).toFixed(digits));
}

function normalizeSlot(slot, index, boilerW, slotMinutes = DEFAULT_SLOT_MINUTES) {
  const baseLoadW = finiteNumber(slot.baseLoadForecastW) ? Number(slot.baseLoadForecastW) : null;
  const pvForecastW = finiteNumber(slot.pvForecastW) ? Number(slot.pvForecastW) : null;
  const alreadyAllocatedFlexibleLoadW = Math.max(0, finiteNumber(slot.alreadyAllocatedFlexibleLoadW) ? Number(slot.alreadyAllocatedFlexibleLoadW) : 0);
  const availableSurplusW = baseLoadW === null || pvForecastW === null
    ? null
    : Math.max(0, pvForecastW - baseLoadW - alreadyAllocatedFlexibleLoadW);
  const pvCoverageW = availableSurplusW === null ? null : Math.min(boilerW, availableSurplusW);
  const marginalImportW = availableSurplusW === null ? null : Math.max(0, boilerW - availableSurplusW);
  const price = finiteNumber(slot.price_eur_kwh) ? Number(slot.price_eur_kwh) : null;

  return {
    ...slot,
    i: finiteNumber(slot.i) ? Number(slot.i) : index,
    availableSurplusW,
    flexAllocatedW: alreadyAllocatedFlexibleLoadW,
    targets: {
      evTargetW: Math.max(0, Number(slot.targets?.evTargetW) || 0),
      wwTargetW: 0,
      batteryTargetW: Number(slot.targets?.batteryTargetW) || 0,
    },
    phaseHeadroomW: {
      l1: slot.phaseHeadroomW?.l1 ?? null,
      l2: slot.phaseHeadroomW?.l2 ?? null,
      l3: slot.phaseHeadroomW?.l3 ?? null,
    },
    score: {
      pvCoverageW,
      marginalImportW,
      marginalImportKWh: marginalImportW === null ? null : round(marginalImportW * slotMinutes / 60000),
      pricePenalty: marginalImportW === null || price === null ? null : round(marginalImportW * slotMinutes / 60000 * price, 6),
      deadlinePenalty: 0,
      phasePenalty: 0,
    },
  };
}

function compareWwSlots(a, b, contract) {
  const aKnown = finiteNumber(a.score.marginalImportW);
  const bKnown = finiteNumber(b.score.marginalImportW);
  if (aKnown !== bKnown) return aKnown ? -1 : 1;

  // Primary objective: minimize marginal grid import caused by WW.
  if (aKnown && bKnown && a.score.marginalImportW !== b.score.marginalImportW) {
    return a.score.marginalImportW - b.score.marginalImportW;
  }

  // Equivalent import: prefer greatest direct PV coverage.
  if (aKnown && bKnown && a.score.pvCoverageW !== b.score.pvCoverageW) {
    return b.score.pvCoverageW - a.score.pvCoverageW;
  }

  // Price only breaks ties on imported energy; cheap grid never outranks better PV cover.
  if (String(contract || '').toUpperCase() === 'DYNAMIC') {
    const ap = finiteNumber(a.price_eur_kwh) ? Number(a.price_eur_kwh) : Number.POSITIVE_INFINITY;
    const bp = finiteNumber(b.price_eur_kwh) ? Number(b.price_eur_kwh) : Number.POSITIVE_INFINITY;
    if (ap !== bp) return ap - bp;
  }

  // Deterministic final tie-breaker. This intentionally does not impose contiguity.
  const at = Date.parse(String(a.start || ''));
  const bt = Date.parse(String(b.start || ''));
  if (Number.isFinite(at) && Number.isFinite(bt) && at !== bt) return at - bt;
  return a.i - b.i;
}

function optimizeWarmWater({
  slots,
  wwRemainingEnergyKWh,
  goalReachedToday = false,
  deadlineMs = null,
  contract = 'UNKNOWN',
  boilerW = DEFAULT_BOILER_W,
  slotMinutes = DEFAULT_SLOT_MINUTES,
}) {
  if (!Array.isArray(slots)) throw new TypeError('slots must be an array');
  if (!finiteNumber(boilerW) || Number(boilerW) <= 0) throw new TypeError('boilerW must be > 0');
  if (!finiteNumber(slotMinutes) || Number(slotMinutes) <= 0) throw new TypeError('slotMinutes must be > 0');

  const normalized = slots.map((slot, index) => normalizeSlot(slot, index, Number(boilerW), Number(slotMinutes)));
  const requestedEnergyKWh = goalReachedToday ? 0 : Math.max(0, Number(wwRemainingEnergyKWh) || 0);
  const slotEnergyKWh = Number(boilerW) * Number(slotMinutes) / 60000;
  const requiredSlots = requestedEnergyKWh > 0 ? Math.ceil(requestedEnergyKWh / slotEnergyKWh) : 0;

  const candidates = normalized.filter((slot) => {
    if (!Number.isFinite(Number(deadlineMs))) return true;
    const startMs = Date.parse(String(slot.start || ''));
    return Number.isFinite(startMs) && startMs < Number(deadlineMs);
  });

  const ranked = [...candidates].sort((a, b) => compareWwSlots(a, b, contract));
  const selected = new Set(ranked.slice(0, Math.min(requiredSlots, ranked.length)).map((slot) => slot.i));

  const actions = normalized.map((slot) => {
    if (!selected.has(slot.i)) return slot;
    return {
      ...slot,
      targets: { ...slot.targets, wwTargetW: Number(boilerW) },
      flexAllocatedW: slot.flexAllocatedW + Number(boilerW),
      allocationReason: slot.score.marginalImportW === 0
        ? 'PV_FULL'
        : slot.score.pvCoverageW > 0
          ? 'PV_PARTIAL'
          : String(contract || '').toUpperCase() === 'DYNAMIC'
            ? 'DEADLINE_REQUIRED_LOWEST_MARGINAL_IMPORT_THEN_PRICE'
            : 'DEADLINE_REQUIRED_LOWEST_MARGINAL_IMPORT',
    };
  });

  const selectedSlots = actions.filter((slot) => slot.targets.wwTargetW > 0);
  const scheduledEnergyKWh = selectedSlots.length * slotEnergyKWh;
  const allocatedDemandKWh = Math.min(requestedEnergyKWh, scheduledEnergyKWh);
  const plannedExcessEnergyKWh = Math.max(0, scheduledEnergyKWh - requestedEnergyKWh);
  const unallocatedEnergyKWh = Math.max(0, requestedEnergyKWh - scheduledEnergyKWh);
  const estimatedGridEnergyKWh = selectedSlots.reduce((sum, slot) => {
    if (!finiteNumber(slot.score.marginalImportW)) return sum;
    return sum + Number(slot.score.marginalImportW) * Number(slotMinutes) / 60000;
  }, 0);
  const estimatedPvEnergyKWh = selectedSlots.reduce((sum, slot) => {
    if (!finiteNumber(slot.score.pvCoverageW)) return sum;
    return sum + Number(slot.score.pvCoverageW) * Number(slotMinutes) / 60000;
  }, 0);
  const estimatedImportCostEur = selectedSlots.reduce((sum, slot) => {
    if (!finiteNumber(slot.score.marginalImportW) || !finiteNumber(slot.price_eur_kwh)) return sum;
    return sum + Number(slot.score.marginalImportW) * Number(slotMinutes) / 60000 * Number(slot.price_eur_kwh);
  }, 0);

  return {
    schema: 'EM2_PLANNER_WW_OPTIMIZER_V0.5_CANDIDATE',
    shadowOnly: true,
    physicalWritePerformed: false,
    modeledPowerW: Number(boilerW),
    slotMinutes: Number(slotMinutes),
    requestedEnergyKWh: round(requestedEnergyKWh),
    slotEnergyKWh: round(slotEnergyKWh),
    requiredSlots,
    selectedSlots: selectedSlots.length,
    scheduledEnergyKWh: round(scheduledEnergyKWh),
    allocatedDemandKWh: round(allocatedDemandKWh),
    plannedExcessEnergyKWh: round(plannedExcessEnergyKWh),
    unallocatedEnergyKWh: round(unallocatedEnergyKWh),
    estimatedPvEnergyKWh: round(estimatedPvEnergyKWh),
    estimatedGridEnergyKWh: round(estimatedGridEnergyKWh),
    estimatedImportCostEur: round(estimatedImportCostEur, 6),
    actions,
  };
}

module.exports = {
  DEFAULT_BOILER_W,
  DEFAULT_SLOT_MINUTES,
  normalizeSlot,
  compareWwSlots,
  optimizeWarmWater,
};
