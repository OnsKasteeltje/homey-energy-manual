import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const src=fs.readFileSync('src/homey/actuators/ev-power/ev-power-v0.4.1.phase-writer-live.js','utf8');

test('live writer enables physical phase execution explicitly',()=>{
  assert.match(src,/const PHASE_EXECUTION_ENABLED=true/);
  assert.match(src,/const canWrite=PHASE_EXECUTION_ENABLED&&liveEnabled/);
});

test('same-phase current decreases are adopted during transition',()=>{
  assert.match(src,/if\(desiredA<t\.requestedA\)/);
  assert.match(src,/t=\{\.\.\.t,requestedA:desiredA\}/);
  assert.match(src,/transitionA=desiredA/);
});

test('same-phase current increases are deferred until stable',()=>{
  assert.match(src,/transitionA=t\.requestedA/);
  assert.match(src,/if\(desiredA!==transitionA\)await scheduleNext\(500\)/);
});

test('phase mode changes during transition fail closed',()=>{
  assert.match(src,/PHASE_MODE_CHANGED_DURING_TRANSITION/);
});

test('transition physical actions use latched transition current',()=>{
  assert.match(src,/setCircuitA\(transitionA\)/);
  assert.match(src,/setCurrentA\(transitionA\)/);
  assert.match(src,/circuitTargetA!==transitionA/);
  assert.match(src,/chargerTargetA!==transitionA/);
});

test('safe writer uses full native Homey card ids plus phase-only cloud call',()=>{
  assert.match(src,/homey:device:\$\{CHARGER_ID\}:pauseCharging/);
  assert.match(src,/homey:device:\$\{CHARGER_ID\}:resumeCharging/);
  assert.match(src,/homey:device:\$\{CHARGER_ID\}:circuitCurrentControl/);
  assert.match(src,/homey:device:\$\{CHARGER_ID\}:setDynamicChargerCurrent/);
  assert.match(src,/Homey\.flow\.runFlowCardAction\(\{id,args\}\)/);
  assert.doesNotMatch(src,/runFlowCardAction\(\{uri,id,args\}\)/);
  assert.match(src,/commands\/set_phase_mode/);
  assert.doesNotMatch(src,/setCapabilityValue\(/);
});


test('live writer uses direct Advanced Flow self-trigger',()=>{
  assert.match(src,/Homey\.flow\.triggerAdvancedFlow\(\{id:FLOW_ID\}\)/);
  assert.doesNotMatch(src,/homey:manager:flow:programmatic_trigger/);
});


test('live cutover ignores transition state from armed-disabled or older writer',()=>{
  assert.match(src,/previous\?\.schema===VERSION/);
  assert.match(src,/previous\?\.phaseExecutionEnabled===true/);
  assert.match(src,/previous\?\.transition\?\.schema===TRANSITION_SCHEMA/);
});


test('failed writer recovers only from safe paused boundary',()=>{
  assert.match(src,/const safePausedRecovery=/);
  assert.match(src,/t\.stage==='FAILED'/);
  assert.match(src,/paused/);
  assert.match(src,/circuitTargetA!==null/);
  assert.match(src,/contractAligned/);
  assert.match(src,/fresh/);
  assert.match(src,/requestValid/);
  assert.match(src,/deadlinePhaseOK/);
  assert.match(src,/stage:'STABLE'/);
  assert.match(src,/failure:null/);
});


test('generic transition age is observability only',()=>{
  assert.match(src,/const TRANSITION_WARN_MS=90000/);
  assert.match(src,/transitionSlow:t\.startedAt&&transitionAge>TRANSITION_WARN_MS/);
  assert.doesNotMatch(src,/TRANSITION_TIMEOUT/);
});

test('stale phase confirmation retries while paused instead of failing',()=>{
  assert.match(src,/PHASE_CONFIRM_TIMEOUT_MS=30000/);
  assert.match(src,/PHASE_CONFIRM_RETRY/);
  assert.match(src,/await setPhaseMode\(desiredMode,vars\)/);
  assert.doesNotMatch(src,/failClosed\('PHASE_CONFIRM_TIMEOUT'\)/);
});
