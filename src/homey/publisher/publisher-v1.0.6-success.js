// EM v2 | 40 Data | Publisher v1.0.6 — post-script success instrumentation
// Records that the HomeyScript action card returned success. It does not prove GitHub changed.

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
await upsertNumber('EM2_Publisher_Script_Diag_Mirror', Number.isFinite(legacyDiag) ? legacyDiag : -1);
await upsertNumber('EM2_Publisher_Flow_Diag_Code', 200);
return true;
