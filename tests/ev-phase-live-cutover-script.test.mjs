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

test('rollback restores source and refreshes armed-disabled status',()=>{
  const rb=src.indexOf('def rollback_armed():');
  const update=src.indexOf('update_writer(ARMED_SOURCE, ARMED_NAME)',rb);
  const trigger=src.indexOf('trigger(ACTUATOR_FLOW_ID)',update);
  const status=src.indexOf('status = get_status()',trigger);
  assert.ok(rb>=0 && update>rb && trigger>update && status>trigger);
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
