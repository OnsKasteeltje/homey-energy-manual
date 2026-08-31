// Contract Price Event Refresh v0.11 — ONE-SHOT STATE PROVISIONING
// Run exactly once. No broad Logic/device enumeration. No physical device writes.
// Returns the created Logic variable ID so it can be committed back to GitHub.

const NAME = 'EM2_ContractPrice_EventRefresh_State';
const INITIAL_VALUE = JSON.stringify({
  schema: 'EM2_PRICE_EVENT_REFRESH_STATE_V0.1',
  lastAttemptAt: null,
  cooldownUntil: null,
  lastResult: 'NEVER',
  lastReason: null
});

const created = await Homey.logic.createVariable({
  variable: {
    name: NAME,
    type: 'string',
    value: INITIAL_VALUE
  }
});

if (!created?.id) {
  throw new Error('EVENT_REFRESH_STATE_CREATE_FAILED_NO_ID');
}

return JSON.stringify({
  ok: true,
  name: NAME,
  id: created.id,
  type: created.type,
  value: created.value
});
