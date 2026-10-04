import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const path='apps/homey/control/ev/pi-dynamic-planner-bridge-v1.5.8.production-tuned.js';
const bridge=fs.readFileSync(path,'utf8');

test('v1.5.8 candidate parses as one async HomeyScript body',()=>{
  assert.doesNotThrow(()=>{
    new Function('Homey', `return (async()=>{\n${bridge}\n})();`);
  });
});

test('v1.5.8 keeps the stable production Bridge identity and single controller',()=>{
  assert.match(bridge,/PI_DYNAMIC_PLANNER_BRIDGE_V1\.5\.8_PRODUCTION_TUNED/);
  assert.match(bridge,/stable Bridge flow 8bf53fdb-76f4-47db-8ccb-773ac515f06e/);
  assert.doesNotMatch(bridge,/let candidateA=/);
  assert.match(bridge,/realtime\.candidateA=requestedA/);
  assert.match(bridge,/source:'REALTIME_PHASE_CURRENT_CONTROLLER'/);
});

test('production tuning separates OFF re-entry and 1P to 3P dwell',()=>{
  assert.match(bridge,/EVPC_OFF_REENTRY_DWELL_MS=120000/);
  assert.match(bridge,/EVPC_1P_TO_3P_DWELL_MS=180000/);
  assert.doesNotMatch(bridge,/EVPC_UPWARD_DWELL_MS/);
  assert.match(bridge,/sampleMs-previousModeSinceMs>=EVPC_OFF_REENTRY_DWELL_MS/);
  assert.match(bridge,/sampleMs-previousModeSinceMs>=EVPC_1P_TO_3P_DWELL_MS/);
  assert.match(bridge,/onePTo3pDwellOK&&[\s\S]*evpcCanSustainMin\('3P',availableTotalW\)/);
  assert.match(bridge,/else if\(offReentryDwellOK\)/);
});

test('downward transitions remain rolling-driven without upward dwell',()=>{
  assert.match(bridge,/3P_TO_OFF_ROLLING_LOW/);
  assert.match(bridge,/3P_TO_1P_ROLLING_LOW/);
  assert.match(bridge,/1P_TO_OFF_ROLLING_LOW/);
  assert.match(bridge,/EVPC_ROLLING_WINDOW_MS=120000/);
  assert.match(bridge,/EVPC_ROLLING_MIN_COVERAGE_MS=90000/);
});

test('same-phase current prefers up to 300 W import without fighting 250 W phase margin',()=>{
  assert.match(bridge,/EVPC_UPSCALE_IMPORT_TARGET_W=300/);
  assert.match(bridge,/EVPC_IMPORT_DEADBAND_W=250/);
  assert.match(bridge,/EVPC_CURRENT_IMPORT_LIMIT_W=Math\.max\(EVPC_IMPORT_DEADBAND_W,EVPC_UPSCALE_IMPORT_TARGET_W\)/);
  assert.match(bridge,/syntheticP1W>EVPC_CURRENT_IMPORT_LIMIT_W/);
  assert.match(bridge,/excessImportW=syntheticP1W-EVPC_CURRENT_IMPORT_LIMIT_W/);

  const wattsPerAmp=690;
  const nextAmp=9;
  const importPreference=300;
  const threshold=nextAmp*wattsPerAmp-importPreference;
  assert.equal(threshold,5910);
  assert.equal(nextAmp*wattsPerAmp-threshold,300);
});

test('bounded predictive current jumps remain unchanged',()=>{
  assert.match(bridge,/EVPC_MAX_UPSTEP_1P_A=3/);
  assert.match(bridge,/EVPC_MAX_UPSTEP_3P_A=2/);
  assert.match(bridge,/physicalTargetSettled=/);
  assert.match(bridge,/phasePhysicalA===requestedA/);
  assert.match(bridge,/currentReason='PREDICTIVE_UP_WAIT_PHYSICAL'/);
  assert.match(bridge,/currentReason='PREDICTIVE_UP_BOUNDED'/);
  assert.match(bridge,/currentReason='FAST_IMPORT_DOWN'/);
  assert.match(bridge,/controllerVersion:'EM2_EV_PHASE_CURRENT_CONTROLLER_V0\.3'/);
});

test('phase contract and deadline force remain unchanged',()=>{
  assert.match(bridge,/EM2_EV_PHASE_CONTROL_V0\.1/);
  assert.match(bridge,/DEADLINE_FORCE_3P/);
  assert.match(bridge,/requestedW:deadlineMaxA\*EV_W_PER_A/);
  assert.match(bridge,/Executor-side hard deadline guard runs last/);
});

test('bridge remains logic-only and creates no physical writer',()=>{
  assert.doesNotMatch(bridge,/setCapabilityValue\(/);
  assert.doesNotMatch(bridge,/runFlowCardAction\(/);
  assert.match(bridge,/noDeviceWrites:true/);
  assert.match(bridge,/physicalPhaseOwner:'EASEE_EQUALIZER'/);
});
