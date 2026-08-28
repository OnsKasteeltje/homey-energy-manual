// EM v2 | 40 Data | Publisher v1.0.8 event-driven LOW-LOAD
// Trigger contract: EM2_Public_State variable_changed (plus manual start for recovery/smoke).
// Homey load contract: targeted Logic reads only; NO getVariables(), NO getDevices(), NO device writes.
// Publication contract: rolling docs/data/energy-state-v2.json on main; revision + heartbeat dedupe.

const VERSION = 'EM2_PUBLISHER_V1.0.8';
const OWNER = 'OnsKasteeltje';
const REPO = 'homey-energy-manual';
const PATH = 'docs/data/energy-state-v2.json';
const BRANCH = 'main';
const HEARTBEAT_MS = 6 * 60 * 1000;

const ID = {
  publicState: 'b0d68d98-efdb-41e4-be72-3bd6bdcc19eb',
  state: '8e1efbb0-7999-494c-9429-7d274afacd79',
  token: '235cfe0f-5760-48b9-9349-a33be47d04d1',
  lastPublish: 'fc95dcad-55d5-4d21-be15-f565f0a9bac3',
  lastPublishedRevision: 'c10ea01b-3dfc-4e04-bb27-2a56dfc636cd',
  lastPublisherVersion: 'c8422ce3-093b-4781-ae20-67d2154c0a36',
  publisherStatus: '4a4c6e90-67b6-44a6-9172-00eb7eb9cf72',
  flowDiag: 'af2be122-eca0-43fd-a18f-b4d8082acbc9',
  diag: '9269873c-33d6-43a8-a6a7-c12dcf2e42d6',
  lastAttemptRevision: 'df11ce4f-e9e2-491c-8bd5-c3f41d62d507',
  publishDue: 'fb0e42b6-8199-479e-be4c-43be3eb6a0ad'
};

const parse = v => { try { return JSON.parse(String(v ?? '')); } catch { return null; } };
const n = v => Number.isFinite(Number(v)) ? Number(v) : null;
const isoMs = v => { const x = Date.parse(String(v || '')); return Number.isFinite(x) ? x : 0; };
const set = async (id, value) => Homey.logic.updateVariable({ id, variable: { value } });

const [pubV, stateV, tokenV, lastPubV, lastRevV] = await Promise.all([
  Homey.logic.getVariable({ id: ID.publicState }),
  Homey.logic.getVariable({ id: ID.state }),
  Homey.logic.getVariable({ id: ID.token }),
  Homey.logic.getVariable({ id: ID.lastPublish }),
  Homey.logic.getVariable({ id: ID.lastPublishedRevision })
]);

const pub = parse(pubV?.value);
const state = parse(stateV?.value);
const token = String(tokenV?.value || '').trim();
if (!pub || typeof pub !== 'object') {
  await Promise.allSettled([set(ID.flowDiag, 410), set(ID.diag, 410), set(ID.publisherStatus, 'ERROR_PUBLIC_STATE')]);
  throw new Error('Publisher v1.0.8: EM2_Public_State missing/invalid');
}

const rev = n(pub?.meta?.state_revision ?? pub?.state_revision ?? pub?.revision ?? pub?.sourceRevision);
if (rev === null) {
  await Promise.allSettled([set(ID.flowDiag, 411), set(ID.diag, 411), set(ID.publisherStatus, 'ERROR_REVISION')]);
  throw new Error('Publisher v1.0.8: Public State revision missing/invalid');
}

const stateRev = n(state?.revision ?? state?.state_revision ?? state?.sourceRevision);
if (stateRev !== null && stateRev !== rev) {
  await Promise.allSettled([set(ID.flowDiag, 412), set(ID.diag, 412), set(ID.lastAttemptRevision, rev), set(ID.publisherStatus, 'ERROR_REVISION_MISMATCH')]);
  throw new Error(`Publisher v1.0.8: revision mismatch public=${rev} state=${stateRev}`);
}
if (!token) {
  await Promise.allSettled([set(ID.flowDiag, 413), set(ID.diag, 413), set(ID.lastAttemptRevision, rev), set(ID.publisherStatus, 'ERROR_TOKEN')]);
  throw new Error('Publisher v1.0.8: GH_Status_Token missing');
}

const lastRev = n(lastRevV?.value);
const lastPublishMs = isoMs(lastPubV?.value);
const heartbeatDue = !lastPublishMs || (Date.now() - lastPublishMs >= HEARTBEAT_MS);
const revisionDue = lastRev !== rev;
if (!revisionDue && !heartbeatDue) {
  await Promise.allSettled([set(ID.flowDiag, 211), set(ID.diag, 211), set(ID.lastAttemptRevision, rev), set(ID.publisherStatus, 'SKIP_CURRENT'), set(ID.publishDue, false)]);
  return true;
}

const now = new Date().toISOString();
const payload = JSON.parse(JSON.stringify(pub));
payload.meta = payload.meta || {};
payload.meta.generated_at = now;
payload.meta.heartbeat_at = now;
payload.meta.publisher_version = VERSION;
payload.meta.state_revision = rev;
payload.meta.publish_reason = revisionDue ? 'REVISION_EVENT' : 'HEARTBEAT_EVENT';
payload.meta.min_publish_interval_sec = 300;

const headers = {
  'Authorization': `Bearer ${token}`,
  'Accept': 'application/vnd.github+json',
  'X-GitHub-Api-Version': '2022-11-28',
  'User-Agent': 'Homey-EM2-Publisher-v1.0.8',
  'Content-Type': 'application/json'
};
const url = `https://api.github.com/repos/${OWNER}/${REPO}/contents/${PATH}`;
async function getSha() {
  const r = await fetch(`${url}?ref=${BRANCH}`, { headers });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`Publisher GET ${r.status}: ${(await r.text()).slice(0,160)}`);
  return (await r.json()).sha || null;
}
async function put(sha) {
  const body = { message: 'chore: publish rolling energy state', content: Buffer.from(JSON.stringify(payload, null, 2) + '\n').toString('base64'), branch: BRANCH, ...(sha ? { sha } : {}) };
  return fetch(url, { method: 'PUT', headers, body: JSON.stringify(body) });
}

await Promise.allSettled([set(ID.lastAttemptRevision, rev), set(ID.publisherStatus, 'PUBLISHING')]);
let sha;
try { sha = await getSha(); }
catch (e) {
  await Promise.allSettled([set(ID.flowDiag, 421), set(ID.diag, 421), set(ID.publisherStatus, 'ERROR_GITHUB_GET')]);
  throw e;
}
let r = await put(sha);
if (!r.ok && (r.status === 409 || r.status === 422)) { sha = await getSha(); r = await put(sha); }
if (!r.ok) {
  const msg = (await r.text()).slice(0,160);
  await Promise.allSettled([set(ID.flowDiag, 422), set(ID.diag, 422), set(ID.publisherStatus, `ERROR_GITHUB_PUT_${r.status}`)]);
  throw new Error(`Publisher PUT ${r.status}: ${msg}`);
}

await Promise.allSettled([
  set(ID.flowDiag, 210),
  set(ID.diag, 210),
  set(ID.publisherStatus, 'OK'),
  set(ID.lastPublish, now),
  set(ID.lastPublishedRevision, rev),
  set(ID.lastPublisherVersion, VERSION),
  set(ID.publishDue, false)
]);
return true;
