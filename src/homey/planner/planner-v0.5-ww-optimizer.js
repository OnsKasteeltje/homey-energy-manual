'use strict';

/**
 * Planner v0.5 WW optimizer candidate.
 *
 * Pure function module: no Homey API access, no network access, no physical writes.
 * Intended for synthetic validation before any HomeyScript integration.
 *
 * v0.5 policy:
 * - treat WW as remaining energy, not one contiguous window;
 * - reserve forecast slots with zero marginal grid import immediately;
 * - defer grid-requiring fallback while enough time remains before the deadline;
 * - once deadline feasibility becomes tight, reserve only the minimum remaining
 *   fallback slots, ranked by marginal import and then price;
 * - keep all output SHADOW-only.
 */

const DEFAULT_BOILER_W = 1900;
const DEFAULT_SLOT_MINUTES = 15;
const DEFAULT_GRID_FALLBACK_SAFETY_SLOTS = 2; // 30 min at 15-minute resolution.

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

  if (aKnown && bKnown && a.score.marginalImportW !== b.score.marginalImportW) {
    return a.score.marginalImportW - b.score.marginalImportW;
  }

  if (aKnown && bKnown && a.score.pvCoverageW !== b.score.pvCoverageW) {
    return b.score.pvCoverageW - a.score.pvCoverageW;
  }

  if (String(contract || '').toUpperCase() === 'DYNAMIC') {
    const ap = finiteNumber(a.price_eur_kwh) ? Number(a.price_eur_kwh) : Number.POSITIVE_INFINITY;
    const bp = finiteNumber(b.price_eur_kwh) ? Number(b.price_eur_kwh) : Number.POSITIVE_INFINITY;
    if (ap !== bp) return ap - bp;
  }

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
  deferGridFallback = true,
  gridFallbackSafetySlots = DEFAULT_GRID_FALLBACK_SAFETY_SLOTS,
}) {
  if (!Array.isArray(slots)) throw new TypeError('slots must be an array');
  if (!finiteNumber(boilerW) || Number(boilerW) <= 0) throw new TypeError('boilerW must be > 0');
  if (!finiteNumber(slotMinutes) || Number(slotMinutes) <= 0) throw new TypeError('slotMinutes must be > 0');
  if (!finiteNumber(gridFallbackSafetySlots) || Number(gridFallbackSafetySlots) < 0) throw new TypeError('gridFallbackSafetySlots must be >= 0');

  const normalized = slots.map((slot, index) => normalizeSlot(slot, index, Number(boilerW), Number(slotMinutes)));
  const requestedEnergyKWh = goalReachedToday ? 0 : Math.max(0, Number(wwRemainingEnergyKWh) || 0);
  const slotEnergyKWh = Number(boilerW) * Number(slotMinutes) / 60000;
  const requiredSlots = requestedEnergyKWh > 0 ? Math.ceil(requestedEnergyKWh / slotEnergyKWh) : 0;
  const hasDeadline = finiteNumber(deadlineMs);

  const candidates = normalized.filter((slot) => {
    if (!hasDeadline) return true;
    const startMs = Date.parse(String(slot.start || ''));
    return Number.isFinite(startMs) && startMs < Number(deadlineMs);
  });

  const fullPvCandidates = candidates
    .filter((slot) => finiteNumber(slot.score.marginalImportW) && Number(slot.score.marginalImportW) <= 1e-9)
    .sort((a, b) => compareWwSlots(a, b, contract));

  const selectedIds = [];
  for (const slot of fullPvCandidates) {
    if (selectedIds.length >= requiredSlots) break;
    selectedIds.push(slot.i);
  }

  const gridSlotsNeeded = Math.max(0, requiredSlots - selectedIds.length);
  const remainingCandidates = candidates.filter((slot) => !selectedIds.includes(slot.i));
  const remainingFeasibleSlots = remainingCandidates.length;
  const safetySlots = Math.max(0, Math.floor(Number(gridFallbackSafetySlots)));
  const deadlineUrgent = gridSlotsNeeded > 0 && remainingFeasibleSlots <= gridSlotsNeeded + safetySlots;
  const gridFallbackActive = gridSlotsNeeded > 0 && (!deferGridFallback || deadlineUrgent || !hasDeadline);

  if (gridFallbackActive) {
    const rankedFallback = [...remainingCandidates].sort((a, b) => compareWwSlots(a, b, contract));
    for (const slot of rankedFallback) {
      if (selectedIds.length >= requiredSlots) break;
      selectedIds.push(slot.i);
    }
  }

  const selected = new Set(selectedIds);
  let remainingDemandKWh = requestedEnergyKWh;
  const actions = normalized.map((slot) => {
    if (!selected.has(slot.i)) return slot;
    const allocatedDemandKWh = Math.min(slotEnergyKWh, Math.max(0, remainingDemandKWh));
    remainingDemandKWh -= allocatedDemandKWh;
    const fallbackReason = String(contract || '').toUpperCase() === 'DYNAMIC'
      ? 'DEADLINE_REQUIRED_LOWEST_MARGINAL_IMPORT_THEN_PRICE'
      : 'DEADLINE_REQUIRED_LOWEST_MARGINAL_IMPORT';
    return {
      ...slot,
      targets: { ...slot.targets, wwTargetW: Number(boilerW) },
      flexAllocatedW: slot.flexAllocatedW + Number(boilerW),
      allocatedDemandKWh: round(allocatedDemandKWh),
      allocationReason: slot.score.marginalImportW === 0
        ? 'PV_FULL'
        : slot.score.pvCoverageW > 0
          ? (gridFallbackActive ? 'PV_PARTIAL_DEADLINE_FALLBACK' : 'PV_PARTIAL')
          : fallbackReason,
    };
  });

  const selectedSlots = actions.filter((slot) => slot.targets.wwTargetW > 0);
  const scheduledEnergyKWh = selectedSlots.length * slotEnergyKWh;
  const allocatedDemandKWh = Math.min(requestedEnergyKWh, selectedSlots.reduce((sum, slot) => sum + (Number(slot.allocatedDemandKWh) || 0), 0));
  const plannedExcessEnergyKWh = Math.max(0, scheduledEnergyKWh - allocatedDemandKWh);
  const unallocatedEnergyKWh = Math.max(0, requestedEnergyKWh - allocatedDemandKWh);
  const estimatedGridEnergyKWh = selectedSlots.reduce((sum, slot) => {
    if (!finiteNumber(slot.score.marginalImportW)) return sum;
    const fraction = slotEnergyKWh > 0 ? Math.min(1, (Number(slot.allocatedDemandKWh) || slotEnergyKWh) / slotEnergyKWh) : 1;
    return sum + Number(slot.score.marginalImportW) * Number(slotMinutes) / 60000 * fraction;
  }, 0);
  const estimatedPvEnergyKWh = selectedSlots.reduce((sum, slot) => {
    if (!finiteNumber(slot.score.pvCoverageW)) return sum;
    const fraction = slotEnergyKWh > 0 ? Math.min(1, (Number(slot.allocatedDemandKWh) || slotEnergyKWh) / slotEnergyKWh) : 1;
    return sum + Number(slot.score.pvCoverageW) * Number(slotMinutes) / 60000 * fraction;
  }, 0);
  const estimatedImportCostEur = selectedSlots.reduce((sum, slot) => {
    if (!finiteNumber(slot.score.marginalImportW) || !finiteNumber(slot.price_eur_kwh)) return sum;
    const fraction = slotEnergyKWh > 0 ? Math.min(1, (Number(slot.allocatedDemandKWh) || slotEnergyKWh) / slotEnergyKWh) : 1;
    return sum + Number(slot.score.marginalImportW) * Number(slotMinutes) / 60000 * fraction * Number(slot.price_eur_kwh);
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
    fullPvSlotsSelected: selectedSlots.filter((slot) => slot.score.marginalImportW === 0).length,
    gridSlotsNeeded,
    remainingFeasibleSlots,
    gridFallbackSafetySlots: safetySlots,
    deferGridFallback: Boolean(deferGridFallback),
    deadlineUrgent,
    gridFallbackActive,
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
  DEFAULT_GRID_FALLBACK_SAFETY_SLOTS,
  normalizeSlot,
  compareWwSlots,
  optimizeWarmWater,
};
