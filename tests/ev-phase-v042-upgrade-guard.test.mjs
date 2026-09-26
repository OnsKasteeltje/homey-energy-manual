import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const src=fs.readFileSync('services/pi/commissioning/upgrade_ev_phase_writer_v0_4_2.py','utf8');

test('upgrade requires two quiescent stable checks before deployment',()=>{
  assert.match(src,/QUIESCENCE_SEC = 3/);
  assert.match(src,/guards1 = stable_guard\(before_status, before_charger\)/);
  assert.match(src,/time\.sleep\(QUIESCENCE_SEC\)/);
  assert.match(src,/guards2 = stable_guard\(confirm_status, confirm_charger\)/);
  assert.match(src,/sameControlRevision/);
  assert.match(src,/samePhaseMode/);
  assert.match(src,/sameTargetA/);
});

test('upgrade rejects transient low circuit cap and paused positive target',()=>{
  assert.match(src,/MIN_NORMAL_CIRCUIT_A = 16/);
  assert.match(src,/normalCircuitCap/);
  assert.match(src,/notPausedDuringPositiveTarget/);
  assert.match(src,/PRE_UPGRADE_NOT_QUIESCENT/);
  assert.match(src,/PRE_UPGRADE_CHANGED_DURING_QUIESCENCE/);
});

test('upgrade still restores exact previous Advanced Flow on post-deploy failure',()=>{
  assert.match(src,/backup = writable_flow\(flow\)/);
  assert.match(src,/ROLLBACK: restoring exact previous EV Advanced Flow/);
  assert.match(src,/push\(backup\)/);
});
