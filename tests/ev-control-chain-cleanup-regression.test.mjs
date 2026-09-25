import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const adapter=fs.readFileSync('src/homey/adapters/ev-power/ev-power-v0.1.10.control-pure.js','utf8');
const gate=fs.readFileSync('src/homey/validation/ev-power-adapter-gate-v0.2.11.control-contract.js','utf8');
const bridge=fs.readFileSync('src/homey/power-intent/pi-dynamic-planner-bridge-v1.3.2.p1-feedback-stopfix.js','utf8');

test('golden path keeps P1 authoritative',()=>{
  assert.match(bridge,/P1 is authoritative for realtime EV feedback/);
  assert.doesNotMatch(bridge,/EV_ACTUAL_POWER_STALE/);
});

test('adapter never vetoes on Core or Easee chargeState',()=>{
  assert.match(adapter,/chargeStateObservabilityOnly:true/);
  assert.doesNotMatch(adapter,/CHARGER_UNAVAILABLE/);
  assert.doesNotMatch(adapter,/!chargerAvailable/);
  assert.doesNotMatch(adapter,/cs\.includes\('offline'\)/);
});

test('adapter still fails closed on stale intent and invalid control contract',()=>{
  assert.match(adapter,/STALE_INTENT/);
  assert.match(adapter,/SEMANTIC_TOKEN_OR_SCHEMA_MISMATCH/);
  assert.match(adapter,/neverIncreaseUpstreamPower:true/);
});

test('gate validates contract but not Core or Easee chargeState',()=>{
  assert.match(gate,/coreStateObservabilityOnly:true/);
  assert.doesNotMatch(gate,/coreSafety:/);
  assert.doesNotMatch(gate,/coreStateSafe/);
  assert.doesNotMatch(gate,/cs\.includes\('offline'\)/);
});

test('gate still validates electrical mapping, command range and translation',()=>{
  assert.match(gate,/electrical:electricalOK/);
  assert.match(gate,/commandRange:commandRangeOK/);
  assert.match(gate,/translation:/);
  assert.match(gate,/controlRevisionAligned:/);
});

test('device health remains observability-only at gate boundary',()=>{
  assert.match(gate,/deviceHealth:\{observabilityOnly:true/);
});
