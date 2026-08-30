// EM v2 | 12 Input | Core Snapshot Aggregator v0.2 SHADOW NO-QUOOKER
// Canonical source for temporary hourly parity diagnostic.
// Broad getVariables() is SHADOW-only and must be removed before production cut-over.

const OUT = '4c73123a-575a-4ec8-ab28-05256f88cff6';
const parse = x => {
  if (x == null || x === '') return null;
  if (typeof x !== 'string') return x;
  try { return JSON.parse(x); } catch { return x; }
};

const vars = await Homey.logic.getVariables();
const by = Object.fromEntries(Object.values(vars).map(v => [v.name, v.value]));
const snapshot = parse(by.EM2_Core_Input) || {};

const expected = {
  context: {
    updatedAt: by.EM2_Context_UpdatedAt,
    pvTop4h: by.M7_PV_Top4h,
    priceNegative: by.M7_Price_Negative,
    priceCheapNext4h: by.M7_Price_Cheap_Next4h,
    priceExpensiveNext4h: by.M7_Price_Expensive_Next4h
  },
  teslaGoal: {
    deadlineActive: by['EV Deadline actief'],
    deadline: by['EV Deadline tijd'],
    latestStart: by['EV Latest start'],
    remainingKWh: by['EV Resterend kWh'],
    status: by['EV Deadline status']
  },
  hotWater: {
    boilerMode: by.WW_Boilermodus,
    postGoalOpportunity: parse(by.EM2_WW_PostGoal_Opportunity)
  },
  planner: {
    contractPriceContext: parse(by.EM2_ContractPrice_Context),
    dayHistory: parse(by.EM2_Day_History),
    contractType: by.EM2_Contract_Type,
    priceBuffer: parse(by.TEMP_PBTH_JSON_BUFFER)
  },
  publication: {
    lastPublish: by.EM2_Last_Publish,
    lastPublishedRevision: by.EM2_Last_Published_Revision,
    lastPublisherVersion: by.EM2_Last_Publisher_Version
  },
  legacy: { wwStateV13: null }
};

const actual = snapshot.sources || {};
const mismatches = [];
for (const key of Object.keys(expected)) {
  if (JSON.stringify(actual[key]) !== JSON.stringify(expected[key])) mismatches.push(key);
}

const result = {
  schema: 'EM2_CORE_INPUT_PARITY_V0.1',
  checkedAt: new Date().toISOString(),
  ok: mismatches.length === 0,
  snapshotRevision: snapshot.revision ?? null,
  mismatches,
  note: 'Quooker excluded from Core v0.11b critical input path by architecture decision.'
};

await Homey.logic.updateVariable({
  id: OUT,
  variable: { value: JSON.stringify(result) }
});
return true;
