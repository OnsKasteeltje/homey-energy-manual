import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const src=fs.readFileSync(
  'services/pi/commissioning/upgrade_ev_phase_writer_v0_4_4.py',
  'utf8'
);

test('upgrade requires a quiescent STABLE v0.4.3/v0.4.4 writer',()=>{
  assert.match(src,/statusStable/);
  assert.match(src,/transitionStable/);
  assert.match(src,/normalCircuitCap/);
  assert.match(src,/physicalStateCoherent/);
  assert.match(src,/PRE_UPGRADE_NOT_QUIESCENT/);
});

test('upgrade rechecks structural quiescence while allowing same-phase current drift',()=>{
  assert.match(src,/QUIESCENCE_SEC = 10/);
  assert.match(src,/samePhaseMode/);
  assert.match(src,/sameConfirmedMode/);
  assert.match(src,/sameCircuitTargetA/);
  assert.match(src,/sameChargeState/);
  assert.doesNotMatch(src,/"sameControlRevision"/);
  assert.doesNotMatch(src,/"sameTargetA"/);
  assert.match(src,/PRE_UPGRADE_CHANGED_DURING_QUIESCENCE/);
  assert.match(src,/PRE_UPGRADE_CHANGED_BEFORE_PUSH/);
});

test('physical coherence follows Easee requested versus offered current',()=>{
  assert.match(src,/abs\(offered_a - charger_target\) <= 0\.5/);
  assert.doesNotMatch(src,/abs\(offered_a - target_a\)/);
  assert.match(src,/physically_running or physically_paused/);
});

test('upgrade rejects a source that still contains self retrigger',()=>{
  assert.match(src,/SOURCE_SELF_RETRIGGER_STILL_PRESENT/);
  assert.match(src,/triggerAdvancedFlow/);
});

test('post-deploy validation requires live bounded v0.4.4',()=>{
  assert.match(src,/V044_SCHEMA_NOT_ACTIVE/);
  assert.match(src,/V044_NOT_LIVE/);
  assert.match(src,/V044_EXECUTION_NOT_ENABLED/);
  assert.match(src,/V044_BOUNDED_FLAG_MISSING/);
  assert.match(src,/V044_FAILED/);
});

test('deployment failure restores exact prior Advanced Flow body',()=>{
  assert.match(src,/backup = writable_flow\(flow\)/);
  assert.match(src,/ROLLBACK: restoring exact previous EV Advanced Flow/);
  assert.match(src,/push\(backup\)/);
});


test('upgrade blocks unsupported HomeyScript timers',()=>{
  assert.match(src,/SOURCE_UNSUPPORTED_HOMEYSCRIPT_TIMER/);
  assert.match(src,/setTimeout\(/);
  assert.match(src,/const sleep=ms=>wait\(ms\);/);
});
