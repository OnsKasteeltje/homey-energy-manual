// Contract Price Event Refresh v0.11 — EVENT ELIGIBILITY GATE
// Targeted Logic reads only. No PBTH call. No device writes.
// Replace __EVENT_STATE_ID__ exactly once after one-shot provisioning.

const IDS = {
  canonical: '8d346495-f183-4072-86d0-c4bc9da94e2e',
  context: '93e41221-6b4d-4f5f-83dc-997c9620f758',
  eventState: '__EVENT_STATE_ID__'
};

const read = async id => Homey.logic.getVariable({ id });
const write = async (id, value) => Homey.logic.updateVariable({ id, variable: { value } });
const parse = s => { try { return JSON.parse(String(s ?? '')); } catch { return null; } };

const nowMs = Date.now();
const nowIso = new Date(nowMs).toISOString();
const canonical = await read(IDS.canonical);
const contract = String(canonical?.value || 'FIXED').toUpperCase();
const stateVar = await read(IDS.eventState);
const eventState = parse(stateVar?.value) || {
  schema: 'EM2_PRICE_EVENT_REFRESH_STATE_V0.1',
  lastAttemptAt: null,
  cooldownUntil: null,
  lastResult: 'NEVER',
  lastReason: null
};

async function stop(result, reason) {
  await write(IDS.eventState, JSON.stringify({ ...eventState, lastResult: result, lastReason: reason }));
  return false;
}

if (contract !== 'DYNAMIC') return await stop('SKIPPED_FIXED', 'CONTRACT_NOT_DYNAMIC');

const contextVar = await read(IDS.context);
const context = parse(contextVar?.value) || {};
const horizonHours = Number(context.horizonHours);
if (Number.isFinite(horizonHours) && horizonHours >= 12) {
  return await stop('SKIPPED_HORIZON_OK', 'HORIZON_GTE_12H');
}

const cooldownUntilMs = Date.parse(String(eventState.cooldownUntil || ''));
if (Number.isFinite(cooldownUntilMs) && nowMs < cooldownUntilMs) {
  return await stop('SKIPPED_COOLDOWN', 'NO_CHANGE_COOLDOWN');
}

await write(IDS.eventState, JSON.stringify({
  ...eventState,
  lastAttemptAt: nowIso,
  lastResult: 'ATTEMPT_ADMITTED',
  lastReason: 'HORIZON_LT_12H'
}));

return true;
