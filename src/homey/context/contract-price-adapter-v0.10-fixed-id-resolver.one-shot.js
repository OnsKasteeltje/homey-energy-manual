// ONE-SHOT READ-ONLY helper for Contract Price Adapter v0.10 preparation.
// Purpose: resolve the current Homey Logic variable IDs for the FIXED contract inputs.
// Safety: exactly one Homey.logic.getVariables() enumeration; no writes, no devices, no flows, no notifications.
// Remove after use.

const WANTED = [
  'EM2_Fixed_Import_Normal',
  'EM2_Fixed_Import_Offpeak',
  'EM2_Fixed_Export',
  'EM2_Fixed_Offpeak_Active',
  'EM2_Contract_EndDate'
];

const vars = await Homey.logic.getVariables();
const all = Object.values(vars || {});
const result = {};
for (const name of WANTED) {
  const matches = all.filter(v => v?.name === name);
  result[name] = matches.map(v => ({ id: v.id, type: v.type, value: v.value }));
}

return {
  schema: 'EM2_CONTRACT_PRICE_V010_FIXED_ID_RESOLVER_V0.1',
  readOnly: true,
  broadLogicEnumerationCount: 1,
  deviceReads: false,
  writes: false,
  resolved: result
};
