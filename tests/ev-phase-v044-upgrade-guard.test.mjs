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

test('upgrade rechecks unchanged state before replacing the sole writer',()=>{
  assert.match(src,/QUIESCENCE_SEC = 10/);
  assert.match(src,/sameControlRevision/);
  assert.match(src,/samePhaseMode/);
  assert.match(src,/sameTargetA/);
  assert.match(src,/sameCircuitTargetA/);
  assert.match(src,/sameChargeState/);
  assert.match(src,/PRE_UPGRADE_CHANGED_DURING_QUIESCENCE/);
  assert.match(src,/PRE_UPGRADE_CHANGED_BEFORE_PUSH/);
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
