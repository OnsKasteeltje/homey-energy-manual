import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const src=fs.readFileSync('services/pi/commissioning/cutover_ev_phase_writer_live.py','utf8');

test('pre-cutover refreshes armed actuator status after bridge',()=>{
  const bridge=src.indexOf('trigger(BRIDGE_FLOW_ID)');
  const actuator=src.indexOf('trigger(ACTUATOR_FLOW_ID)',bridge);
  const status=src.indexOf('status = get_status()',actuator);
  assert.ok(bridge>=0 && actuator>bridge && status>actuator);
});

test('rollback restores the prebuilt armed-disabled body without extra Homey reads',()=>{
  const start=src.indexOf('def rollback_armed():');
  const end=src.indexOf('\ndef main():',start);
  assert.ok(start>=0 && end>start);
  const rollback=src.slice(start,end);
  assert.match(rollback,/ROLLBACK_BODY_NOT_PREPARED/);
  assert.match(rollback,/push_writer_body\(ROLLBACK_BODY\)/);
  assert.doesNotMatch(rollback,/trigger\(ACTUATOR_FLOW_ID\)/);
  assert.doesNotMatch(rollback,/get_status\(\)/);
});

test('cutover guard still requires paused zero-load state and enough PV',()=>{
  assert.match(src,/"paused": charger\.get\("chargeState"\) == "plugged_in_paused"/);
  assert.match(src,/"offeredZero"/);
  assert.match(src,/"powerZero"/);
  assert.match(src,/"p1ExportEnough"/);
});

test('cutover rollback remains armed-disabled on failure',()=>{
  assert.match(src,/except Exception:\s*\n\s*rollback_armed\(\)/);
});


test('external commissioning monitor is low-rate and read-only',()=>{
  assert.match(src,/POLL_SEC = 5/);
  assert.match(src,/one persisted Logic status read per poll/);
  assert.doesNotMatch(src,/fallback: actuator status stalled/);
  assert.doesNotMatch(src,/stagnant_polls/);
});
