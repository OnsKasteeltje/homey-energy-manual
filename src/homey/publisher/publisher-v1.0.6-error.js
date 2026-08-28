// EM v2 | 40 Data | Publisher v1.0.6 — error instrumentation
// Preserves a preflight 1xx code; otherwise marks the publish-script card error as 510.

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

const legacyDiag = Number(byName.EM2_Publisher_Diag_Code?.value);
const flowDiag = Number(byName.EM2_Publisher_Flow_Diag_Code?.value);
await upsertNumber('EM2_Publisher_Script_Diag_Mirror', Number.isFinite(legacyDiag) ? legacyDiag : -1);
if (!(flowDiag >= 110 && flowDiag <= 119)) {
  await upsertNumber('EM2_Publisher_Flow_Diag_Code', 510);
}
return true;
