import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const src=fs.readFileSync('src/homey/actuators/ev-power/ev-power-v0.4.0.phase-writer.js','utf8');

test('writer is armed but physically disabled by default',()=>{
  assert.match(src,/const PHASE_EXECUTION_ENABLED=false/);
  assert.match(src,/phaseExecutionEnabled:PHASE_EXECUTION_ENABLED/);
  assert.match(src,/const canWrite=PHASE_EXECUTION_ENABLED&&liveEnabled/);
});

test('native Homey Easee action cards own non-phase writes',()=>{
  assert.match(src,/runNative\('pauseCharging'/);
  assert.match(src,/runNative\('resumeCharging'/);
  assert.match(src,/runNative\('circuitCurrentControl',\{current:a\}\)/);
  assert.match(src,/runNative\('setDynamicChargerCurrent',\{current:a\}\)/);
  assert.doesNotMatch(src,/setCapabilityValue\(/);
});

test('custom cloud path is phase-only and uses locked 1P or 3P',()=>{
  assert.match(src,/commands\/set_phase_mode/);
  assert.match(src,/\{phaseMode:pv\}/);
  assert.match(src,/mode==='1P'\?1:mode==='3P'\?3:null/);
  assert.doesNotMatch(src,/dynamicChargerCurrent/);
  assert.doesNotMatch(src,/dynamicCurrent/);
});

test('token refresh stores rotating pair without credentials',()=>{
  assert.match(src,/accounts\/refresh_token/);
  assert.match(src,/\{refreshToken:refresh\}/);
  assert.match(src,/IDS\.access/);
  assert.match(src,/IDS\.refresh/);
  assert.match(src,/IDS\.expires/);
  assert.doesNotMatch(src,/password/i);
  assert.doesNotMatch(src,/username/i);
});

test('writer follows safe transition resume sequence by stage',()=>{
  const deadtimeStage=src.indexOf("if(t.stage==='DEADTIME')");
  const capWrite=src.indexOf("await setCircuitA(desiredA);",deadtimeStage);
  const armingStage=src.indexOf("if(t.stage==='ARMING_CIRCUIT_CAP')");
  const resumeWrite=src.indexOf("await resumeSession();",armingStage);
  const resumingStage=src.indexOf("if(t.stage==='RESUMING')");
  const currentWrite=src.indexOf("await setCurrentA(desiredA);",resumingStage);
  const applyStage=src.indexOf("if(t.stage==='APPLY_CURRENT')");
  const restoreWrite=src.indexOf("await setCircuitA(restoreA);",applyStage);
  const restoringStage=src.indexOf("if(t.stage==='RESTORING_CIRCUIT_CAP')");

  assert.ok(deadtimeStage>=0);
  assert.ok(capWrite>deadtimeStage && capWrite<armingStage);
  assert.ok(resumeWrite>armingStage && resumeWrite<resumingStage);
  assert.ok(currentWrite>resumingStage && currentWrite<applyStage);
  assert.ok(restoreWrite>applyStage && restoreWrite<restoringStage);
});

test('phase change requires confirmed pause before cloud command',()=>{
  assert.match(src,/if\(!paused\)[\s\S]*pauseSession/);
  assert.match(src,/await setPhaseMode\(desiredMode,vars\)/);
  assert.match(src,/stage:'CONFIRMING_PHASE'/);
});

test('phase confirmation precedes deadtime and circuit cap',()=>{
  assert.match(src,/confirmedMode===desiredMode/);
  assert.match(src,/stage:'DEADTIME'/);
  assert.match(src,/DEADTIME_MS=5000/);
  assert.match(src,/PROTECT_RESUME_CURRENT_RESET/);
});

test('resume reset is bounded before desired current is re-applied',()=>{
  assert.match(src,/await setCircuitA\(desiredA\)/);
  assert.match(src,/await resumeSession\(\)/);
  assert.match(src,/await setCurrentA\(desiredA\)/);
  assert.match(src,/RESUME_RESETS_CHARGER_CURRENT/);
});

test('writer restores original circuit limit only after current and charging confirmation',()=>{
  assert.match(src,/chargerTargetA!==desiredA/);
  assert.match(src,/charging\|\|chargeState==='plugged_in_charging'/);
  assert.match(src,/await setCircuitA\(restoreA\)/);
  assert.match(src,/stage:'RESTORING_CIRCUIT_CAP'/);
});

test('fail closed pauses and never invents a higher circuit limit',()=>{
  assert.match(src,/const failClosed=async reason/);
  assert.match(src,/await pauseSession\(\)/);
  assert.match(src,/CIRCUIT_TARGET_UNKNOWN/);
  assert.match(src,/CIRCUIT_LIMIT_BELOW_REQUEST/);
  assert.match(src,/ORIGINAL_CIRCUIT_LIMIT_INVALID/);
});

test('writer uses authoritative adapter and gate schemas',()=>{
  assert.match(src,/EM2_EV_POWER_ADAPTER_V0\.2/);
  assert.match(src,/EM2_EV_ADAPTER_GATE_V0\.3/);
  assert.match(src,/EM2_EV_PHASE_COMMAND_V0\.1/);
  assert.match(src,/controlRevision/);
});

test('writer self-retriggers in bounded short steps',()=>{
  assert.match(src,/scheduleNext/);
  assert.match(src,/Homey\.flow\.triggerAdvancedFlow\(\{id:FLOW_ID\}\)/);
  assert.match(src,/TRANSITION_TIMEOUT_MS=90000/);
  assert.match(src,/PHASE_CONFIRM_TIMEOUT_MS=30000/);
});
