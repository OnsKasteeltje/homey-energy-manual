import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const production=fs.readFileSync('src/homey/actuators/ev-power/ev-power-v0.2.15.control-authority.js','utf8');
const transition=fs.readFileSync('src/homey/actuators/ev-power/ev-phase-transition-v0.4.mjs','utf8');
const cloud=fs.readFileSync('src/homey/actuators/ev-power/easee-phase-cloud-v0.3.mjs','utf8');
const bootstrap=fs.readFileSync('services/pi/commissioning/bootstrap_easee_homey_tokens.py','utf8');

test('current production actuator still has no phase-mode writer',()=>{
  assert.doesNotMatch(production,/set_phase_mode/);
  assert.doesNotMatch(production,/phaseModeValue/);
  assert.doesNotMatch(production,/commands\/set_phase_mode/);
});

test('transition state machine is decision-only and models native circuit cap restore',()=>{
  assert.match(transition,/physicalWriteAllowed:false/);
  assert.match(transition,/PAUSE_SESSION/);
  assert.match(transition,/SET_TRANSITION_CIRCUIT_CAP/);
  assert.match(transition,/RESTORE_CIRCUIT_CAP/);
  assert.doesNotMatch(transition,/Homey\.devices/);
  assert.doesNotMatch(transition,/fetch\(/);
  assert.doesNotMatch(transition,/setCapabilityValue/);
});

test('custom Easee cloud layer is phase-only',()=>{
  assert.match(cloud,/commands\/set_phase_mode/);
  assert.match(cloud,/accounts\/refresh_token/);
  assert.doesNotMatch(cloud,/dynamicChargerCurrent/);
  assert.doesNotMatch(cloud,/dynamicCurrent/);
  assert.doesNotMatch(cloud,/pause_charging/);
  assert.doesNotMatch(cloud,/resume_charging/);
});

test('bootstrap stores tokens in Homey but never username or password',()=>{
  assert.match(bootstrap,/EM2_Easee_Access_Token/);
  assert.match(bootstrap,/EM2_Easee_Refresh_Token/);
  assert.match(bootstrap,/getpass\.getpass/);
  assert.match(bootstrap,/Username\/password were not stored/);
  assert.doesNotMatch(bootstrap,/EASEE_PASSWORD=/);
});

test('only locked 1P and locked 3P are phase command values',()=>{
  assert.match(cloud,/\[1,3\]\.includes/);
  assert.doesNotMatch(cloud,/\[1,2,3\]\.includes/);
});


test('bootstrap does not enumerate full Homey Logic store or expose token bodies in argv',()=>{
  assert.doesNotMatch(bootstrap,/get-variables/);
  assert.match(bootstrap,/get-variable/);
  assert.match(bootstrap,/tempfile\.mkstemp/);
  assert.match(bootstrap,/os\.fchmod\(fd, 0o600\)/);
  assert.match(bootstrap,/--body", f"@\{path\}"/);
});
