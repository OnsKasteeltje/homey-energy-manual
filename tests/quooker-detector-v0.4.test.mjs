import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

import {
  classifyQuookerSample,
  CONFIG,
  SCHEMA,
} from '../src/homey/observability/quooker/quooker-detector-v0.4.mjs';

const runtime=fs.readFileSync(
  'src/homey/observability/quooker/quooker-detector-v0.4.live-homey.js',
  'utf8',
);

test('today replay: OFF baseline then +1636 W L3 step becomes HEATING',()=>{
  let s=classifyQuookerSample(
    {switchOn:false,l3W:-1290},
    {},
  );
  assert.equal(s.status,'OFF');
  assert.equal(s.baselineL3W,-1290);

  s=classifyQuookerSample(
    {switchOn:true,l3W:-1290},
    s,
  );
  assert.equal(s.status,'ON_IDLE');
  assert.equal(s.baselineL3W,-1290);

  s=classifyQuookerSample(
    {switchOn:true,l3W:346},
    s,
  );
  assert.equal(s.schema,SCHEMA);
  assert.equal(s.status,'HEATING');
  assert.equal(s.active,true);
  assert.equal(s.powerW,1636);
  assert.equal(s.baselineL3W,-1290);
});

test('today replay: falling back to background ends heating and resets baseline',()=>{
  const previous={
    baselineL3W:-1290,
    active:true,
    status:'HEATING',
  };
  const s=classifyQuookerSample(
    {switchOn:true,l3W:-1636},
    previous,
  );
  assert.equal(s.status,'ON_IDLE');
  assert.equal(s.active,false);
  assert.equal(s.powerW,0);
  assert.equal(s.baselineL3W,-1636);
  assert.equal(s.reason,'HEATING_STOP_BASELINE_RESET');
});

test('short thermostat top-up is detected against updated ON-idle background',()=>{
  const idle={
    baselineL3W:-1650,
    active:false,
    status:'ON_IDLE',
  };
  const heat=classifyQuookerSample(
    {switchOn:true,l3W:-53},
    idle,
  );
  assert.equal(heat.status,'HEATING');
  assert.equal(heat.powerW,1597);
});

test('switch OFF is authoritative even with heating-sized L3 delta',()=>{
  const s=classifyQuookerSample(
    {switchOn:false,l3W:400},
    {baselineL3W:-1200,active:true,status:'HEATING'},
  );
  assert.equal(s.status,'OFF');
  assert.equal(s.active,false);
  assert.equal(s.powerW,0);
  assert.equal(s.baselineL3W,400);
});

test('ON-idle baseline follows PV/background when no heating signature exists',()=>{
  const s=classifyQuookerSample(
    {switchOn:true,l3W:-1800},
    {baselineL3W:-1200,active:false,status:'ON_IDLE'},
  );
  assert.equal(s.status,'ON_IDLE');
  assert.equal(s.baselineL3W,-1800);
});

test('heating hysteresis holds a pulse down to hold threshold',()=>{
  const s=classifyQuookerSample(
    {switchOn:true,l3W:10},
    {baselineL3W:-1290,active:true,status:'HEATING'},
  );
  assert.equal(10-(-1290),1300);
  assert.ok(1300>=CONFIG.holdMinW);
  assert.equal(s.status,'HEATING');
  assert.equal(s.powerW,1300);
});

test('runtime parses as HomeyScript JavaScript',()=>{
  assert.doesNotThrow(()=>{
    new Function('Homey', `return (async()=>{\n${runtime}\n})();`);
  });
});

test('runtime is observe-only and contains no physical device write',()=>{
  assert.doesNotMatch(runtime,/setCapabilityValue\s*\(/);
  assert.doesNotMatch(runtime,/runFlowCardAction\s*\(/);
  assert.match(runtime,/physicalWritePerformed:false/);
  assert.match(runtime,/observeOnly:true/);
});

test('runtime samples P1 continuously while Cooker is ON and sparsely while OFF',()=>{
  assert.match(runtime,/const needP1=cookerOn \|\| switchChanged/);
  assert.match(runtime,/OFF_P1_REFRESH_MS=55000/);
});

test('runtime keeps legacy EM_Quooker public contract for Core',()=>{
  for(const name of [
    'EM_Quooker_Switch_On',
    'EM_Quooker_Active',
    'EM_Quooker_Power_W',
    'EM_Quooker_Status',
    'EM_Quooker_Last_Sample',
    'EM_Quooker_Baseline_L3_W',
    'EM_Quooker_Last_Transition',
    'EM_Quooker_Transition_History',
    'EM_Quooker_Last_Heating_At',
    'EM_Quooker_Last_Heating_Power_W',
    'EM_Quooker_Diagnostic',
  ]){
    assert.match(runtime,new RegExp(name));
  }
});
