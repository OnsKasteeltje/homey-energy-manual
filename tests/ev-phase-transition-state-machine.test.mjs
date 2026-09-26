import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULTS,
  decidePhaseTransition,
  initialTransitionState,
  normalizeEaseePhaseMode,
  easeeCommandForMode,
} from '../src/homey/actuators/ev-power/ev-phase-transition-v0.1.mjs';

const t0=1_800_000_000_000;
const base={
  gatePass:true,
  controlFresh:true,
  liveEnabled:false,
  chargerTargetA:0,
  chargerPowerW:0,
  offeredA:0,
};

test('maps Easee readback labels and command values',()=>{
  assert.equal(normalizeEaseePhaseMode('Locked to single phase'),'1P');
  assert.equal(normalizeEaseePhaseMode('Auto'),'AUTO');
  assert.equal(normalizeEaseePhaseMode('Locked to three phase'),'3P');
  assert.equal(easeeCommandForMode('1P'),1);
  assert.equal(easeeCommandForMode('3P'),3);
});

test('OFF normalizes current to zero without phase command',()=>{
  const r=decidePhaseTransition({...base,desiredMode:'OFF',desiredA:0,chargerTargetA:6,easeePhaseMode:'Auto'},initialTransitionState(t0),t0);
  assert.equal(r.action.type,'SET_CURRENT_0');
  assert.equal(r.action.requestedA,0);
  assert.equal(r.action.physicalWriteAllowed,false);
});

test('same confirmed phase applies requested current directly',()=>{
  const r=decidePhaseTransition({...base,desiredMode:'1P',desiredA:11,easeePhaseMode:'Locked to single phase'},initialTransitionState(t0),t0);
  assert.equal(r.action.type,'SET_CURRENT');
  assert.equal(r.action.requestedA,11);
});

test('new phase transition always starts by forcing zero current',()=>{
  const r=decidePhaseTransition({...base,desiredMode:'1P',desiredA:16,chargerTargetA:6,chargerPowerW:4200,offeredA:6,easeePhaseMode:'Auto'},initialTransitionState(t0),t0);
  assert.equal(r.state.stage,'ZEROING');
  assert.equal(r.action.type,'SET_CURRENT_0');
  assert.equal(r.action.reason,'PHASE_CHANGE_REQUIRES_ZERO_CURRENT');
});

test('zero confirmed requests dedicated Easee phase command',()=>{
  let r=decidePhaseTransition({...base,desiredMode:'1P',desiredA:16,easeePhaseMode:'Auto'},initialTransitionState(t0),t0);
  r=decidePhaseTransition({...base,desiredMode:'1P',desiredA:16,easeePhaseMode:'Auto'},r.state,t0+1000);
  assert.equal(r.state.stage,'PHASE_COMMAND');
  assert.equal(r.action.type,'SET_PHASE_MODE');
  assert.equal(r.action.phaseModeValue,1);
});

test('accepted command waits for readback confirmation',()=>{
  let r=decidePhaseTransition({...base,desiredMode:'3P',desiredA:6,easeePhaseMode:'Auto'},initialTransitionState(t0),t0);
  r=decidePhaseTransition({...base,desiredMode:'3P',desiredA:6,easeePhaseMode:'Auto'},r.state,t0+1000);
  const id=r.state.transitionId;
  r=decidePhaseTransition({...base,desiredMode:'3P',desiredA:6,easeePhaseMode:'Auto',phaseCommandResult:{transitionId:id,ok:true,at:new Date(t0+1500).toISOString()}},r.state,t0+1500);
  assert.equal(r.state.stage,'CONFIRMING');
  assert.equal(r.action.type,'WAIT_PHASE_CONFIRM');
});

test('confirmed mode enforces dead-time before current',()=>{
  let r=decidePhaseTransition({...base,desiredMode:'1P',desiredA:12,easeePhaseMode:'Auto'},initialTransitionState(t0),t0);
  r=decidePhaseTransition({...base,desiredMode:'1P',desiredA:12,easeePhaseMode:'Auto'},r.state,t0+1000);
  const id=r.state.transitionId;
  r=decidePhaseTransition({...base,desiredMode:'1P',desiredA:12,easeePhaseMode:'Auto',phaseCommandResult:{transitionId:id,ok:true}},r.state,t0+1500);
  r=decidePhaseTransition({...base,desiredMode:'1P',desiredA:12,easeePhaseMode:'Locked to single phase'},r.state,t0+2000);
  assert.equal(r.state.stage,'DEADTIME');
  assert.equal(r.action.type,'WAIT_DEADTIME');
  r=decidePhaseTransition({...base,desiredMode:'1P',desiredA:12,easeePhaseMode:'Locked to single phase'},r.state,t0+2000+DEFAULTS.deadTimeMs);
  assert.equal(r.state.stage,'APPLY_CURRENT');
  assert.equal(r.action.type,'SET_CURRENT');
  assert.equal(r.action.requestedA,12);
});

test('transition completes only after current target matches',()=>{
  const prev={
    ...initialTransitionState(t0),
    stage:'APPLY_CURRENT',
    transitionId:'x',
    requestedMode:'3P',
    requestedA:7,
    startedAt:new Date(t0).toISOString(),
    stageSince:new Date(t0+1000).toISOString(),
  };
  const r=decidePhaseTransition({...base,desiredMode:'3P',desiredA:7,easeePhaseMode:'Locked to three phase',chargerTargetA:7},prev,t0+2000);
  assert.equal(r.state.stage,'STABLE');
  assert.equal(r.action.type,'NOOP');
});

test('gate failure always fails closed to zero',()=>{
  const r=decidePhaseTransition({...base,gatePass:false,desiredMode:'1P',desiredA:10,easeePhaseMode:'Locked to single phase',chargerTargetA:10},initialTransitionState(t0),t0);
  assert.equal(r.state.stage,'FAILED');
  assert.equal(r.action.type,'SET_CURRENT_0');
  assert.equal(r.action.failClosed,true);
});

test('phase confirmation timeout fails closed',()=>{
  const prev={
    ...initialTransitionState(t0),
    stage:'CONFIRMING',
    transitionId:'x',
    requestedMode:'1P',
    requestedA:10,
    startedAt:new Date(t0).toISOString(),
    stageSince:new Date(t0).toISOString(),
    phaseCommandSentAt:new Date(t0).toISOString(),
  };
  const r=decidePhaseTransition({...base,desiredMode:'1P',desiredA:10,easeePhaseMode:'Auto'},prev,t0+DEFAULTS.commandConfirmTimeoutMs+1);
  assert.equal(r.state.stage,'FAILED');
  assert.equal(r.action.type,'SET_CURRENT_0');
  assert.equal(r.action.reason,'PHASE_CONFIRM_TIMEOUT');
});

test('state machine never performs a physical write itself',()=>{
  const cases=[
    {...base,desiredMode:'OFF',desiredA:0,easeePhaseMode:'Auto'},
    {...base,desiredMode:'1P',desiredA:6,easeePhaseMode:'Auto'},
    {...base,desiredMode:'3P',desiredA:6,easeePhaseMode:'Auto'},
  ];
  for(const x of cases){
    const r=decidePhaseTransition(x,initialTransitionState(t0),t0);
    assert.equal(r.action.physicalWriteAllowed,false);
  }
});
