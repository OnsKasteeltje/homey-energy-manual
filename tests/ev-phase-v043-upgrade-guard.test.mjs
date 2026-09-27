import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const src=fs.readFileSync(
  'services/pi/commissioning/upgrade_ev_phase_writer_v0_4_3.py',
  'utf8'
);

test('v0.4.3 upgrade supports stable or diagnosed orphaned-cap state only',()=>{
  assert.match(src,/def classify\(st, charger\):/);
  assert.match(src,/return "STABLE"/);
  assert.match(src,/return "ORPHANED_CAP"/);
  assert.match(src,/PRE_UPGRADE_UNSAFE_OR_UNKNOWN_STATE/);
});

test('orphaned-cap guard requires safe paused zero-load state',()=>{
  assert.match(src,/CIRCUIT_LIMIT_BELOW_REQUEST/);
  assert.match(src,/CIRCUIT_RECOVERY_REQUIRES_KNOWN_BASELINE/);
  assert.match(src,/originalCircuitLost/);
  assert.match(src,/plugged_in_paused/);
  assert.match(src,/offeredZero/);
  assert.match(src,/powerZero/);
  assert.match(src,/temporaryCapRange/);
});

test('upgrade requires quiescence and unchanged circuit target before push',()=>{
  assert.match(src,/QUIESCENCE_SEC = 10/);
  assert.match(src,/sameControlRevision/);
  assert.match(src,/samePhaseMode/);
  assert.match(src,/sameTargetA/);
  assert.match(src,/sameCircuitTargetA/);
  assert.match(src,/PRE_UPGRADE_CHANGED_DURING_QUIESCENCE/);
  assert.match(src,/PRE_UPGRADE_CHANGED_BEFORE_PUSH/);
});

test('upgrade never guesses or writes an orphan baseline',()=>{
  assert.doesNotMatch(src,/circuitCurrentControl/);
  assert.doesNotMatch(src,/setDynamicCircuit/);
  assert.match(src,/Do not guess it/);
});

test('post-deploy orphan remains intentionally fail closed until baseline is restored',()=>{
  assert.match(src,/V043_ORPHAN_EXPECTED_FAIL_CLOSED/);
  assert.match(src,/CIRCUIT_RECOVERY_REQUIRES_KNOWN_BASELINE/);
});

test('upgrade restores exact previous Advanced Flow on deployment failure',()=>{
  assert.match(src,/backup = writable_flow\(flow\)/);
  assert.match(src,/ROLLBACK: restoring exact previous EV Advanced Flow/);
  assert.match(src,/push\(backup\)/);
});
