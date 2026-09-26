import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULTS,
  decidePhaseTransition,
  initialTransitionState,
  normalizeEaseePhaseMode,
  easeeCommandForMode,
} from '../src/homey/actuators/ev-power/ev-phase-transition-v0.3.mjs';

const t0=1_800_000_000_000;
const paused={
  gatePass:true,
  controlFresh:true,
  liveEnabled:false,
  chargerTargetA:0,
  chargerPowerW:0,
  offeredA:0,
  charging:false,
  chargeState:'plugged_in_paused',
};
const charging={
  ...paused,
  chargerTargetA:6,
  chargerPowerW:4200,
  offeredA:6,
  charging:true,
  chargeState:'plugged_in_charging',
};

test('maps Easee readback labels and command values',()=>{
  assert.equal(normalizeEaseePhaseMode('Locked to single phase'),'1P');
  assert.equal(normalizeEaseePhaseMode('Auto'),'AUTO');
  assert.equal(normalizeEaseePhaseMode('Locked to three phase'),'3P');
  assert.equal(easeeCommandForMode('1P'),1);
  assert.equal(easeeCommandForMode('3P'),3);
});

test('OFF requires paused session',()=>{
  const r=decidePhaseTransition({...charging,desiredMode:'OFF',desiredA:0,easeePhaseMode:'Auto'},initialTransitionState(t0),t0);
  assert.equal(r.action.type,'PAUSE_SESSION');
});

test('same phase but paused still arms safety circuit cap before resume',()=>{
  const r=decidePhaseTransition({...paused,desiredMode:'1P',desiredA:11,easeePhaseMode:'Locked to single phase'},initialTransitionState(t0),t0);
  assert.equal(r.state.stage,'ARMING_CIRCUIT_CAP');
  assert.equal(r.action.type,'SET_TRANSITION_CIRCUIT_CAP');
  assert.equal(r.action.amps,11);
  assert.equal(r.action.ttlMinutes,1);
});

test('new mode transition starts by pausing session',()=>{
  const r=decidePhaseTransition({...charging,desiredMode:'1P',desiredA:16,easeePhaseMode:'Auto'},initialTransitionState(t0),t0);
  assert.equal(r.state.stage,'PAUSING');
  assert.equal(r.action.type,'PAUSE_SESSION');
});

test('pause confirmed requests dedicated phase command',()=>{
  let r=decidePhaseTransition({...charging,desiredMode:'1P',desiredA:16,easeePhaseMode:'Auto'},initialTransitionState(t0),t0);
  r=decidePhaseTransition({...paused,desiredMode:'1P',desiredA:16,easeePhaseMode:'Auto'},r.state,t0+1000);
  assert.equal(r.state.stage,'PHASE_COMMAND');
  assert.equal(r.action.type,'SET_PHASE_MODE');
  assert.equal(r.action.phaseModeValue,1);
});

test('accepted phase command waits for locked readback',()=>{
  let r=decidePhaseTransition({...charging,desiredMode:'3P',desiredA:6,easeePhaseMode:'Auto'},initialTransitionState(t0),t0);
  r=decidePhaseTransition({...paused,desiredMode:'3P',desiredA:6,easeePhaseMode:'Auto'},r.state,t0+1000);
  const id=r.state.transitionId;
  r=decidePhaseTransition({...paused,desiredMode:'3P',desiredA:6,easeePhaseMode:'Auto',phaseCommandResult:{transitionId:id,ok:true,at:new Date(t0+1500).toISOString()}},r.state,t0+1500);
  assert.equal(r.state.stage,'CONFIRMING_PHASE');
  assert.equal(r.action.type,'WAIT_PHASE_CONFIRM');
});

test('phase confirmation then deadtime arms symmetric TTL circuit cap',()=>{
  let r=decidePhaseTransition({...charging,desiredMode:'1P',desiredA:12,easeePhaseMode:'Auto'},initialTransitionState(t0),t0);
  r=decidePhaseTransition({...paused,desiredMode:'1P',desiredA:12,easeePhaseMode:'Auto'},r.state,t0+1000);
  const id=r.state.transitionId;
  r=decidePhaseTransition({...paused,desiredMode:'1P',desiredA:12,easeePhaseMode:'Auto',phaseCommandResult:{transitionId:id,ok:true}},r.state,t0+1500);
  r=decidePhaseTransition({...paused,desiredMode:'1P',desiredA:12,easeePhaseMode:'Locked to single phase'},r.state,t0+2000);
  assert.equal(r.state.stage,'DEADTIME');
  r=decidePhaseTransition({...paused,desiredMode:'1P',desiredA:12,easeePhaseMode:'Locked to single phase'},r.state,t0+2000+DEFAULTS.deadTimeMs);
  assert.equal(r.state.stage,'ARMING_CIRCUIT_CAP');
  assert.equal(r.action.type,'SET_TRANSITION_CIRCUIT_CAP');
  assert.equal(r.action.amps,12);
  assert.equal(r.action.ttlMinutes,1);
});

test('accepted circuit cap permits resume',()=>{
  const prev={
    ...initialTransitionState(t0),
    stage:'ARMING_CIRCUIT_CAP',
    transitionId:'x',
    requestedMode:'1P',
    requestedA:8,
    startedAt:new Date(t0).toISOString(),
    stageSince:new Date(t0+1000).toISOString(),
    phaseConfirmedAt:new Date(t0+500).toISOString(),
  };
  const r=decidePhaseTransition({...paused,desiredMode:'1P',desiredA:8,easeePhaseMode:'Locked to single phase',circuitCapResult:{transitionId:'x',ok:true,at:new Date(t0+1500).toISOString()}},prev,t0+1500);
  assert.equal(r.state.stage,'RESUMING');
  assert.equal(r.action.type,'RESUME_SESSION');
});

test('resume transition reapplies charger current because Easee resets it',()=>{
  const prev={
    ...initialTransitionState(t0),
    stage:'RESUMING',
    transitionId:'x',
    requestedMode:'1P',
    requestedA:6,
    startedAt:new Date(t0).toISOString(),
    stageSince:new Date(t0+1000).toISOString(),
    circuitCapAcceptedAt:new Date(t0+500).toISOString(),
  };
  const r=decidePhaseTransition({
    ...paused,
    chargeState:'plugged_in',
    desiredMode:'1P',
    desiredA:6,
    easeePhaseMode:'Locked to single phase',
    chargerTargetA:32,
  },prev,t0+2000);
  assert.equal(r.state.stage,'APPLY_CURRENT');
  assert.equal(r.action.type,'SET_CURRENT');
  assert.equal(r.action.requestedA,6);
  assert.equal(r.action.reason,'RESUME_RESETS_CHARGER_CURRENT');
});

test('transition completes only after desired current and charging are observed',()=>{
  const prev={
    ...initialTransitionState(t0),
    stage:'APPLY_CURRENT',
    transitionId:'x',
    requestedMode:'1P',
    requestedA:6,
    startedAt:new Date(t0).toISOString(),
    stageSince:new Date(t0+1000).toISOString(),
  };
  const r=decidePhaseTransition({
    ...charging,
    chargerTargetA:6,
    chargerPowerW:1400,
    offeredA:6,
    desiredMode:'1P',
    desiredA:6,
    easeePhaseMode:'Locked to single phase',
  },prev,t0+2000);
  assert.equal(r.state.stage,'STABLE');
  assert.equal(r.action.type,'NOOP');
});

test('circuit cap failure fail-closes by pausing',()=>{
  const prev={
    ...initialTransitionState(t0),
    stage:'ARMING_CIRCUIT_CAP',
    transitionId:'x',
    requestedMode:'3P',
    requestedA:6,
    startedAt:new Date(t0).toISOString(),
    stageSince:new Date(t0).toISOString(),
  };
  const r=decidePhaseTransition({...paused,desiredMode:'3P',desiredA:6,easeePhaseMode:'Locked to three phase',circuitCapResult:{transitionId:'x',ok:false,reason:'HTTP_500'}},prev,t0+1000);
  assert.equal(r.state.stage,'FAILED');
  assert.equal(r.action.type,'PAUSE_SESSION');
  assert.match(r.action.reason,/CIRCUIT_CAP_FAILED/);
});

test('gate failure always fail-closes by pausing',()=>{
  const r=decidePhaseTransition({...charging,gatePass:false,desiredMode:'1P',desiredA:10,easeePhaseMode:'Locked to single phase'},initialTransitionState(t0),t0);
  assert.equal(r.state.stage,'FAILED');
  assert.equal(r.action.type,'PAUSE_SESSION');
  assert.equal(r.action.failClosed,true);
});

test('state machine never performs a physical write itself',()=>{
  for(const x of [
    {...paused,desiredMode:'OFF',desiredA:0,easeePhaseMode:'Auto'},
    {...charging,desiredMode:'1P',desiredA:6,easeePhaseMode:'Auto'},
    {...charging,desiredMode:'3P',desiredA:6,easeePhaseMode:'Auto'},
  ]){
    const r=decidePhaseTransition(x,initialTransitionState(t0),t0);
    assert.equal(r.action.physicalWriteAllowed,false);
  }
});
