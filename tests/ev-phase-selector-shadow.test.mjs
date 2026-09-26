import test from 'node:test';
import assert from 'node:assert/strict';
import {decideEvPhaseShadow} from '../services/pi/planner/ev/ev_phase_selector_shadow_v0.2.mjs';

const now=1_800_000_000_000;
const old={modeSinceMs:now-600000};

test('OFF -> 1P sizes from total P1 and delegates physical phase',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:-2500,p1L1W:-400,p1L2W:-1800,p1L3W:-300,actualEvCommandA:0,actualEvPhaseCount:0},{mode:'OFF',...old},now);
 assert.equal(r.mode,'1P');
 assert.equal(r.requestedA,10);
 assert.equal(r.requestedW,2300);
 assert.equal(r.phaseCommand,null);
 assert.equal(r.physicalPhaseOwner,'EASEE_EQUALIZER');
});

test('OFF -> 3P uses total P1 even with one importing phase',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:-4400,p1L1W:-2800,p1L2W:-2200,p1L3W:600,actualEvCommandA:0,actualEvPhaseCount:0},{mode:'OFF',...old},now);
 assert.equal(r.mode,'3P');
 assert.equal(r.requestedA,6);
 assert.equal(r.p1DecisionBasis,'TOTAL_NET_GRID_POWER_PLUS_ACTUAL_EV_COMMAND');
});

test('previous SHADOW command is not added back as physical load',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:-2000,actualEvCommandA:0,actualEvPhaseCount:0},{mode:'3P',requestedA:16,...old},now);
 assert.equal(r.mode,'1P');
 assert.equal(r.input.actualEvW,0);
 assert.equal(r.shadowStateAffectsPhysicalReconstruction,false);
});

test('actual production 3P 6A is added back to total P1',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:0,actualEvCommandA:6,actualEvPhaseCount:3},{mode:'3P',requestedA:12,...old},now);
 assert.equal(r.input.actualEvW,4140);
 assert.equal(r.input.availableTotalW,4140);
 assert.equal(r.mode,'3P');
 assert.equal(r.requestedA,6);
});

test('actual production 1P load does not require knowing physical phase',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:0,actualEvCommandA:8,actualEvPhaseCount:1},{mode:'1P',requestedA:15,...old},now);
 assert.equal(r.input.actualEvW,1840);
 assert.equal(r.input.availableTotalW,1840);
 assert.equal(r.mode,'1P');
 assert.equal(r.requestedA,8);
 assert.equal(r.phaseCommand,null);
});

test('invalid actual EV phase count fails shadow closed',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:-5000,actualEvCommandA:8,actualEvPhaseCount:2},{mode:'OFF',...old},now);
 assert.equal(r.mode,'OFF');
 assert.equal(r.reason,'INVALID_ACTUAL_EV_COMMAND_SHAPE');
});

test('1P holds mode inside transition hysteresis',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:-2000,actualEvCommandA:0,actualEvPhaseCount:0},{mode:'1P',requestedA:8,...old},now);
 assert.equal(r.mode,'1P');
});

test('1P -> 3P above enter threshold after dwell',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:-4600,actualEvCommandA:0,actualEvPhaseCount:0},{mode:'1P',requestedA:16,...old},now);
 assert.equal(r.mode,'3P');
 assert.equal(r.requestedA,6);
 assert.equal(r.reason,'1P_TO_3P_TOTAL_SURPLUS_HIGH');
});

test('blocked opportunity always OFF',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:false,maxA:16,p1TotalW:-6000,actualEvCommandA:8,actualEvPhaseCount:3},{mode:'3P',requestedA:8,...old},now);
 assert.equal(r.mode,'OFF');
 assert.equal(r.requestedA,0);
 assert.equal(r.deviceWrites,false);
});

test('shadow has no control or device writes',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:-5000,actualEvCommandA:0,actualEvPhaseCount:0},{mode:'OFF',...old},now);
 assert.equal(r.shadow,true);
 assert.equal(r.deviceWrites,false);
 assert.equal(r.controlWrites,false);
});
