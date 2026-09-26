import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const src=fs.readFileSync('src/homey/actuators/ev-power/ev-power-v0.3.0.phase-candidate.js','utf8');

test('candidate is hard disabled for physical phase execution',()=>{
  assert.match(src,/const PHASE_EXECUTION_ENABLED=false/);
  assert.match(src,/physicalWriteAllowed:false/);
  assert.match(src,/physicalWritePerformed:false/);
});

test('candidate contains no physical write primitive',()=>{
  assert.doesNotMatch(src,/setCapabilityValue\(/);
  assert.doesNotMatch(src,/runFlowCardAction\(/);
  assert.doesNotMatch(src,/fetch\(/);
  assert.doesNotMatch(src,/commands\/set_phase_mode/);
});

test('candidate consumes validated phase chain',()=>{
  assert.match(src,/EM2_EV_POWER_ADAPTER_PHASE_SHADOW_V0\.1/);
  assert.match(src,/gatePhase\?\.status==='PASS'/);
  assert.match(src,/doesNotAffectProductionGate===true/);
  assert.match(src,/PHASE_SHADOW_CANDIDATE/);
});

test('deadline remains forced to 3P',()=>{
  assert.match(src,/NUMERIC_DEADLINE_TARGET/);
  assert.match(src,/REMAINING_KWH_OVER_TIME_TO_DEADLINE/);
  assert.match(src,/desiredMode='3P'/);
  assert.match(src,/DEADLINE_FORCE_3P/);
});

test('candidate reads live Homey Easee state and phase readback',()=>{
  assert.match(src,/evcharger_charging_state/);
  assert.match(src,/target_charger_current/);
  assert.match(src,/target_circuit_current/);
  assert.match(src,/measure_current\.offered/);
  assert.match(src,/measure_power/);
  assert.match(src,/getDeviceSettingsObj/);
  assert.match(src,/phaseMode/);
});

test('paused same-phase resume first requires circuit safety cap',()=>{
  assert.match(src,/nextAction='SET_TRANSITION_CIRCUIT_CAP'/);
  assert.match(src,/PAUSED_RESUME_REQUIRES_SAFETY_CAP/);
});

test('phase mismatch requires pause before phase command',()=>{
  assert.match(src,/nextAction=paused\?'SET_PHASE_MODE':'PAUSE_SESSION'/);
  assert.match(src,/PAUSE_CONFIRMED_PHASE_CHANGE_REQUIRED/);
});

test('candidate persists only observability state',()=>{
  assert.match(src,/status:'PHASE_CANDIDATE'/);
  assert.match(src,/Homey\.logic\.updateVariable/);
  assert.doesNotMatch(src,/Homey\.devices\.setCapabilityValue/);
});
