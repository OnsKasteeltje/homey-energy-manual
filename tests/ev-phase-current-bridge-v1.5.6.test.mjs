import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const bridge=fs.readFileSync(
  'src/homey/power-intent/pi-dynamic-planner-bridge-v1.5.6.phase-aware-upscale.js',
  'utf8',
);

test('full HomeyScript candidate parses as async JavaScript',()=>{
  assert.doesNotThrow(()=>{
    new Function('Homey', `return (async()=>{\n${bridge}\n})();`);
  });
});

test('v1.5.6 carries the deployed production identity',()=>{
  assert.match(bridge,/PI_DYNAMIC_PLANNER_BRIDGE_V1\.5\.6_PHASE_CURRENT/);
  assert.match(bridge,/stable Bridge flow 8bf53fdb-76f4-47db-8ccb-773ac515f06e/);
});

test('legacy parallel candidateA current loop is removed',()=>{
  assert.doesNotMatch(bridge,/let candidateA=/);
  assert.doesNotMatch(bridge,/candidateA=currentA\+1/);
  assert.doesNotMatch(bridge,/P1_UP_THRESHOLD_W/);
  assert.doesNotMatch(bridge,/let phaseA=/);
});

test('one phase-aware current regulator produces requestedA',()=>{
  assert.match(bridge,/let requestedA=0/);
  assert.match(bridge,/const wpa=evpcWPerA\(phaseMode\)/);
  assert.match(bridge,/currentReason='FAST_IMPORT_DOWN'/);
  assert.match(bridge,/currentReason='SLOW_PLUS_1A'/);
  assert.match(bridge,/requestedW=requestedA\*evpcWPerA\(phaseMode\)/);
});

test('current regulation is phase aware and prefers up to 200 W import over unused PV',()=>{
  assert.match(bridge,/const evpcWPerA=mode=>mode==='1P'\?230:mode==='3P'\?690:0/);
  assert.match(bridge,/EVPC_IMPORT_DEADBAND_W=250/);
  assert.match(bridge,/EVPC_UPSCALE_CONFIRM_1P_MS=20000/);
  assert.match(bridge,/EVPC_UPSCALE_CONFIRM_3P_MS=30000/);
  assert.match(bridge,/const upscaleConfirmMs=phaseMode==='1P'\?EVPC_UPSCALE_CONFIRM_1P_MS:EVPC_UPSCALE_CONFIRM_3P_MS/);
  assert.match(bridge,/EVPC_UPSCALE_IMPORT_TARGET_W=200/);
  assert.match(bridge,/syntheticP1W\+wpa<=EVPC_UPSCALE_IMPORT_TARGET_W/);
  assert.match(bridge,/upscaleImportTargetW:EVPC_UPSCALE_IMPORT_TARGET_W/);
});

test('unknown modeSince is dwell-ready and is not synthesized as a stop timestamp',()=>{
  assert.match(bridge,/const previousModeSinceMs=Number\.isFinite\(previousSinceParsed\)[\s\S]*\?previousSinceParsed[\s\S]*:null/);
  assert.match(bridge,/!Number\.isFinite\(previousModeSinceMs\)\|\|[\s\S]*EVPC_UPWARD_DWELL_MS/);
  assert.match(bridge,/const modeSinceAt=phaseChanged[\s\S]*\?new Date\(sampleMs\)\.toISOString\(\)[\s\S]*:\(previousPhase\?\.modeSinceAt\|\|null\)/);
});

test('phase selector uses sustained rolling signal and asymmetric dwell',()=>{
  assert.match(bridge,/EVPC_ROLLING_WINDOW_MS=120000/);
  assert.match(bridge,/EVPC_ROLLING_MIN_COVERAGE_MS=90000/);
  assert.match(bridge,/EVPC_UPWARD_DWELL_MS=300000/);
  assert.match(bridge,/3P_TO_1P_ROLLING_LOW/);
  assert.match(bridge,/1P_TO_OFF_ROLLING_LOW/);
  assert.match(bridge,/1P_TO_3P_ROLLING_HIGH/);
});

test('upward entry requires instantaneous 6A viability',()=>{
  assert.match(bridge,/evpcCanSustainMin\('3P',availableTotalW\)/);
  assert.match(bridge,/evpcCanSustainMin\('1P',availableTotalW\)/);
});

test('same-phase current change is explicitly not a physical phase transition',()=>{
  assert.match(bridge,/currentOnlyChange:currentChanged&&!phaseChanged/);
  assert.match(bridge,/requiresPhysicalPhaseTransition:phaseChanged/);
});

test('compatibility candidate fields mirror the single controller only',()=>{
  assert.match(bridge,/realtime\.candidateA=requestedA/);
  assert.match(bridge,/realtime\.candidateW=requestedW/);
  assert.doesNotMatch(bridge,/realtime\.candidateA=candidateA/);
});

test('authoritative phase control consumes combined controller result',()=>{
  assert.match(bridge,/EM2_EV_PHASE_CONTROL_V0\.1/);
  assert.match(bridge,/const ps=realtime\?\.phaseShadow\|\|\{\}/);
  assert.match(bridge,/source:'REALTIME_PHASE_CURRENT_CONTROLLER'/);
  assert.match(bridge,/target_W:valid\?phaseControl\.requestedW:0/);
});

test('deadline 3P force path remains unchanged and downstream of opportunity control',()=>{
  assert.match(bridge,/DEADLINE_FORCE_3P/);
  assert.match(bridge,/requestedW:deadlineMaxA\*EV_W_PER_A/);
  assert.match(bridge,/Executor-side hard deadline guard runs last/);
  assert.match(bridge,/deadlineGuardApplied=true/);
});

test('candidate preserves live connection and physical-load reconstruction boundaries',()=>{
  assert.match(bridge,/electricalConnectedEvidence/);
  assert.match(bridge,/effectiveConnected/);
  assert.match(bridge,/rawChargeState==='plugged_in_charging'/);
  assert.match(bridge,/measure_current\.offered/);
  assert.match(bridge,/offeredAUsable/);
  assert.match(bridge,/actualProductionPhaseCount/);
  assert.match(bridge,/EASEE_OFFERED_CURRENT/);
});

test('candidate keeps phase readback fail-closed for active physical load',()=>{
  assert.match(bridge,/const phaseReadbackValid=/);
  assert.match(bridge,/actualProductionPhaseCount===1/);
  assert.match(bridge,/actualProductionPhaseCount===3/);
  assert.match(bridge,/PHASE_READBACK_UNCONFIRMED/);
});

test('bridge remains logic-only with no physical device writes',()=>{
  assert.doesNotMatch(bridge,/setCapabilityValue\(/);
  assert.doesNotMatch(bridge,/runFlowCardAction\(/);
  assert.match(bridge,/noDeviceWrites:true/);
});

test('existing adapter/gate phase contract remains V0.1',()=>{
  assert.match(bridge,/phase_control_schema:'EM2_EV_PHASE_CONTROL_V0\.1'/);
  assert.match(bridge,/phase_control_authoritative:true/);
  assert.match(bridge,/phaseControlSchema:'EM2_EV_PHASE_CONTROL_V0\.1'/);
  assert.match(bridge,/phaseControlAuthoritative:true/);
});
