'use strict';

const SUPPORTED_PLANNER_SCHEMAS = new Set([
  'EM2_ENERGY_PLAN_24H_V0.4.9',
  'EM2_ENERGY_PLAN_24H_V0.5.0',
]);

function parseTime(value) {
  const ms = Date.parse(String(value || ''));
  return Number.isFinite(ms) ? ms : null;
}

function localDateEuropeAmsterdam(ms) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Amsterdam',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date(ms));
  const get = (type) => parts.find((p) => p.type === type)?.value;
  return `${get('year')}-${get('month')}-${get('day')}`;
}

function parsePlannerForCore(plannerSnap, options = {}) {
  const nowMs = Number.isFinite(Number(options.nowMs)) ? Number(options.nowMs) : Date.now();
  const freshMs = Number.isFinite(Number(options.freshMs)) ? Number(options.freshMs) : 35 * 60 * 1000;
  const modeledWwPowerW = Number.isFinite(Number(options.modeledWwPowerW)) ? Number(options.modeledWwPowerW) : 1900;

  const generatedAt = plannerSnap?.generatedAt ?? plannerSnap?.plan?.generatedAt ?? null;
  const generatedAtMs = parseTime(generatedAt);
  const fresh = generatedAtMs !== null && nowMs - generatedAtMs >= 0 && nowMs - generatedAtMs <= freshMs;
  const schema = String(plannerSnap?.plan?.schema || '');
  const schemaSupported = SUPPORTED_PLANNER_SCHEMAS.has(schema);
  const actions = schemaSupported && Array.isArray(plannerSnap?.plan?.plan?.actions)
    ? plannerSnap.plan.plan.actions
    : [];
  const slot = actions.find((a) => {
    const startMs = parseTime(a?.start);
    const endMs = parseTime(a?.end);
    return startMs !== null && endMs !== null && startMs <= nowMs && nowMs < endMs;
  }) || null;

  let slotContractValid = !!slot;
  let wwTargetW = null;
  let plannerWW = 'HOLD';
  let plannerWWReason = String(slot?.warmWaterReason || 'UNKNOWN');
  let compatibilityReason = 'OK';

  if (!fresh) {
    slotContractValid = false;
    compatibilityReason = 'PLANNER_STALE';
  } else if (!schemaSupported) {
    slotContractValid = false;
    compatibilityReason = 'UNSUPPORTED_SCHEMA';
  } else if (!slot) {
    slotContractValid = false;
    compatibilityReason = 'NO_CURRENT_SLOT';
  } else if (schema === 'EM2_ENERGY_PLAN_24H_V0.5.0') {
    const localDate = String(slot.localDate || '');
    const today = localDateEuropeAmsterdam(nowMs);
    const relation = String(slot.warmWaterDayRelation || '');
    const rawTarget = slot?.targets?.wwTargetW;
    const targetValid = rawTarget === 0 || rawTarget === modeledWwPowerW;
    const dayValid = localDate === today && (relation === '' || relation === 'CURRENT_DAY');
    const warmWater = String(slot.warmWater || 'HOLD').toUpperCase();
    const actionValid = rawTarget === 0
      ? warmWater === 'HOLD'
      : warmWater === 'PV_PREFERRED' || warmWater === 'DEADLINE_REQUIRED';

    if (!targetValid) {
      slotContractValid = false;
      compatibilityReason = 'INVALID_WW_TARGET';
    } else if (!dayValid) {
      slotContractValid = false;
      compatibilityReason = 'NON_CURRENT_DAY_SLOT';
    } else if (!actionValid) {
      slotContractValid = false;
      compatibilityReason = 'TARGET_ACTION_MISMATCH';
    } else {
      wwTargetW = rawTarget;
      plannerWW = rawTarget === modeledWwPowerW ? warmWater : 'HOLD';
    }
  } else {
    // v0.4.9 compatibility is intentionally unchanged.
    plannerWW = String(slot.warmWater || 'HOLD').toUpperCase();
    wwTargetW = plannerWW === 'PV_PREFERRED' || plannerWW === 'DEADLINE_REQUIRED'
      ? modeledWwPowerW
      : 0;
  }

  const compatible = fresh && schemaSupported && slotContractValid;
  if (!compatible) {
    plannerWW = 'HOLD';
    wwTargetW = null;
  }

  return {
    fresh,
    schema,
    schemaSupported,
    compatible,
    compatibilityReason,
    slot,
    plannerWW,
    plannerWWReason,
    wwTargetW,
    plannerWWStart: compatible ? slot?.start ?? null : null,
    plannerWWEnd: compatible ? slot?.end ?? null : null,
    plannerPvSlot: compatible && plannerWW === 'PV_PREFERRED' && wwTargetW === modeledWwPowerW,
    plannerGridSlot: compatible && plannerWW === 'DEADLINE_REQUIRED' && wwTargetW === modeledWwPowerW,
  };
}

module.exports = {
  SUPPORTED_PLANNER_SCHEMAS,
  parsePlannerForCore,
};
