// EM v2 | 40 Data | Publisher Probe v0.1 — Logic snapshot
// Diagnostic only. One Logic enumeration, no physical device reads or writes.

const vars = await Homey.logic.getVariables();
const byName = Object.fromEntries(Object.values(vars).map(v => [v.name, v]));
const n = name => Number(byName[name]?.value);
const clean = v => Number.isFinite(v) ? String(v) : 'NA';

const flowDiag = n('EM2_Publisher_Flow_Diag_Code');
const mirror = n('EM2_Publisher_Script_Diag_Mirror');
const attempt = n('EM2_Publisher_Flow_LastAttemptRevision');
const legacy = n('EM2_Publisher_Diag_Code');
const last = n('EM2_Last_Published_Revision');

const snapshotName = `TEMP_PUBDIAG_F${clean(flowDiag)}_M${clean(mirror)}_A${clean(attempt)}_L${clean(legacy)}_P${clean(last)}`;
const existing = Object.values(vars).find(v => v.name === snapshotName);
if (!existing) {
  await Homey.logic.createVariable({ variable: { name: snapshotName, type: 'number', value: 1 } });
}

return true;
