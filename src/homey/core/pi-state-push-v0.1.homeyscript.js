// Homey Core public state -> Pi local runtime state transport v0.1
// Transport-only: no device reads, no physical writes, no planning decisions.
// Trigger this after EM2_Public_State changes.

const STATE_VAR_ID = 'b0d68d98-efdb-41e4-be72-3bd6bdcc19eb'; // EM2_Public_State
const TOKEN_VAR_ID = '33d0c297-0760-4fd1-810c-00ef4303974b'; // EM2_PI_State_Ingest_Token
const PI_STATE_URL = 'http://192.168.1.42:3100/state/energy';
const EXPECTED_SCHEMA = '2.12';
const EXPECTED_PUBLISHER_PREFIX = 'EM2_CORE_STATE_';

const [stateVar, tokenVar] = await Promise.all([
  Homey.logic.getVariable({ id: STATE_VAR_ID }),
  Homey.logic.getVariable({ id: TOKEN_VAR_ID }),
]);

if (!stateVar) throw new Error('PI_STATE_PUSH_STATE_VARIABLE_MISSING');
if (!tokenVar) throw new Error('PI_STATE_PUSH_TOKEN_VARIABLE_MISSING');

const token = String(tokenVar.value ?? '').trim();
if (!token) throw new Error('PI_STATE_PUSH_TOKEN_EMPTY');

let payload;
try {
  payload = JSON.parse(String(stateVar.value ?? ''));
} catch (_) {
  throw new Error('PI_STATE_PUSH_STATE_JSON_INVALID');
}

if (!payload || typeof payload !== 'object') throw new Error('PI_STATE_PUSH_STATE_INVALID');
if (payload?.meta?.schema_version !== EXPECTED_SCHEMA) throw new Error('PI_STATE_PUSH_SCHEMA_MISMATCH');
if (!String(payload?.meta?.publisher_version ?? '').startsWith(EXPECTED_PUBLISHER_PREFIX)) {
  throw new Error('PI_STATE_PUSH_PUBLISHER_MISMATCH');
}
if (!payload.grid || !payload.tesla || !payload.hot_water) throw new Error('PI_STATE_PUSH_REQUIRED_BLOCK_MISSING');

const response = await fetch(PI_STATE_URL, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
  body: JSON.stringify(payload),
});

let result = null;
try {
  result = await response.json();
} catch (_) {}

if (!response.ok) {
  throw new Error(`PI_STATE_PUSH_HTTP_${response.status}_${String(result?.reason ?? 'REJECTED')}`);
}
if (result?.stateWritten !== true) throw new Error('PI_STATE_PUSH_NOT_WRITTEN');

return true;
