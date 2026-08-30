'use strict';

const PLANNER_TESLA_MIN_IMPORT_BUDGET_W = 4140;

function decideTeslaV011e(input) {
  const {
    deadlineActive = false,
    remainingKWh = 0,
    latestStartMs = NaN,
    nowMs = Date.now(),
    plugged = false,
    p1Fresh = false,
    gridMeasurementValid = false,
    discretionaryImportBudgetW = 0,
    plannerCompatible = false,
    plannerTesla = 'HOLD',
    plannerTeslaStart = null,
    plannerTeslaEnd = null,
    flexExportBudgetW = 0,
    teslaOpportunityW = 800,
    priceNegative = false,
    priceCheapNext4h = false,
    teslaPriceBudgetOk = false,
    noDeadlineBufferThresholdW = 1500,
  } = input || {};

  const remaining = Math.max(0, Number(remainingKWh) || 0);
  const plannerTeslaNormalized = String(plannerTesla || 'HOLD').toUpperCase();
  const plannerTeslaDeadlineSlot =
    plannerCompatible && plannerTeslaNormalized === 'PREFERRED_BEFORE_DEADLINE';
  const plannerTeslaImportGuardOk =
    Number(discretionaryImportBudgetW) >= PLANNER_TESLA_MIN_IMPORT_BUDGET_W;
  const beforeLatestStart = Number.isFinite(latestStartMs) && nowMs < latestStartMs;
  const atOrAfterLatestStart = Number.isFinite(latestStartMs) && nowMs >= latestStartMs;
  const plannerTeslaDeadlineEligible =
    plannerTeslaDeadlineSlot &&
    deadlineActive === true &&
    remaining > 0 &&
    beforeLatestStart &&
    plugged === true &&
    p1Fresh === true &&
    gridMeasurementValid === true;

  let priority = 'MAY';
  let intent = 'HOLD';
  let reason = 'Geen harde verplichting of sterke opportunity';
  let triggerSource = 'NONE';

  if (deadlineActive === true && remaining > 0 && atOrAfterLatestStart) {
    priority = 'MUST';
    intent = plugged ? 'TESLA_CHARGE_DEADLINE' : 'TESLA_DEADLINE_BLOCKED_NOT_CONNECTED';
    reason = `Tesla deadline catch-up: ${remaining.toFixed(2)} kWh resterend`;
    triggerSource = 'LATEST_START_MUST';
  } else if (plannerTeslaDeadlineEligible && plannerTeslaImportGuardOk) {
    priority = 'SHOULD';
    intent = 'TESLA_CHARGE_DEADLINE';
    reason = `PLANNER_TESLA_DEADLINE_SLOT_EXECUTED | ${plannerTeslaStart}–${plannerTeslaEnd} | importbudget ${Math.round(discretionaryImportBudgetW)} W`;
    triggerSource = 'PLANNER_DEADLINE_SLOT';
  } else if (plannerTeslaDeadlineSlot && deadlineActive === true && remaining > 0 && !plugged) {
    priority = 'SHOULD';
    intent = 'TESLA_WAIT_NOT_CONNECTED';
    reason = 'PLANNER_TESLA_BLOCKED_NOT_CONNECTED | deadline-slot actief';
    triggerSource = 'PLANNER_DEADLINE_SLOT';
  } else if (plannerTeslaDeadlineSlot && deadlineActive === true && remaining > 0 && (!p1Fresh || !gridMeasurementValid)) {
    priority = 'MAY';
    intent = 'HOLD';
    reason = 'PLANNER_TESLA_BLOCKED_P1 | deadline-slot actief maar P1 niet vers/geldig';
    triggerSource = 'PLANNER_DEADLINE_SLOT';
  } else if (plannerTeslaDeadlineSlot && deadlineActive === true && remaining > 0 && !plannerTeslaImportGuardOk) {
    priority = 'MAY';
    intent = 'HOLD';
    reason = `PLANNER_TESLA_BLOCKED_IMPORT_BUDGET | ${Math.round(discretionaryImportBudgetW)} W < ${PLANNER_TESLA_MIN_IMPORT_BUDGET_W} W`;
    triggerSource = 'PLANNER_DEADLINE_SLOT';
  } else if (
    deadlineActive === true &&
    remaining > 0 &&
    (Number(flexExportBudgetW) >= Number(teslaOpportunityW) ||
      priceNegative === true ||
      (priceCheapNext4h === true && teslaPriceBudgetOk === true))
  ) {
    priority = 'SHOULD';
    intent = plugged ? 'TESLA_CHARGE_OPPORTUNITY' : 'TESLA_WAIT_NOT_CONNECTED';
    reason = Number(flexExportBudgetW) >= Number(teslaOpportunityW)
      ? `Flex-exportbudget ${Math.round(flexExportBudgetW)} W`
      : priceNegative
        ? 'Negatieve prijs'
        : `Goedkoop prijsvenster; importbudget ${Math.round(discretionaryImportBudgetW)} W`;
    triggerSource = 'REALTIME_OPPORTUNITY';
  } else if (
    deadlineActive !== true &&
    plugged === true &&
    Number(flexExportBudgetW) >= Number(noDeadlineBufferThresholdW)
  ) {
    priority = 'MAY';
    intent = 'TESLA_BUFFER_EXPORT';
    reason = `Geen deadline; flex-exportbudget ${Math.round(flexExportBudgetW)} W`;
    triggerSource = 'REALTIME_OPPORTUNITY';
  }

  return {
    priority,
    intent,
    reason,
    triggerSource,
    planner: {
      plannerTesla: plannerTeslaNormalized,
      plannerTeslaDeadlineSlot,
      plannerTeslaDeadlineEligible,
      plannerTeslaImportGuardOk,
      plannerTeslaStart,
      plannerTeslaEnd,
      minImportBudgetW: PLANNER_TESLA_MIN_IMPORT_BUDGET_W,
    },
  };
}

module.exports = {
  PLANNER_TESLA_MIN_IMPORT_BUDGET_W,
  decideTeslaV011e,
};
