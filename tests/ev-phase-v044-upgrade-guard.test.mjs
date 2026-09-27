import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const src=fs.readFileSync(
  'services/pi/commissioning/upgrade_ev_phase_writer_v0_4_4.py',
  'utf8'
);

test('deploy guard checks only active transition and temporary circuit cap',()=>{
  assert.match(src,/def deploy_guard/);
  assert.match(src,/noActiveTransition/);
  assert.match(src,/normalCircuitBaseline/);
  assert.match(src,/EV_MAX_TRANSITION_CAP_A = 16/);
  assert.match(src,/circuit_target > EV_MAX_TRANSITION_CAP_A/);
  assert.doesNotMatch(src,/QUIESCENCE_SEC/);
  assert.doesNotMatch(src,/statusStable/);
  assert.doesNotMatch(src,/phaseAligned/);
  assert.doesNotMatch(src,/physicalStateCoherent/);
  assert.doesNotMatch(src,/samePhaseMode/);
  assert.doesNotMatch(src,/sameChargeState/);
});

test('guard does not require charging, paused, phase alignment or PV state',()=>{
  assert.doesNotMatch(src,/physically_running/);
  assert.doesNotMatch(src,/physically_paused/);
  assert.doesNotMatch(src,/offered_a - charger_target/);
  assert.doesNotMatch(src,/sameConfirmedMode/);
  assert.doesNotMatch(src,/sameCircuitTargetA/);
});

test('upgrade rejects a source that still contains self retrigger',()=>{
  assert.match(src,/SOURCE_SELF_RETRIGGER_STILL_PRESENT/);
  assert.match(src,/triggerAdvancedFlow/);
});

test('upgrade requires bounded final pause-read fix',()=>{
  assert.match(src,/FINAL_PAUSE_READ_AFTER_TIMEOUT/);
});

test('upgrade blocks unsupported HomeyScript timers',()=>{
  assert.match(src,/SOURCE_UNSUPPORTED_HOMEYSCRIPT_TIMER/);
  assert.match(src,/setTimeout\(/);
  assert.match(src,/const sleep=ms=>wait\(ms\);/);
});

test('deployment verifies exact installed source before one validation trigger',()=>{
  assert.match(src,/DEPLOYED_SOURCE_MISMATCH/);
  assert.match(src,/deployed_source != source/);
  assert.match(src,/trigger-advanced-flow/);
  assert.match(src,/V044_VALIDATION_TRIGGER_DID_NOT_UPDATE_STATUS/);
});

test('runtime FAILED after validation does not cause deployment rollback',()=>{
  assert.doesNotMatch(src,/raise RuntimeError\("V044_FAILED:/);
  assert.match(src,/writer reported runtime FAILED after deployment/);
});

test('true deployment failure restores exact previous Advanced Flow body',()=>{
  assert.match(src,/backup = writable_flow\(flow\)/);
  assert.match(src,/ROLLBACK: restoring exact previous EV Advanced Flow/);
  assert.match(src,/push\(backup\)/);
});
