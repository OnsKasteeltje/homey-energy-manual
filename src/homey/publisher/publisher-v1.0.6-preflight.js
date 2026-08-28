// EM v2 | 40 Data | Publisher v1.0.6 — preflight instrumentation
// Read-only with respect to physical devices. Writes diagnostic Logic variables only.

const vars = await Homey.logic.getVariables();
const byName = Object.fromEntries(Object.values(vars).map(v => [v.name, v]));

const upsertNumber = async (name, value) => {
  const existing = byName[name];
  if (existing) {
    if (Number(existing.value) !== Number(value)) {
      await Homey.logic.updateVariable({ id: existing.id, variable: { value: Number(value) } });
      existing.value = Number(value);
    }
    return;
  }
  const created = await Homey.logic.createVariable({ variable: { name, type: 'number', value: Number(value) } });
  byName[name] = created;
};

const parse = (name) => {
  try { return JSON.parse(String(byName[name]?.value ?? '')); }
  catch { return null; }
};

const pub = parse('EM2_Public_State');
const state = parse('EM2_State');
const pubRev = Number(pub?.meta?.state_revision);
const stateRev = Number(state?.revision);
const attemptRev = Number.isFinite(pubRev) ? pubRev : (Number.isFinite(stateRev) ? stateRev : 0);

await upsertNumber('EM2_Publisher_Flow_LastAttemptRevision', attemptRev);

let diag = 120;
let reason = 'READY';
if (!pub || typeof pub !== 'object') {
  diag = 110; reason = 'PUBLIC_STATE_MISSING_OR_INVALID';
} else if (!Number.isFinite(pubRev) || pubRev <= 0) {
  diag = 111; reason = 'PUBLIC_STATE_REVISION_MISSING';
} else if (!state || typeof state !== 'object') {
  diag = 112; reason = 'CORE_STATE_MISSING_OR_INVALID';
} else if (!Number.isFinite(stateRev) || stateRev <= 0 || stateRev !== pubRev) {
  diag = 113; reason = 'PUBLIC_CORE_REVISION_MISMATCH';
}

await upsertNumber('EM2_Publisher_Flow_Diag_Code', diag);

if (diag !== 120) {
  throw new Error(`PUBLISHER_PREFLIGHT_${diag}_${reason}_PUB${Number.isFinite(pubRev) ? pubRev : 'NA'}_STATE${Number.isFinite(stateRev) ? stateRev : 'NA'}`);
}

return true;
