import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const s=fs.readFileSync('services/pi/commissioning/ev_phase_commission.py','utf8');

test('commissioning is guarded by zero-current preconditions',()=>{
  assert.match(s,/PRECONDITION_TARGET_NOT_ZERO/);
  assert.match(s,/PRECONDITION_OFFERED_CURRENT_NOT_ZERO/);
  assert.match(s,/PRECONDITION_POWER_NOT_ZERO/);
  assert.match(s,/PRECONDITION_CHARGING_STILL_TRUE/);
});

test('credentials are interactive and not persisted',()=>{
  assert.match(s,/getpass\.getpass/);
  assert.match(s,/accessToken/);
  assert.doesNotMatch(s,/write_text\(.*password/);
  assert.doesNotMatch(s,/open\(.*token/);
});

test('commissioning uses official phase command and Homey readback',()=>{
  assert.match(s,/commands\/set_phase_mode/);
  assert.match(s,/phaseMode/);
  assert.match(s,/Locked to single phase/);
  assert.match(s,/Locked to three phase/);
});

test('failed 1P confirmation attempts locked 3P restore',()=>{
  assert.match(s,/best-effort restoring locked 3P/);
  assert.match(s,/MODE\["3P"\]\["value"\]/);
});

test('commissioning tool does not become an automatic daemon or timer',()=>{
  assert.doesNotMatch(s,/systemctl/);
  assert.doesNotMatch(s,/while True/);
  assert.match(s,/--mode/);
});
