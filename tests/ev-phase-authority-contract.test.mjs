import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const bridge=fs.readFileSync('src/homey/power-intent/pi-dynamic-planner-bridge-v1.5.1.phase-authority.js','utf8');
const adapter=fs.readFileSync('src/homey/adapters/ev-power/ev-power-v0.2.0.phase-aware.js','utf8');
const gate=fs.readFileSync('src/homey/validation/ev-power-adapter-gate-v0.3.0.phase-aware.js','utf8');
const actuator=fs.readFileSync('src/homey/actuators/ev-power/ev-power-v0.3.1.phase-authority-candidate.js','utf8');

test('bridge exposes one authoritative phase control contract',()=>{
  assert.match(bridge,/EM2_EV_PHASE_CONTROL_V0\.1/);
  assert.match(bridge,/phase_control_authoritative:true/);
  assert.match(bridge,/phase_mode:/);
  assert.match(bridge,/phase_requested_A:/);
  assert.match(bridge,/phase_requested_W:/);
  assert.match(bridge,/controlRevision/);
});

test('bridge derives target_W from authoritative mode plus amps',()=>{
  assert.match(bridge,/target_W:valid\?phaseControl\.requestedW:0/);
  assert.match(bridge,/requestedW:pm==='1P'\?pa\*230:pm==='3P'\?pa\*EV_W_PER_A:0/);
});

test('deadline phase control is forced to 3P',()=>{
  assert.match(bridge,/DEADLINE_FORCE_3P/);
  assert.match(bridge,/mode:'3P'/);
  assert.match(bridge,/requestedW:deadlineMaxA\*EV_W_PER_A/);
});

test('adapter validates phase aware power exactly',()=>{
  assert.match(adapter,/EM2_EV_POWER_ADAPTER_V0\.2/);
  assert.match(adapter,/EM2_EV_PHASE_CONTROL_V0\.1/);
  assert.match(adapter,/PHASE_MODE_A_230V_V0\.1/);
  assert.match(adapter,/targetW===requestedW/);
  assert.match(adapter,/requestedW===expectedW/);
  assert.match(adapter,/EM2_EV_PHASE_COMMAND_V0\.1/);
});

test('adapter has no physical writes',()=>{
  assert.match(adapter,/physicalWrite:false/);
  assert.match(adapter,/noDeviceWrites:true/);
  assert.doesNotMatch(adapter,/setCapabilityValue\(/);
  assert.doesNotMatch(adapter,/runFlowCardAction\(/);
});

test('gate makes phase command part of final authority',()=>{
  assert.match(gate,/EM2_EV_ADAPTER_GATE_V0\.3/);
  assert.match(gate,/EM2_EV_POWER_ADAPTER_V0\.2/);
  assert.match(gate,/EM2_EV_PHASE_COMMAND_V0\.1/);
  assert.match(gate,/phaseAuthority:/);
  assert.match(gate,/finalStatus:errors\.length\?'FAIL':'PASS'/);
  assert.match(gate,/phaseControl:true/);
});

test('actuator candidate consumes only authoritative adapter command',()=>{
  assert.match(actuator,/EM2_EV_POWER_ADAPTER_V0\.2/);
  assert.match(actuator,/EM2_EV_ADAPTER_GATE_V0\.3/);
  assert.match(actuator,/cmd\?\.schema==='EM2_EV_PHASE_COMMAND_V0\.1'/);
  assert.match(actuator,/const desiredMode=String\(cmd\?\.mode/);
  assert.match(actuator,/const desiredA=num\(cmd\?\.requested_A\)/);
  assert.doesNotMatch(actuator,/adapter\?\.phaseShadow/);
});

test('actuator candidate remains hard no-write',()=>{
  assert.match(actuator,/const PHASE_EXECUTION_ENABLED=false/);
  assert.match(actuator,/physicalWritePerformed:false/);
  assert.doesNotMatch(actuator,/await\s+[^;\n]*setCapabilityValue\(/);
  assert.doesNotMatch(actuator,/await\s+[^;\n]*runFlowCardAction\(/);
  assert.doesNotMatch(actuator,/await\s+fetch\(/);
});

test('deadline is independently rejected if not 3P at actuator boundary',()=>{
  assert.match(actuator,/const deadlinePhaseOK=!deadlineTarget\|\|desiredMode==='3P'/);
  assert.match(actuator,/DEADLINE_MUST_USE_3P/);
});

test('paused same phase requires safety cap before resume',()=>{
  assert.match(actuator,/SET_TRANSITION_CIRCUIT_CAP/);
  assert.match(actuator,/PAUSED_RESUME_REQUIRES_SAFETY_CAP/);
});


test('bridge reconstructs physical EV load from Easee offered current',()=>{
  assert.match(bridge,/measure_current\.offered/);
  assert.match(bridge,/offeredAUsable/);
  assert.match(bridge,/EASEE_OFFERED_CURRENT/);
  assert.match(bridge,/phaseShadowPhysicalA=/);
});
