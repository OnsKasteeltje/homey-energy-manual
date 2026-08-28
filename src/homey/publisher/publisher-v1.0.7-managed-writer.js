// EM v2 | 40 Data | Publisher v1.0.7 — GitHub-managed writer
// Publication infrastructure only: reads Homey Logic, writes GitHub public JSON + publication Logic metadata.
// No Homey device reads or physical actuator writes.

const VERSION = 'EM2_PUBLISHER_V1.0.7';
const OWNER = 'OnsKasteeltje';
const REPO = 'homey-energy-manual';
const PATH = 'docs/data/energy-state-v2.json';
const BRANCH = 'main';
const HEARTBEAT_MS = 6 * 60 * 1000;

const vars = await Homey.logic.getVariables();
const byName = Object.fromEntries(Object.values(vars).map(v => [v.name, v]));

const parseJSON = (name) => {
  try { return JSON.parse(String(byName[name]?.value ?? '')); }
  catch { return null; }
};
const numberValue = (name) => Number(byName[name]?.value);
const boolValue = (name) => Boolean(byName[name]?.value);
const stringValue = (name) => String(byName[name]?.value ?? '');

const setExisting = async (name, value) => {
  const v = byName[name];
  if (!v) return false;
  if (v.value !== value) {
    await Homey.logic.updateVariable({ id: v.id, variable: { value } });
    v.value = value;
  }
  return true;
};
const upsertNumber = async (name, value) => {
  if (await setExisting(name, Number(value))) return;
  const created = await Homey.logic.createVariable({ variable: { name, type: 'number', value: Number(value) } });
  byName[name] = created;
};
const upsertString = async (name, value) => {
  value = String(value);
  if (await setExisting(name, value)) return;
  const created = await Homey.logic.createVariable({ variable: { name, type: 'string', value } });
  byName[name] = created;
};
const upsertBoolean = async (name, value) => {
  value = Boolean(value);
  if (await setExisting(name, value)) return;
  const created = await Homey.logic.createVariable({ variable: { name, type: 'boolean', value } });
  byName[name] = created;
};

const setDiag = async (code, status, extra = {}) => {
  await upsertNumber('EM2_Publisher_Flow_Diag_Code', code);
  await upsertNumber('EM2_Publisher_Diag_Code', code);
  await upsertString('EM2_Publisher_Status', JSON.stringify({
    schema: 'EM2_PUBLISHER_STATUS_V1.0.7',
    version: VERSION,
    at: new Date().toISOString(),
    status,
    ...extra,
  }));
};

const pub = parseJSON('EM2_Public_State');
const state = parseJSON('EM2_State');
const pubRev = Number(pub?.meta?.state_revision);
const stateRev = Number(state?.revision);
const attemptRev = Number.isFinite(pubRev) ? pubRev : (Number.isFinite(stateRev) ? stateRev : 0);
await upsertNumber('EM2_Publisher_Flow_LastAttemptRevision', attemptRev);

if (!pub || typeof pub !== 'object') {
  await setDiag(410, 'BLOCKED_PUBLIC_STATE_MISSING');
  await upsertBoolean('EM2_Publish_Due', true);
  throw new Error('PUBLISHER_410_PUBLIC_STATE_MISSING');
}
if (!Number.isFinite(pubRev) || pubRev <= 0) {
  await setDiag(411, 'BLOCKED_REVISION_MISSING');
  await upsertBoolean('EM2_Publish_Due', true);
  throw new Error('PUBLISHER_411_REVISION_MISSING');
}
if (!state || typeof state !== 'object' || !Number.isFinite(stateRev) || stateRev <= 0 || stateRev !== pubRev) {
  await setDiag(412, 'BLOCKED_REVISION_MISMATCH', { publicRevision: pubRev, coreRevision: Number.isFinite(stateRev) ? stateRev : null });
  await upsertBoolean('EM2_Publish_Due', true);
  throw new Error(`PUBLISHER_412_REVISION_MISMATCH_${pubRev}_${Number.isFinite(stateRev) ? stateRev : 'NA'}`);
}

const token = stringValue('GH_Status_Token').trim();
if (!token) {
  await setDiag(413, 'BLOCKED_TOKEN_MISSING', { sourceRevision: pubRev });
  await upsertBoolean('EM2_Publish_Due', true);
  throw new Error('PUBLISHER_413_TOKEN_MISSING');
}

const lastPublishedRevision = numberValue('EM2_Last_Published_Revision');
const lastPublishRaw = stringValue('EM2_Last_Publish');
const lastPublishMs = Date.parse(lastPublishRaw);
const heartbeatDue = !Number.isFinite(lastPublishMs) || (Date.now() - lastPublishMs) >= HEARTBEAT_MS;
const forced = boolValue('EM2_Publish_Due');
const revisionDue = !Number.isFinite(lastPublishedRevision) || lastPublishedRevision !== pubRev;

if (!revisionDue && !heartbeatDue && !forced) {
  await setDiag(211, 'SKIP_CURRENT', { sourceRevision: pubRev });
  return true;
}

const publishReason = revisionDue ? 'REVISION_RETRY' : (forced ? 'FORCED_RETRY' : 'HEARTBEAT_RETRY');
const now = new Date().toISOString();
const payload = JSON.parse(JSON.stringify(pub));
payload.meta = payload.meta || {};
payload.meta.generated_at = now;
payload.meta.heartbeat_at = now;
payload.meta.publisher_version = VERSION;
payload.meta.publish_reason = publishReason;
payload.meta.state_revision = pubRev;

const deadlineStatus = stringValue('EV Deadline status').trim();
if (deadlineStatus) {
  payload.tesla = payload.tesla || {};
  payload.tesla.deadline_status = deadlineStatus;
}

const apiUrl = `https://api.github.com/repos/${OWNER}/${REPO}/contents/${PATH}`;
const headers = {
  Accept: 'application/vnd.github+json',
  Authorization: `Bearer ${token}`,
  'X-GitHub-Api-Version': '2022-11-28',
};

let sha = null;
let getStatus = 0;
try {
  const getResp = await fetch(`${apiUrl}?ref=${encodeURIComponent(BRANCH)}`, { method: 'GET', headers });
  getStatus = getResp.status;
  if (getResp.status === 200) {
    const current = await getResp.json();
    sha = current?.sha || null;
  } else if (getResp.status !== 404) {
    const body = await getResp.text();
    await setDiag(421, 'GITHUB_GET_ERROR', { sourceRevision: pubRev, httpStatus: getResp.status });
    await upsertBoolean('EM2_Publish_Due', true);
    throw new Error(`PUBLISHER_421_GITHUB_GET_${getResp.status}_${body.slice(0, 120)}`);
  }
} catch (e) {
  if (String(e?.message || e).startsWith('PUBLISHER_421_')) throw e;
  await setDiag(421, 'GITHUB_GET_ERROR', { sourceRevision: pubRev, httpStatus: getStatus || null });
  await upsertBoolean('EM2_Publish_Due', true);
  throw new Error(`PUBLISHER_421_GITHUB_GET_EXCEPTION_${String(e?.message || e).slice(0, 160)}`);
}

const encoded = Buffer.from(JSON.stringify(payload, null, 2) + '\n', 'utf8').toString('base64');
const putBody = {
  message: `data: publish energy state r${pubRev}`,
  content: encoded,
  branch: BRANCH,
  ...(sha ? { sha } : {}),
};

let putResp;
try {
  putResp = await fetch(apiUrl, {
    method: 'PUT',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify(putBody),
  });
} catch (e) {
  await setDiag(422, 'GITHUB_PUT_ERROR', { sourceRevision: pubRev, httpStatus: null });
  await upsertBoolean('EM2_Publish_Due', true);
  throw new Error(`PUBLISHER_422_GITHUB_PUT_EXCEPTION_${String(e?.message || e).slice(0, 160)}`);
}

if (!(putResp.status === 200 || putResp.status === 201)) {
  const body = await putResp.text();
  await setDiag(422, 'GITHUB_PUT_ERROR', { sourceRevision: pubRev, httpStatus: putResp.status });
  await upsertBoolean('EM2_Publish_Due', true);
  throw new Error(`PUBLISHER_422_GITHUB_PUT_${putResp.status}_${body.slice(0, 120)}`);
}

await upsertString('EM2_Public_State', JSON.stringify(payload));
await upsertString('EM2_Last_Publish', now);
await upsertNumber('EM2_Last_Published_Revision', pubRev);
await upsertString('EM2_Last_Publisher_Version', VERSION);
await upsertBoolean('EM2_Publish_Due', false);
await setDiag(210, 'PUBLISHED', { sourceRevision: pubRev, publishReason });

return true;
