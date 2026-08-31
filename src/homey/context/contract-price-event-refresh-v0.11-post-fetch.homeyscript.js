// Contract Price Event Refresh v0.11 — POST-FETCH SEMANTIC PROCESSOR
// Targeted Logic reads/writes only. Context-only. No actuator/device writes.
// Replace __EVENT_STATE_ID__ exactly once after one-shot provisioning.

const IDS = {
  mirror: '211e5846-aada-4607-8d52-01b2ef578866',
  buffer: '29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b',
  context: '93e41221-6b4d-4f5f-83dc-997c9620f758',
  source: '3e5a182d-2479-479a-bb58-42a27f4a4e23',
  quality: 'abedc6f4-cfee-4496-9b3c-418f1f3ad2bc',
  horizon: '587ea957-f9e9-44c7-b975-3bed53bd9ab8',
  updatedAt: '77e16ec7-9ebb-4488-9caf-47c1ab3d4ddb',
  eventState: '__EVENT_STATE_ID__'
};

const COOLDOWN_MS = 60 * 60 * 1000;
const EPS = 1e-9;
const read = async id => Homey.logic.getVariable({ id });
const write = async (id, value) => Homey.logic.updateVariable({ id, variable: { value } });
const parse = s => { try { return JSON.parse(String(s ?? '')); } catch { return null; } };

const nowMs = Date.now();
const nowIso = new Date(nowMs).toISOString();
const stateVar = await read(IDS.eventState);
const eventState = parse(stateVar?.value) || {};
const oldVar = await read(IDS.context);
const oldCtx = parse(oldVar?.value) || {};
const oldPrices = Array.isArray(oldCtx.priceSeries)
  ? oldCtx.priceSeries.map(Number).filter(Number.isFinite)
  : [];

const buffer = await read(IDS.buffer);
const raw = parse(buffer?.value);
const source = Array.isArray(raw) ? raw : [];
const prices = [];
for (const v of source) {
  const n = Number(v);
  if (!Number.isFinite(n) || n <= -2 || n >= 5) break;
  prices.push(n);
}

async function setCooldown(result, reason) {
  await write(IDS.eventState, JSON.stringify({
    ...eventState,
    cooldownUntil: new Date(nowMs + COOLDOWN_MS).toISOString(),
    lastResult: result,
    lastReason: reason
  }));
  return false;
}

if (prices.length < 4) {
  return await setCooldown('DEGRADED', 'LT_4_CONTIGUOUS_SLOTS');
}

const oldSlots = Number(oldCtx.slots) || oldPrices.length || 0;
const oldHorizon = Number(oldCtx.horizonHours) || oldSlots * 0.25;
const newSlots = prices.length;
const newHorizon = newSlots * 0.25;
const overlap = Math.min(oldPrices.length, prices.length);
let priceChanged = false;
for (let i = 0; i < overlap; i++) {
  if (Math.abs(Number(oldPrices[i]) - prices[i]) > EPS) {
    priceChanged = true;
    break;
  }
}

const changed = newSlots > oldSlots || newHorizon > oldHorizon + EPS || priceChanged;
if (!changed) {
  return await setCooldown('UNCHANGED', 'NO_SEMANTIC_PRICE_CHANGE');
}

const horizon = newHorizon >= 12 ? 'FULL' : newHorizon >= 6 ? 'INTRADAY' : 'DIAGNOSTIC';
const ctx = {
  ...oldCtx,
  schema: 'EM2_UNIFORM_PRICE_CONTEXT_V0.4',
  contractType: 'DYNAMIC',
  source: 'PBTH_PRICES_JSON_TARGETED_EVENT',
  quality: 'GOOD',
  updatedAt: nowIso,
  importPriceNow: prices[0],
  negativeNow: prices[0] < 0,
  horizon,
  horizonHours: newHorizon,
  slotMinutes: 15,
  slots: newSlots,
  priceSeries: prices,
  guards: {
    ...(oldCtx.guards || {}),
    targetedLogicReads: true,
    broadLogicEnumeration: false,
    broadDeviceEnumeration: false,
    pbthActionCardOnly: true,
    noActuatorWrites: true,
    eventDrivenShortHorizonRefresh: true,
    eventRefreshThresholdHours: 12,
    noChangeCooldownMinutes: 60
  }
};

await write(IDS.mirror, 'DYNAMIC');
await write(IDS.context, JSON.stringify(ctx));
await write(IDS.source, ctx.source);
await write(IDS.quality, 'GOOD');
await write(IDS.horizon, horizon);
await write(IDS.updatedAt, nowIso);
await write(IDS.eventState, JSON.stringify({
  ...eventState,
  cooldownUntil: null,
  lastResult: 'UPDATED',
  lastReason: 'SEMANTIC_PRICE_CHANGE'
}));

return true;
