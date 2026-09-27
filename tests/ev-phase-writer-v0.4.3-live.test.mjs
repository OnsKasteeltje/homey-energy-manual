import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const src=fs.readFileSync(
  'src/homey/actuators/ev-power/ev-power-v0.4.3.phase-writer-live.js',
  'utf8'
);

test('HomeyScript source compiles as an async function body',()=>{
  const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
  assert.doesNotThrow(()=>new AsyncFunction(src));
});

test('v0.4.3 remains the sole guarded live phase writer contract',()=>{
  assert.match(src,/EM2_EV_ACTUATOR_V0\.4\.3_PHASE_WRITER/);
  assert.match(src,/const PHASE_EXECUTION_ENABLED=true/);
  assert.match(src,/const canWrite=PHASE_EXECUTION_ENABLED&&liveEnabled/);
});

test('failed transition preserves captured original circuit limit for recovery',()=>{
  assert.match(src,/const recoveryOriginalA=num\(t\.originalCircuitA\)/);
  assert.match(src,/recoveryOriginalValid/);
  assert.match(src,/RECOVERING_CIRCUIT_CAP/);
  assert.match(src,/RESTORE_FAILED_TRANSITION_CIRCUIT_CAP/);
  assert.match(src,/await setCircuitA\(recoveryOriginalA\)/);
});

test('writer only clears original circuit limit after recovery confirmation',()=>{
  const restoreWrite=src.indexOf("await setCircuitA(recoveryOriginalA)");
  const recoveryComplete=src.indexOf("'CIRCUIT_RECOVERY_COMPLETE'");
  const clearOriginal=src.indexOf("originalCircuitA:null",restoreWrite);
  assert.ok(restoreWrite>=0);
  assert.ok(recoveryComplete>restoreWrite);
  assert.ok(clearOriginal>restoreWrite);
});

test('legacy orphaned cap is not silently adopted as baseline',()=>{
  assert.match(src,/circuitTargetA>EV_MAX_A/);
  assert.match(src,/ORPHAN_CIRCUIT_BASELINE_CONFIRMED/);
  assert.match(src,/CIRCUIT_RECOVERY_REQUIRES_KNOWN_BASELINE/);
  assert.doesNotMatch(src,/setCircuitA\(20\)/);
  assert.doesNotMatch(src,/recoveryOriginalA\s*=\s*20/);
});

test('phase mode changes during an unfinished transition still fail closed',()=>{
  assert.match(src,/PHASE_MODE_CHANGED_DURING_TRANSITION/);
  assert.match(src,/const failClosed=async reason/);
});

test('normal transition still restores captured original circuit limit',()=>{
  assert.match(src,/RESTORING_CIRCUIT_CAP/);
  assert.match(src,/const restoreA=Number\(t\.originalCircuitA\)/);
  assert.match(src,/await setCircuitA\(restoreA\)/);
});

test('native Homey actions still own session current and circuit writes',()=>{
  assert.match(src,/homey:device:\$\{CHARGER_ID\}:pauseCharging/);
  assert.match(src,/homey:device:\$\{CHARGER_ID\}:resumeCharging/);
  assert.match(src,/homey:device:\$\{CHARGER_ID\}:circuitCurrentControl/);
  assert.match(src,/homey:device:\$\{CHARGER_ID\}:setDynamicChargerCurrent/);
  assert.doesNotMatch(src,/setCapabilityValue\(/);
});
