import test from 'node:test';
import assert from 'node:assert/strict';
import {decideEvPhaseShadow} from '../src/homey/ev/ev-phase-selector-shadow-v0.1.mjs';

const now=1_800_000_000_000;
const old={modeSinceMs:now-600000,phaseSinceMs:now-600000};

test('OFF -> 1P chooses phase with largest surplus',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:-2500,p1L1W:-400,p1L2W:-1800,p1L3W:-300},{mode:'OFF',...old},now);
 assert.equal(r.mode,'1P'); assert.equal(r.phase,2); assert.equal(r.requestedA,7);
});

test('OFF -> 3P uses total P1 even with one importing phase',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:-4400,p1L1W:-2800,p1L2W:-2200,p1L3W:600},{mode:'OFF',...old},now);
 assert.equal(r.mode,'3P'); assert.equal(r.requestedA,6); assert.equal(r.threePhaseDecisionBasis,'TOTAL_P1_NET_POWER');
});

test('3P falls back to 1P instead of OFF when one phase still has surplus',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:0,p1L1W:-2000,p1L2W:1000,p1L3W:1000},{mode:'3P',requestedA:6,...old},now);
 assert.equal(r.mode,'1P'); assert.equal(r.phase,1);
});

test('1P holds mode inside transition hysteresis',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:-2000,p1L1W:-2000,p1L2W:0,p1L3W:0},{mode:'1P',phase:1,requestedA:8,...old},now);
 assert.equal(r.mode,'1P');
});

test('blocked opportunity always OFF',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:false,maxA:16,p1TotalW:-6000,p1L1W:-3000,p1L2W:-3000,p1L3W:0},{mode:'3P',requestedA:8,...old},now);
 assert.equal(r.mode,'OFF'); assert.equal(r.requestedA,0); assert.equal(r.deviceWrites,false);
});

test('shadow has no control or device writes',()=>{
 const r=decideEvPhaseShadow({opportunityAllowed:true,maxA:16,p1TotalW:-5000,p1L1W:-2500,p1L2W:-2500,p1L3W:0},{mode:'OFF',...old},now);
 assert.equal(r.shadow,true); assert.equal(r.deviceWrites,false); assert.equal(r.controlWrites,false);
});
