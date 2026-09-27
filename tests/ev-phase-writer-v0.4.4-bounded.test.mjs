import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const src=fs.readFileSync(
  'src/homey/actuators/ev-power/ev-power-v0.4.4.phase-writer-live.js',
  'utf8'
);

test('v0.4.4 HomeyScript compiles as one async function body',()=>{
  const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
  assert.doesNotThrow(()=>new AsyncFunction(src));
});

test('v0.4.4 removes inter-stage self retrigger completely',()=>{
  assert.doesNotMatch(src,/triggerAdvancedFlow/);
  assert.doesNotMatch(src,/scheduleNext/);
  assert.match(src,/BOUNDED_TRANSITION_START/);
  assert.match(src,/BOUNDED_TRANSITION_COMPLETE/);
  assert.match(src,/selfRetriggerUsed:false/);
});

test('bounded writer uses HomeyScript native wait and never setTimeout',()=>{
  assert.match(src,/const sleep=ms=>wait\(ms\)/);
  assert.doesNotMatch(src,/setTimeout\s*\(/);
});

test('bounded transition keeps all physical safety stages in one invocation',()=>{
  const pause=src.indexOf('hw=await pauseAndConfirm()');
  const phase=src.indexOf('await setPhaseMode(control.mode,vars)');
  const deadtime=src.indexOf('await sleep(DEADTIME_MS)');
  const cap=src.indexOf('await setCircuitA(control.requestedA)');
  const resume=src.indexOf('await resumeSession()');
  const current=src.indexOf('await setCurrentA(control.requestedA)',resume);
  const restore=src.indexOf('hw=await restoreCircuit(originalCircuitA)',current);
  assert.ok(pause>=0);
  assert.ok(phase>pause);
  assert.ok(deadtime>phase);
  assert.ok(cap>deadtime);
  assert.ok(resume>cap);
  assert.ok(current>resume);
  assert.ok(restore>current);
});

test('writer re-reads authoritative control while safely paused',()=>{
  assert.match(src,/MAX_REPLANS_WHILE_PAUSED=3/);
  assert.match(src,/const afterDeadtime=await readControl\(\)/);
  assert.match(src,/const beforeResume=await readControl\(\)/);
  assert.match(src,/MODE_UNSTABLE_DURING_TRANSITION/);
});

test('writer confirms Easee opportunity settings without requiring Tesla consumption',()=>{
  assert.match(src,/PAUSE_CONFIRM_TIMEOUT/);
  assert.match(src,/PHASE_CONFIRM_TIMEOUT/);
  assert.match(src,/TRANSITION_CIRCUIT_CAP_CONFIRM_TIMEOUT/);
  assert.match(src,/CURRENT_TARGET_CONFIRM_TIMEOUT/);
  assert.match(src,/CIRCUIT_RESTORE_TIMEOUT/);
  assert.match(src,/teslaConsumptionRequired:false/);
  assert.match(src,/OPPORTUNITY_CURRENT_CONFIRMED/);
  assert.doesNotMatch(src,/CHARGING_CONFIRM_TIMEOUT_MS/);
  assert.doesNotMatch(src,/CHARGING_PHASE_CONFIRM_TIMEOUT/);
  assert.doesNotMatch(src,/RESUME_CONFIRM_TIMEOUT/);
  assert.doesNotMatch(src,/x\.powerW!==null && x\.powerW>500/);
});

test('zero Tesla draw is explicitly a healthy armed opportunity',()=>{
  assert.match(src,/OPPORTUNITY_ARMED/);
  assert.match(src,/Tesla draw is\s*\/\/ irrelevant|Tesla draw is/);
  assert.match(src,/Tesla decides whether to\s*\/\/ consume it|Tesla decides whether to consume it/);
  assert.match(src,/teslaConsumptionObserved/);
});

test('all failure exits restore the captured circuit baseline through safeAbort',()=>{
  assert.match(src,/const safeAbort=async/);
  assert.match(src,/hw=await pauseAndConfirm\(\)/);
  assert.match(src,/hw=await restoreCircuit\(originalCircuitA\)/);
  assert.match(src,/PAUSE_AND_RESTORE/);
});

test('concurrent gate triggers cannot start a second bounded transaction',()=>{
  assert.match(src,/RUN_LOCK_MS=35000/);
  assert.match(src,/previous\?\.status==='RUNNING'/);
  assert.match(src,/age\(previous\?\.at\)<RUN_LOCK_MS/);
});

test('stable same-phase opportunity does not depend on active charging',()=>{
  assert.match(src,/hw\.confirmedMode===control\.mode/);
  assert.match(src,/hw\.sessionEnabled===true/);
  assert.match(src,/hw\.chargerTargetA===control\.requestedA/);
  assert.match(src,/OPPORTUNITY_ARMED/);
  assert.match(src,/OPPORTUNITY_CURRENT_ADJUST/);
});

test('native Homey cards remain the only session/current/circuit writers',()=>{
  assert.match(src,/pauseCharging/);
  assert.match(src,/resumeCharging/);
  assert.match(src,/circuitCurrentControl/);
  assert.match(src,/setDynamicChargerCurrent/);
  assert.doesNotMatch(src,/setCapabilityValue\(/);
});
