import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const production=fs.readFileSync('src/homey/actuators/ev-power/ev-power-v0.2.15.control-authority.js','utf8');
const transition=fs.readFileSync('src/homey/actuators/ev-power/ev-phase-transition-v0.1.mjs','utf8');
const transport=fs.readFileSync('src/homey/actuators/ev-power/easee-phase-command-transport-v0.1.mjs','utf8');

test('current production actuator has no phase-mode writer',()=>{
  assert.doesNotMatch(production,/set_phase_mode/);
  assert.doesNotMatch(production,/phaseModeValue/);
  assert.doesNotMatch(production,/commands\/set_phase_mode/);
});

test('transition state machine is decision-only',()=>{
  assert.match(transition,/physicalWriteAllowed:false/);
  assert.doesNotMatch(transition,/Homey\.devices/);
  assert.doesNotMatch(transition,/fetch\(/);
  assert.doesNotMatch(transition,/setCapabilityValue/);
});

test('Easee transport contains no policy or credential persistence',()=>{
  assert.match(transport,/commands\/set_phase_mode/);
  assert.match(transport,/secretMaterialPersisted:false/);
  assert.doesNotMatch(transport,/userName/);
  assert.doesNotMatch(transport,/password/);
  assert.doesNotMatch(transport,/refreshToken/);
});

test('only locked 1P and locked 3P are valid command values',()=>{
  assert.match(transport,/\[1,3\]\.includes/);
  assert.doesNotMatch(transport,/\[1,2,3\]\.includes/);
});
