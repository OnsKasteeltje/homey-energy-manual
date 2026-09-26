import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const bridge=fs.readFileSync('src/homey/power-intent/pi-dynamic-planner-bridge-v1.4.4.pause-aware-phase-shadow.js','utf8');
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
  assert.match(bridge,/evW=candidateA\*EV_W_PER_A/);
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


test('bridge cuts large grid import proportionally instead of one amp per cycle',()=>{
  assert.match(bridge,/excessImportW=Math\.max\(0,p1W-P1_DOWN_THRESHOLD_W\)/);
  assert.match(bridge,/Math\.ceil\(excessImportW\/EV_W_PER_A\)/);
  assert.match(bridge,/candidateA=reducedA>=MIN_A\?reducedA:0/);
  assert.match(bridge,/REALTIME_P1_IMPORT_PROPORTIONAL_DOWN/);
});

test('bridge keeps upward PV capture bounded to one amp per cycle',()=>{
  assert.match(bridge,/candidateA=currentA\+1/);
});


test('phase shadow reconstructs active EV load from confirmed Easee phase readback',()=>{
  assert.match(bridge,/confirmedPhaseMode=normalizePhaseMode\(confirmedPhaseRaw\)/);
  assert.match(bridge,/actualProductionPhaseCount=currentA<=0/);
  assert.match(bridge,/confirmedPhaseMode==='1P'/);
  assert.match(bridge,/confirmedPhaseMode==='3P'/);
  assert.match(bridge,/currentA\*230\*\(actualProductionPhaseCount\|\|0\)/);
});

test('unconfirmed active phase readback fails phase shadow closed only',()=>{
  assert.match(bridge,/PHASE_READBACK_UNCONFIRMED/);
  assert.match(bridge,/phaseReadbackValid=currentA===0\|\|actualProductionPhaseCount===1\|\|actualProductionPhaseCount===3/);
  assert.match(bridge,/production remains the proven fixed-3P controller below/);
});


test('phase readback is observability even when Pi realtime envelope is disabled',()=>{
  const obsIndex=bridge.indexOf('let easeeObs=null');
  const envIndex=bridge.indexOf('const envValid=');
  assert.ok(obsIndex>=0 && envIndex>=0 && obsIndex<envIndex);
  assert.match(bridge,/confirmedPhaseRaw=phaseRawObs/);
  assert.match(bridge,/confirmedPhaseMode=normalizePhaseMode\(phaseRawObs\)/);
});


test('paused session contributes zero physical EV addback to phase shadow',()=>{
  assert.match(bridge,/chargeState==='plugged_in_charging'\s*\?currentA\s*:0/);
  assert.match(bridge,/actualProductionA:phaseShadowPhysicalA/);
  assert.match(bridge,/controllerStateA:currentA/);
  assert.match(bridge,/phaseShadowPhysicalA\*230\*\(actualProductionPhaseCount\|\|0\)/);
});

test('production current loop still uses controller current state independently',()=>{
  assert.match(bridge,/let candidateA=currentA/);
  assert.match(bridge,/evW=candidateA\*EV_W_PER_A/);
});
