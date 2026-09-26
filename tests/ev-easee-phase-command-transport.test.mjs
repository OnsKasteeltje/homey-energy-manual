import test from 'node:test';
import assert from 'node:assert/strict';
import {
  sendEaseePhaseMode,
  sendEaseeTransitionCircuitCap,
  validatePhaseCommandInput,
  validateCircuitCapInput,
} from '../src/homey/actuators/ev-power/easee-transition-command-transport-v0.2.mjs';

test('validates required Easee phase command input',()=>{
  assert.throws(()=>validatePhaseCommandInput({serialNumber:'',phaseMode:1,accessToken:'x'}),/SERIAL_MISSING/);
  assert.throws(()=>validatePhaseCommandInput({serialNumber:'ABC',phaseMode:2,accessToken:'x'}),/PHASE_MODE_INVALID/);
  assert.throws(()=>validatePhaseCommandInput({serialNumber:'ABC',phaseMode:1,accessToken:''}),/ACCESS_TOKEN_MISSING/);
});

test('sends official set_phase_mode command for 1P',async()=>{
  const calls=[];
  const fetchFn=async(url,opts)=>{calls.push({url,opts});return {ok:true,status:200};};
  const r=await sendEaseePhaseMode({
    fetchFn,serialNumber:'ECHM6B9F',phaseMode:1,accessToken:'secret-token',transitionId:'t1',
    now:()=>new Date('2026-09-26T10:00:00Z'),
  });
  assert.equal(r.ok,true);
  assert.equal(calls[0].url,'https://api.easee.com/api/chargers/ECHM6B9F/commands/set_phase_mode');
  assert.deepEqual(JSON.parse(calls[0].opts.body),{phaseMode:1});
  assert.equal(JSON.stringify(r).includes('secret-token'),false);
  assert.equal(r.secretMaterialPersisted,false);
});

test('validates temporary circuit cap input',()=>{
  assert.throws(()=>validateCircuitCapInput({siteId:'',circuitId:'1',amps:6,minutes:1,accessToken:'x'}),/SITE_ID_MISSING/);
  assert.throws(()=>validateCircuitCapInput({siteId:'1',circuitId:'',amps:6,minutes:1,accessToken:'x'}),/CIRCUIT_ID_MISSING/);
  assert.throws(()=>validateCircuitCapInput({siteId:'1',circuitId:'2',amps:5,minutes:1,accessToken:'x'}),/AMPS_INVALID/);
  assert.throws(()=>validateCircuitCapInput({siteId:'1',circuitId:'2',amps:6,minutes:0,accessToken:'x'}),/TTL_INVALID/);
});

test('sets symmetric A/A/A transition circuit cap with one minute TTL',async()=>{
  const calls=[];
  const fetchFn=async(url,opts)=>{calls.push({url,opts});return {ok:true,status:200};};
  const r=await sendEaseeTransitionCircuitCap({
    fetchFn,
    siteId:'749051',
    circuitId:'705301',
    amps:6,
    minutes:1,
    accessToken:'secret',
    transitionId:'t2',
    now:()=>new Date('2026-09-26T10:00:00Z'),
  });
  assert.equal(r.ok,true);
  assert.equal(r.kind,'SET_TRANSITION_CIRCUIT_CAP');
  assert.equal(calls[0].url,'https://api.easee.com/api/sites/749051/circuits/705301/dynamicCurrent');
  assert.deepEqual(JSON.parse(calls[0].opts.body),{phase1:6,phase2:6,phase3:6,timeToLive:1});
  assert.equal(JSON.stringify(r).includes('secret'),false);
});

test('circuit safety cap never chooses a physical phase',async()=>{
  let body=null;
  const fetchFn=async(_url,opts)=>{body=JSON.parse(opts.body);return {ok:true,status:200};};
  await sendEaseeTransitionCircuitCap({fetchFn,siteId:'749051',circuitId:'705301',amps:12,minutes:1,accessToken:'x'});
  assert.equal(body.phase1,12);
  assert.equal(body.phase2,12);
  assert.equal(body.phase3,12);
});

test('returns fail result on HTTP error without leaking token',async()=>{
  const fetchFn=async()=>({ok:false,status:401});
  const r=await sendEaseePhaseMode({fetchFn,serialNumber:'ECHM6B9F',phaseMode:1,accessToken:'very-secret'});
  assert.equal(r.ok,false);
  assert.equal(r.reason,'HTTP_401');
  assert.equal(JSON.stringify(r).includes('very-secret'),false);
});
