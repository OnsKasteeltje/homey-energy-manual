import test from 'node:test';
import assert from 'node:assert/strict';
import {decideEvPhaseShadow} from '../src/homey/ev/ev-phase-selector-shadow-v0.1.mjs';

const now=1_800_000_000_000;
const old={modeSinceMs:now-600000,phaseSinceMs:now-600000};

test('OFF -> 1P chooses phase with largest surplus',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:-2500,p1L1W:-400,p1L2W:-1800,p1L3W:-300,actualEvCommandA:0,actualEvPhaseCount:0},{mode:'OFF',...old},now);
 assert.equal(r.mode,'1P'); assert.equal(r.phase,2); assert.equal(r.requestedA,7);
});

test('OFF -> 3P uses total P1 even with one importing phase',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:-4400,p1L1W:-2800,p1L2W:-2200,p1L3W:600,actualEvCommandA:0,actualEvPhaseCount:0},{mode:'OFF',...old},now);
 assert.equal(r.mode,'3P'); assert.equal(r.requestedA,6); assert.equal(r.threePhaseDecisionBasis,'TOTAL_P1_NET_POWER_PLUS_ACTUAL_EV_COMMAND');
});

test('previous SHADOW 3P command is not added back as physical load',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:0,p1L1W:-2000,p1L2W:1000,p1L3W:1000,actualEvCommandA:0,actualEvPhaseCount:0},{mode:'3P',requestedA:6,...old},now);
 assert.equal(r.mode,'1P'); assert.equal(r.phase,1);
 assert.equal(r.input.actualEvW,0);
 assert.equal(r.shadowStateAffectsPhysicalReconstruction,false);
});

test('actual production 3P 6A is added back while SHADOW state remains separate',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:0,p1L1W:0,p1L2W:0,p1L3W:0,actualEvCommandA:6,actualEvPhaseCount:3},{mode:'3P',requestedA:12,...old},now);
 assert.equal(r.input.actualEvW,4140);
 assert.equal(r.input.availableTotalW,4140);
 assert.equal(r.mode,'3P');
 assert.equal(r.requestedA,6);
});

test('actual production 1P load is added back only to its physical phase',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:0,p1L1W:0,p1L2W:0,p1L3W:0,actualEvCommandA:8,actualEvPhaseCount:1,actualEvPhase:2},{mode:'1P',phase:2,requestedA:15,...old},now);
 assert.deepEqual(r.input.phaseAvailableW,[0,1840,0]);
 assert.equal(r.phase,2);
 assert.equal(r.requestedA,8);
});

test('invalid actual EV phase shape fails shadow closed',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:-5000,p1L1W:-2000,p1L2W:-2000,p1L3W:-1000,actualEvCommandA:8,actualEvPhaseCount:1},{mode:'OFF',...old},now);
 assert.equal(r.mode,'OFF');
 assert.equal(r.reason,'INVALID_ACTUAL_EV_COMMAND_SHAPE');
});

test('1P holds mode inside transition hysteresis',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:-2000,p1L1W:-2000,p1L2W:0,p1L3W:0,actualEvCommandA:0,actualEvPhaseCount:0},{mode:'1P',phase:1,requestedA:8,...old},now);
 assert.equal(r.mode,'1P');
});

test('blocked opportunity always OFF',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:false,maxA:16,p1TotalW:-6000,p1L1W:-3000,p1L2W:-3000,p1L3W:0,actualEvCommandA:8,actualEvPhaseCount:3},{mode:'3P',requestedA:8,...old},now);
 assert.equal(r.mode,'OFF'); assert.equal(r.requestedA,0); assert.equal(r.deviceWrites,false);
});

test('shadow has no control or device writes',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:-5000,p1L1W:-2500,p1L2W:-2500,p1L3W:0,actualEvCommandA:0,actualEvPhaseCount:0},{mode:'OFF',...old},now);
 assert.equal(r.shadow,true); assert.equal(r.deviceWrites,false); assert.equal(r.controlWrites,false);
});
