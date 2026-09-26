import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const src=fs.readFileSync('src/homey/actuators/ev-power/ev-power-v0.4.2.phase-writer-live.js','utf8');

test('v0.4.2 remains the sole guarded live phase writer',()=>{
  assert.match(src,/EM2_EV_ACTUATOR_V0\.4\.2_PHASE_WRITER/);
  assert.match(src,/const PHASE_EXECUTION_ENABLED=true/);
  assert.match(src,/const canWrite=PHASE_EXECUTION_ENABLED&&liveEnabled/);
});

test('active electrical telemetry confirms an already-running phase before settings readback can force a pause',()=>{
  assert.match(src,/measure_current\.p1/);
  assert.match(src,/measure_current\.p2/);
  assert.match(src,/measure_current\.p3/);
  assert.match(src,/activeElectricalPhases/);
  assert.match(src,/electricalMode/);
  assert.match(src,/let confirmedMode=electricalMode!=='UNKNOWN'\?electricalMode:homeyConfirmedMode/);
  assert.match(src,/ELECTRICAL_TELEMETRY/);
});

test('true phase transitions can confirm through Easee observation 38',()=>{
  assert.match(src,/const PHASE_OBSERVATION_ID=38/);
  assert.match(src,/state\/\$\{encodeURIComponent\(CHARGER_SERIAL\)\}\/observations\?ids=\$\{PHASE_OBSERVATION_ID\}/);
  assert.match(src,/EASEE_CLOUD_OBSERVATION_38/);
  assert.match(src,/PHASE_CLOUD_CONFIRM_INTERVAL_MS=5000/);
});

test('phase confirmation is latched across paused transition stages',()=>{
  assert.match(src,/phaseConfirmedMode/);
  assert.match(src,/phaseConfirmedAt/);
  assert.match(src,/phaseConfirmationSource/);
  assert.match(src,/t\.phaseConfirmedMode===desiredMode/);
});

test('cloud confirmation is only consulted on safe paused phase-transition stages',()=>{
  assert.match(src,/const cloudConfirmStage=\['CONFIRMING_PHASE','DEADTIME','ARMING_CIRCUIT_CAP'\]\.includes\(t\.stage\)/);
  assert.match(src,/paused &&\s*cloudConfirmStage/);
});

test('same-phase current semantics remain unchanged',()=>{
  assert.match(src,/if\(desiredA<t\.requestedA\)/);
  assert.match(src,/transitionA=desiredA/);
  assert.match(src,/transitionA=t\.requestedA/);
  assert.match(src,/if\(desiredA!==transitionA\)await scheduleNext\(500\)/);
});

test('phase mode changes during a transition still fail closed',()=>{
  assert.match(src,/PHASE_MODE_CHANGED_DURING_TRANSITION/);
  assert.match(src,/const failClosed=async reason/);
});

test('native Homey actions still own session current and circuit writes',()=>{
  assert.match(src,/homey:device:\$\{CHARGER_ID\}:pauseCharging/);
  assert.match(src,/homey:device:\$\{CHARGER_ID\}:resumeCharging/);
  assert.match(src,/homey:device:\$\{CHARGER_ID\}:circuitCurrentControl/);
  assert.match(src,/homey:device:\$\{CHARGER_ID\}:setDynamicChargerCurrent/);
  assert.doesNotMatch(src,/setCapabilityValue\(/);
});
