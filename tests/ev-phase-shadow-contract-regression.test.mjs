import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const bridge=fs.readFileSync('src/homey/power-intent/pi-dynamic-planner-bridge-v1.4.0.phase-shadow.js','utf8');
const adapter=fs.readFileSync('src/homey/adapters/ev-power/ev-power-v0.1.11.phase-shadow.js','utf8');
const gate=fs.readFileSync('src/homey/validation/ev-power-adapter-gate-v0.2.12.phase-shadow.js','utf8');

test('bridge carries Pi phase policy only as shadow',()=>{
  assert.match(bridge,/EMS_PI_EV_PHASE_POLICY_V0\.1/);
  assert.match(bridge,/phasePolicy\.shadowOnly===true/);
  assert.match(bridge,/physicalPhaseOwner==='EASEE_EQUALIZER'/);
  assert.match(bridge,/EM2_EV_PHASE_EXECUTION_SHADOW_V0\.1/);
  assert.match(bridge,/deviceWrites:false/);
  assert.match(bridge,/controlWrites:false/);
});

test('bridge production current controller remains fixed 3P',()=>{
  assert.match(bridge,/const EV_W_PER_A=690/);
  assert.match(bridge,/currentA\*EV_W_PER_A/);
  assert.match(bridge,/production remains the proven fixed-3P controller below/);
  assert.doesNotMatch(bridge,/set_phase_mode/);
  assert.doesNotMatch(bridge,/setCapabilityValue\(/);
});

test('power intent carries phase shadow without replacing production target',()=>{
  assert.match(bridge,/target_W:valid\?evW:0/);
  assert.match(bridge,/phase_mode_shadow:/);
  assert.match(bridge,/phase_requested_A_shadow:/);
});

test('adapter validates phase shadow but performs no phase write',()=>{
  assert.match(adapter,/EM2_EV_POWER_ADAPTER_PHASE_SHADOW_V0\.1/);
  assert.match(adapter,/physicalPhaseOwner:'EASEE_EQUALIZER'/);
  assert.match(adapter,/phaseCommand:null/);
  assert.match(adapter,/physicalWrite:false/);
  assert.doesNotMatch(adapter,/set_phase_mode/);
});

test('gate exposes phase shadow validation as observability only',()=>{
  assert.match(gate,/phaseShadowErrors/);
  assert.match(gate,/observabilityOnly:true/);
  assert.match(gate,/doesNotAffectProductionGate:true/);
  assert.match(gate,/finalStatus:errors\.length\?'FAIL':'PASS'/);
});

test('phase shadow cannot create a second physical writer',()=>{
  for(const source of [bridge,adapter,gate]){
    assert.doesNotMatch(source,/commands\/set_phase_mode/);
    assert.doesNotMatch(source,/charger_set_phase_mode/);
  }
});
