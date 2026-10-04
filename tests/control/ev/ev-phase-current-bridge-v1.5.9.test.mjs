import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const path='apps/homey/control/ev/pi-dynamic-planner-bridge-v1.5.9.adaptive-upscale.js';
const bridge=fs.readFileSync(path,'utf8');

test('v1.5.9 candidate parses as one async HomeyScript body',()=>{
  assert.doesNotThrow(()=>{
    new Function('Homey', `return (async()=>{\n${bridge}\n})();`);
  });
});

test('v1.5.9 keeps stable production Bridge identity and single controller',()=>{
  assert.match(bridge,/PI_DYNAMIC_PLANNER_BRIDGE_V1\.5\.9_ADAPTIVE_UPSCALE/);
  assert.match(bridge,/stable Bridge flow 8bf53fdb-76f4-47db-8ccb-773ac515f06e/);
  assert.doesNotMatch(bridge,/let candidateA=/);
  assert.match(bridge,/realtime\.candidateA=requestedA/);
  assert.match(bridge,/source:'REALTIME_PHASE_CURRENT_CONTROLLER'/);
  assert.match(bridge,/controllerVersion:'EM2_EV_PHASE_CURRENT_CONTROLLER_V0\.4'/);
});

test('phase dwell and downward safety remain unchanged',()=>{
  assert.match(bridge,/EVPC_OFF_REENTRY_DWELL_MS=120000/);
  assert.match(bridge,/EVPC_1P_TO_3P_DWELL_MS=180000/);
  assert.match(bridge,/EVPC_ROLLING_WINDOW_MS=120000/);
  assert.match(bridge,/EVPC_ROLLING_MIN_COVERAGE_MS=90000/);
  assert.match(bridge,/3P_TO_OFF_ROLLING_LOW/);
  assert.match(bridge,/3P_TO_1P_ROLLING_LOW/);
  assert.match(bridge,/1P_TO_OFF_ROLLING_LOW/);
});

test('baseline current bounds remain +3A 1P and +2A 3P',()=>{
  assert.match(bridge,/EVPC_MAX_UPSTEP_1P_A=3/);
  assert.match(bridge,/EVPC_MAX_UPSTEP_3P_A=2/);
  assert.match(bridge,/EVPC_MAX_ADAPTIVE_UPSTEP_3P_A=4/);
  assert.match(bridge,/currentReason='PREDICTIVE_UP_WAIT_PHYSICAL'/);
  assert.match(bridge,/currentReason='FAST_IMPORT_DOWN'/);
});

test('adaptive 3P step requires current export and rolling support',()=>{
  assert.match(bridge,/phaseMode==='3P'&&rolling\.ready&&currentExportW>0/);
  assert.match(bridge,/Math\.floor\(\(currentExportW\+EVPC_UPSCALE_IMPORT_TARGET_W\)\/wpa\)/);
  assert.match(bridge,/rollingSupportedStepA=Math\.max\(0,rollingDesiredA-requestedA\)/);
  assert.match(bridge,/desiredStepA=Math\.max\(0,desiredA-requestedA\)/);
  assert.match(bridge,/adaptive3pStepA=Math\.min\([\s\S]*EVPC_MAX_ADAPTIVE_UPSTEP_3P_A,[\s\S]*currentExportSupportedStepA,[\s\S]*rollingSupportedStepA,[\s\S]*desiredStepA/);
  assert.match(bridge,/adaptive3pStepA>EVPC_MAX_UPSTEP_3P_A/);
  assert.match(bridge,/PREDICTIVE_UP_ADAPTIVE_EXPORT/);
});

test('adaptive 3P arithmetic only exceeds baseline when both signals support it',()=>{
  const step=({requestedA,desiredA,rollingDesiredA,currentExportW})=>{
    const wpa=690;
    const currentExportSupportedStepA=Math.max(
      0,
      Math.floor((currentExportW+300)/wpa)
    );
    const rollingSupportedStepA=Math.max(0,rollingDesiredA-requestedA);
    const desiredStepA=Math.max(0,desiredA-requestedA);
    return Math.min(
      4,
      currentExportSupportedStepA,
      rollingSupportedStepA,
      desiredStepA
    );
  };

  // 3 kW export + rolling support for 4 A -> one bounded +4 A catch-up.
  assert.equal(step({
    requestedA:7,
    desiredA:12,
    rollingDesiredA:11,
    currentExportW:3000,
  }),4);

  // Current export only supports the existing +2 A baseline: no adaptive extension.
  assert.equal(step({
    requestedA:7,
    desiredA:12,
    rollingDesiredA:11,
    currentExportW:1500,
  }),2);

  // Large instantaneous export is insufficient when the 2-minute signal only supports +2 A.
  assert.equal(step({
    requestedA:7,
    desiredA:12,
    rollingDesiredA:9,
    currentExportW:4000,
  }),2);

  // No export means adaptive extension is disabled.
  assert.equal(step({
    requestedA:7,
    desiredA:12,
    rollingDesiredA:12,
    currentExportW:0,
  }),0);
});

test('same-phase import preference and fast down-regulation stay unchanged',()=>{
  assert.match(bridge,/EVPC_UPSCALE_IMPORT_TARGET_W=300/);
  assert.match(bridge,/EVPC_IMPORT_DEADBAND_W=250/);
  assert.match(bridge,/EVPC_CURRENT_IMPORT_LIMIT_W=Math\.max\(EVPC_IMPORT_DEADBAND_W,EVPC_UPSCALE_IMPORT_TARGET_W\)/);
  assert.match(bridge,/syntheticP1W>EVPC_CURRENT_IMPORT_LIMIT_W/);
  assert.match(bridge,/excessImportW=syntheticP1W-EVPC_CURRENT_IMPORT_LIMIT_W/);
});

test('adaptive diagnostics expose why a larger step was allowed',()=>{
  for(const field of [
    'rollingDesiredA',
    'currentExportW',
    'adaptive3pCandidateStepA',
    'appliedUpscaleStepA',
    'maxAdaptiveUpscaleStep3pA',
  ]){
    assert.match(bridge,new RegExp(field));
  }
});

test('phase contract, deadline force and writer ownership remain unchanged',()=>{
  assert.match(bridge,/EM2_EV_PHASE_CONTROL_V0\.1/);
  assert.match(bridge,/DEADLINE_FORCE_3P/);
  assert.match(bridge,/requestedW:deadlineMaxA\*EV_W_PER_A/);
  assert.match(bridge,/Executor-side hard deadline guard runs last/);
  assert.doesNotMatch(bridge,/setCapabilityValue\(/);
  assert.doesNotMatch(bridge,/runFlowCardAction\(/);
  assert.match(bridge,/noDeviceWrites:true/);
  assert.match(bridge,/physicalPhaseOwner:'EASEE_EQUALIZER'/);
});
