import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const src=fs.readFileSync(
  'src/homey/actuators/ev-power/ev-power-v0.4.5.phase-writer-live.js',
  'utf8'
);

test('v0.4.5 HomeyScript compiles as one async function body',()=>{
  const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
  assert.doesNotThrow(()=>new AsyncFunction(src));
});

test('v0.4.5 removes inter-stage self retrigger completely',()=>{
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

test('same-phase paused opportunity resumes directly without circuit-cap transition',()=>{
  const start=src.indexOf('// If the EV is already safely paused on the requested confirmed phase');
  const end=src.indexOf('// If Easee already exposes the requested same-phase opportunity',start);
  const paused=src.slice(start,end);
  assert.match(paused,/ZERO_HOLD_RESUME_CURRENT_CONFIRM_TIMEOUT/);
  assert.match(paused,/RESUME_SAME_PHASE_PAUSED/);
  assert.match(paused,/SAME_PHASE_RESUMED/);
  assert.match(paused,/hw\.confirmedMode===control\.mode/);
  assert.doesNotMatch(paused,/previousWasZeroHold/);
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


test('same confirmed phase can never fall through to bounded phase transition',()=>{
  const kiss=src.indexOf('KISS invariant: same confirmed phase is never a phase transition');
  const bounded=src.indexOf('const originalCircuitA=hw.circuitTargetA;');
  assert.ok(kiss>=0);
  assert.ok(bounded>kiss);
  const block=src.slice(kiss,bounded);
  assert.match(block,/if\(hw\.confirmedMode===control\.mode\)/);
  assert.match(block,/await resumeSession\(\)/);
  assert.match(block,/await setCurrentA\(control\.requestedA\)/);
  assert.match(block,/SAME_PHASE_CURRENT_CONFIRM_TIMEOUT/);
  assert.match(block,/return true/);
  assert.doesNotMatch(block,/setPhaseMode\(/);
  assert.doesNotMatch(block,/setCircuitA\(/);
});


test('same-phase fallback ignores stale sessionEnabled false while charging',()=>{
  const kiss=src.indexOf('KISS invariant: same confirmed phase is never a phase transition');
  const bounded=src.indexOf('const originalCircuitA=hw.circuitTargetA;',kiss);
  const block=src.slice(kiss,bounded);
  assert.match(block,/hw\.chargeState==='plugged_in_paused'\|\|hw\.paused===true/);
  assert.doesNotMatch(block,/hw\.sessionEnabled!==true\|\|/);
});

test('same-phase current-confirm lag preserves a bounded existing target instead of pausing',()=>{
  const kiss=src.indexOf('KISS invariant: same confirmed phase is never a phase transition');
  const bounded=src.indexOf('const originalCircuitA=hw.circuitTargetA;',kiss);
  const block=src.slice(kiss,bounded);
  assert.match(block,/boundedExistingTarget/);
  assert.match(block,/hw\.chargerTargetA<=control\.requestedA/);
  assert.match(block,/SAME_PHASE_CURRENT_CONFIRM_TIMEOUT_PRESERVED/);
  assert.match(block,/PRESERVE_BOUNDED_SAME_PHASE_TARGET/);
});


test('v0.4.5 classifies refresh and phase retry authentication failures separately',()=>{
  assert.match(src,/EASEE_REFRESH/);
  assert.match(src,/EASEE_PHASE_COMMAND_RETRY/);
  assert.match(src,/EASEE_PHASE_OBSERVATION_RETRY/);
  assert.ok(src.includes("operation+'_HTTP_'+r.status"));
  assert.match(src,/terminalEaseeAuthCode/);
  assert.ok(src.includes('EASEE_REFRESH_HTTP_(400|401|403)'));
  assert.ok(src.includes('EASEE_PHASE_(COMMAND|OBSERVATION)_RETRY_HTTP_(401|403)'));
});

test('recovered primary 401 remains silent and retry is bounded to one refresh',()=>{
  const start=src.indexOf('const withEasee401RefreshRetry=async');
  const end=src.indexOf('const setPhaseMode=async',start);
  const block=src.slice(start,end);
  assert.match(block,/if\(err\?\.httpStatus!==401\)throw err/);
  assert.equal((block.match(/getAccessToken\(latestVars,true\)/g)||[]).length,1);
  assert.equal((block.match(/request\(access,'RETRY'\)/g)||[]).length,1);
  assert.doesNotMatch(block,/notifyEaseeAuthFailure/);
});

test('terminal Easee auth failure sends owner push with timeline fallback and no secret material',()=>{
  assert.match(src,/const notifyEaseeAuthFailure=async/);
  assert.match(src,/Homey\.users\.getUsers\(\)/);
  assert.match(src,/role\|\|'\'\)\.toLowerCase\(\)==='owner'/);
  assert.match(src,/homey:manager:mobile:push_text/);
  assert.match(src,/homey:manager:notifications:create_notification/);
  assert.match(src,/RUN_EASEE_TOKEN_BOOTSTRAP/);
  assert.match(src,/secretMaterialIncluded:false/);
  assert.doesNotMatch(src,/text:.*accessToken/);
  assert.doesNotMatch(src,/text:.*refreshToken/);
});

test('auth alerts deduplicate while the same failed incident remains active',()=>{
  assert.match(src,/previousStatus\?\.status==='FAILED'/);
  assert.match(src,/prior\?\.code===code/);
  assert.match(src,/deliveryAlreadySucceeded/);
  assert.match(src,/retryStillSuppressed/);
  assert.match(src,/AUTH_ALERT_RETRY_MS=15\*60\*1000/);
  assert.match(src,/attemptedAt/);
  assert.match(src,/deduped:true/);
});

test('auth notification is best effort and happens only after fail-safe recovery attempt',()=>{
  const safe=src.indexOf('const safeAbort=async');
  const pause=src.indexOf('hw=await pauseAndConfirm()',safe);
  const restore=src.indexOf('hw=await restoreCircuit(originalCircuitA)',pause);
  const notify=src.indexOf('notifyEaseeAuthFailure(finalReason,previous)',restore);
  const save=src.indexOf("await saveStatus(\n    'FAILED'",notify);
  assert.ok(safe>=0);
  assert.ok(pause>safe);
  assert.ok(restore>pause);
  assert.ok(notify>restore);
  assert.ok(save>notify);
});

test('v0.4.5 preserves in-flight and zero-hold state from v0.4.4 during upgrade',()=>{
  assert.match(src,/PREVIOUS_COMPAT_VERSION='EM2_EV_ACTUATOR_V0\.4\.4_PHASE_WRITER'/);
  assert.match(src,/\[VERSION,PREVIOUS_COMPAT_VERSION\]\.includes\(previous\?\.schema\)/);
});
