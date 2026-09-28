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
  // Scope ordering assertions to the bounded-transition transaction itself.
  // OFF zero-amp recovery legitimately contains an earlier resumeSession().
  const bounded=src.indexOf("const startedAt=iso();");
  const pause=src.indexOf('hw=await pauseAndConfirm()',bounded);
  const phase=src.indexOf('await setPhaseMode(control.mode,vars)',pause);
  const deadtime=src.indexOf('await sleep(DEADTIME_MS)',phase);
  const cap=src.indexOf('await setCircuitA(control.requestedA)',deadtime);
  const resume=src.indexOf('await resumeSession()',cap);
  const current=src.indexOf('await setCurrentA(control.requestedA)',resume);
  const restore=src.indexOf('hw=await restoreCircuit(originalCircuitA)',current);
  assert.ok(bounded>=0);
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


test('Easee phase/cloud auth retries exactly once after HTTP 401',()=>{
  assert.match(src,/const withEasee401RefreshRetry=async/);
  assert.match(src,/if\(err\?\.httpStatus!==401\)throw err/);
  assert.match(src,/const latestVars=await readEaseeVars\(\)/);
  assert.match(src,/getAccessToken\(latestVars,true\)/);
  assert.match(src,/setPhaseMode=async/);
  assert.match(src,/readCloudPhaseMode=async/);
});

test('Easee HTTP errors preserve status for bounded auth recovery',()=>{
  const matches=src.match(/err\.httpStatus=r\.status/g)||[];
  assert.ok(matches.length>=2);
});

test('pause timeout gets one final hardware read before fail-closed',()=>{
  const start=src.indexOf('FINAL_PAUSE_READ_AFTER_TIMEOUT');
  const wait=src.indexOf("waitHardware(x=>x.paused,PAUSE_TIMEOUT_MS,'PAUSE_CONFIRM_TIMEOUT')",start);
  const catchTimeout=src.indexOf("String(err?.message||err)!=='PAUSE_CONFIRM_TIMEOUT'",wait);
  const finalRead=src.indexOf('hw=await readHardware()',catchTimeout);
  const accept=src.indexOf('if(hw.paused)return hw',finalRead);
  const rethrow=src.indexOf('throw err',accept);
  assert.ok(start>=0);
  assert.ok(wait>start);
  assert.ok(catchTimeout>wait);
  assert.ok(finalRead>catchTimeout);
  assert.ok(accept>finalRead);
  assert.ok(rethrow>accept);
});


test('normal OFF holds zero amps without pausing the EV session',()=>{
  const start=src.indexOf("if(control.mode==='OFF'){");
  const end=src.indexOf('// If Easee already exposes',start);
  const off=src.slice(start,end);
  assert.match(src,/NORMAL_OFF_ZERO_A_HOLD/);
  assert.match(off,/setCurrentA\(0\)/);
  assert.match(off,/OFF_ZERO_A_HOLD/);
  assert.doesNotMatch(off,/pauseAndConfirm\(/);
  assert.doesNotMatch(off,/pauseSession\(/);
});

test('legacy plugged-in pause is recovered once and hold readback ignores Homey onoff',()=>{
  const start=src.indexOf('NORMAL_OFF_ZERO_A_HOLD');
  const end=src.indexOf('// If Easee already exposes',start);
  const off=src.slice(start,end);
  assert.match(off,/previousWasZeroHold/);
  assert.match(off,/recoverLegacyPause/);
  assert.match(off,/hw\.chargeState==='plugged_in_paused'/);
  assert.match(off,/await resumeSession\(\)/);
  assert.match(off,/OFF_ZERO_CURRENT_CONFIRM_TIMEOUT/);
  assert.match(off,/x\.chargerTargetA===0/);
  assert.match(off,/x\.offeredA!==null && x\.offeredA<=1/);
  assert.match(off,/x\.powerW!==null && x\.powerW<=250/);
  assert.doesNotMatch(off,/x=>x\.sessionEnabled===true&&x\.chargerTargetA===0/);
});

test('same-phase opportunity resumes directly from zero-amp hold',()=>{
  assert.match(src,/ZERO_HOLD_RESUME_CURRENT_CONFIRM_TIMEOUT/);
  assert.match(src,/RESUME_FROM_ZERO_HOLD/);
  assert.match(src,/ZERO_HOLD_RESUMED/);
  assert.match(src,/previousWasZeroHold &&/);
});


test('startup recovery accepts only a safely paused live normal circuit baseline over stale saved normal baseline',()=>{
  assert.match(src,/startupRecoveryBaselineReconciled=false/);
  assert.match(src,/hw\.paused===true/);
  assert.match(src,/previousOriginal>EV_MAX_A/);
  assert.match(src,/hw\.circuitTargetA>EV_MAX_A/);
  assert.match(src,/previousNormalCircuitBaseline/);
  assert.match(src,/liveNormalCircuitBaseline/);
  assert.match(src,/statusExtra:\{startupRecoveryBaselineReconciled\}/);
});
