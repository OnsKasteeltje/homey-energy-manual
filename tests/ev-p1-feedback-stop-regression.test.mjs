import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const src=fs.readFileSync(
  'src/homey/power-intent/pi-dynamic-planner-bridge-v1.3.2.p1-feedback-stopfix.js',
  'utf8'
);

test('P1 remains authoritative for realtime feedback',()=>{
  assert.match(src,/P1 is authoritative for realtime EV feedback/);
  assert.match(src,/const p1W=num\(cap\(p1,'measure_power'\)\)/);
});

test('Easee actual power is not required for realtime regulation',()=>{
  assert.doesNotMatch(src,/EV_ACTUAL_POWER_STALE/);
  assert.match(src,/realtime\.evActualW=null/);
  assert.match(src,/realtime\.evPowerAgeSec=null/);
});

test('fresh P1 remains required',()=>{
  assert.match(src,/P1_POWER_INVALID/);
  assert.match(src,/P1_POWER_STALE/);
});

test('controller uses previous realtime command as state',()=>{
  assert.match(src,/previousIntent\?\.policyProjection\?\.realtime\?\.candidateA/);
  assert.match(src,/previousRealtimeApplied && previousRealtimeA!==null/);
});

test('6A can stop to zero on material grid import',()=>{
  assert.match(
    src,
    /candidateA=currentA===MIN_A\?0:Math\.max\(MIN_A,currentA-1\)/
  );
});

test('controller still steps up only one amp',()=>{
  assert.match(src,/candidateA=currentA\+1/);
});

test('start from zero still requires complete temporary 6A threshold',()=>{
  assert.match(src,/p1W<=-\(MIN_A\*EV_W_PER_A\)/);
  assert.match(src,/candidateA=MIN_A/);
});

test('realtime controller remains bounded by envelope maxA',()=>{
  assert.match(src,/Math\.max\(0,Math\.min\(maxA,candidateA\)\)/);
});

test('bridge has no direct device write',()=>{
  assert.doesNotMatch(src,/setCapabilityValue/);
  assert.match(src,/deviceWrites:false/);
});

test('deadline guard remains after realtime controller',()=>{
  const realtime=src.indexOf('let candidateA=currentA');
  const deadline=src.indexOf('Executor-side hard deadline guard runs last');
  assert.ok(realtime>=0);
  assert.ok(deadline>realtime);
});
