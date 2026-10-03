import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

import {
  classifyQuookerSample,
  CONFIG,
  SCHEMA,
} from '../../apps/homey/observability/quooker/quooker-detector-v0.5.mjs';

const idle=(l1,l2,l3)=>({
  schema:SCHEMA,
  active:false,
  status:'ON_IDLE',
  baselineL1W:l1,
  baselineL2W:l2,
  baselineL3W:l3,
  heatingStartedAtMs:null,
});

test('2026-10-03 13:17 regression: EV restart moves all phases ~+1.6 kW and is rejected',()=>{
  // Reconstructed signature from the observed event; these are not claimed as exact raw samples.
  const s=classifyQuookerSample(
    {switchOn:true,l1W:1720,l2W:1680,l3W:360,nowMs:1000},
    idle(120,80,-1240),
  );
  assert.equal(s.deltaL1W,1600);
  assert.equal(s.deltaL2W,1600);
  assert.equal(s.deltaL3W,1600);
  assert.equal(s.active,false);
  assert.equal(s.status,'ON_IDLE');
  assert.equal(s.reason,'REJECT_SIDE_PHASE_MOVEMENT');
});

test('2026-10-03 13:24 regression: short isolated ~+1.64 kW L3 step is Quooker',()=>{
  // Reconstructed signature from the observed event; L1/L2 remain effectively stable.
  const s=classifyQuookerSample(
    {switchOn:true,l1W:145,l2W:95,l3W:410,nowMs:2000},
    idle(120,80,-1230),
  );
  assert.equal(s.deltaL1W,25);
  assert.equal(s.deltaL2W,15);
  assert.equal(s.deltaL3W,1640);
  assert.equal(s.active,true);
  assert.equal(s.status,'HEATING');
  assert.equal(s.powerW,1640);
  assert.equal(s.reason,'HEATING_START_ISOLATED_L3');
});

test('heating latch is forcibly released at 90 seconds',()=>{
  const previous={
    active:true,
    status:'HEATING',
    baselineL1W:100,
    baselineL2W:100,
    baselineL3W:-1200,
    heatingStartedAtMs:1000,
  };
  const s=classifyQuookerSample(
    {switchOn:true,l1W:110,l2W:90,l3W:400,nowMs:1000+CONFIG.maxHeatingMs},
    previous,
  );
  assert.equal(s.active,false);
  assert.equal(s.status,'ON_IDLE');
  assert.equal(s.reason,'HEATING_MAX_DURATION_FAILSAFE');
  assert.equal(s.baselineL3W,400);
});

test('switch OFF remains authoritative',()=>{
  const s=classifyQuookerSample(
    {switchOn:false,l1W:1700,l2W:1700,l3W:400,nowMs:3000},
    {active:true,status:'HEATING',baselineL1W:100,baselineL2W:100,baselineL3W:-1200,heatingStartedAtMs:2000},
  );
  assert.equal(s.status,'OFF');
  assert.equal(s.active,false);
});

test('cold/migration start initializes three-phase baseline instead of detecting',()=>{
  const s=classifyQuookerSample(
    {switchOn:true,l1W:100,l2W:100,l3W:400,nowMs:1},
    {baselineL3W:-1200},
  );
  assert.equal(s.active,false);
  assert.equal(s.reason,'BASELINE_INITIALIZED');
  assert.equal(s.baselineL1W,100);
  assert.equal(s.baselineL2W,100);
  assert.equal(s.baselineL3W,400);
});

const runtime=fs.readFileSync(
  'apps/homey/observability/quooker/quooker-detector-v0.5.live-homey.js',
  'utf8',
);

test('runtime parses as HomeyScript JavaScript',()=>{
  assert.doesNotThrow(()=>new Function('Homey', `return (async()=>{\n${runtime}\n})();`));
});

test('runtime remains observe-only and contains no physical device write',()=>{
  assert.doesNotMatch(runtime,/setCapabilityValue\s*\(/);
  assert.doesNotMatch(runtime,/runFlowCardAction\s*\(/);
  assert.match(runtime,/physicalWritePerformed:false/);
  assert.match(runtime,/observeOnly:true/);
});

test('runtime uses fixed targeted Logic IDs and no broad Logic scan',()=>{
  assert.doesNotMatch(runtime,/getVariables\s*\(/);
  assert.match(runtime,/Homey\.logic\.getVariable\(\{id\}\)/);
  assert.match(runtime,/fbd409dd-1813-4d1d-b095-48c5eead2eaa/);
  assert.match(runtime,/23bfb36f-d883-47ca-a932-c98b1d8c074e/);
});

test('runtime contains three-phase isolation and 90 second failsafe',()=>{
  assert.match(runtime,/SIDE_MAX_W=350/);
  assert.match(runtime,/MAX_HEATING_MS=90000/);
  assert.match(runtime,/REJECT_SIDE_PHASE_MOVEMENT/);
  assert.match(runtime,/HEATING_MAX_DURATION_FAILSAFE/);
});
