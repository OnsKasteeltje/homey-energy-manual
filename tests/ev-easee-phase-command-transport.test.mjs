import test from 'node:test';
import assert from 'node:assert/strict';
import {
  sendEaseePhaseMode,
  validatePhaseCommandInput,
} from '../src/homey/actuators/ev-power/easee-phase-command-transport-v0.1.mjs';

test('validates required Easee command input',()=>{
  assert.throws(()=>validatePhaseCommandInput({serialNumber:'',phaseMode:1,accessToken:'x'}),/SERIAL_MISSING/);
  assert.throws(()=>validatePhaseCommandInput({serialNumber:'ABC',phaseMode:2,accessToken:'x'}),/PHASE_MODE_INVALID/);
  assert.throws(()=>validatePhaseCommandInput({serialNumber:'ABC',phaseMode:1,accessToken:''}),/ACCESS_TOKEN_MISSING/);
});

test('sends official set_phase_mode command for 1P',async()=>{
  const calls=[];
  const fetchFn=async(url,opts)=>{
    calls.push({url,opts});
    return {ok:true,status:200};
  };
  const r=await sendEaseePhaseMode({
    fetchFn,
    serialNumber:'ECHM6B9F',
    phaseMode:1,
    accessToken:'secret-token',
    transitionId:'t1',
    now:()=>new Date('2026-09-26T10:00:00Z'),
  });
  assert.equal(r.ok,true);
  assert.equal(r.httpStatus,200);
  assert.equal(r.transitionId,'t1');
  assert.equal(calls.length,1);
  assert.equal(calls[0].url,'https://api.easee.com/api/chargers/ECHM6B9F/commands/set_phase_mode');
  assert.equal(calls[0].opts.method,'POST');
  assert.deepEqual(JSON.parse(calls[0].opts.body),{phaseMode:1});
  assert.equal(calls[0].opts.headers.Authorization,'Bearer secret-token');
  assert.equal(JSON.stringify(r).includes('secret-token'),false);
  assert.equal(r.secretMaterialPersisted,false);
});

test('sends locked 3P command value 3',async()=>{
  let body=null;
  const fetchFn=async(_url,opts)=>{body=JSON.parse(opts.body);return {ok:true,status:200};};
  const r=await sendEaseePhaseMode({fetchFn,serialNumber:'ECHM6B9F',phaseMode:3,accessToken:'token'});
  assert.equal(r.ok,true);
  assert.deepEqual(body,{phaseMode:3});
});

test('returns fail result on HTTP error without leaking token',async()=>{
  const fetchFn=async()=>({ok:false,status:401});
  const r=await sendEaseePhaseMode({fetchFn,serialNumber:'ECHM6B9F',phaseMode:1,accessToken:'very-secret'});
  assert.equal(r.ok,false);
  assert.equal(r.reason,'HTTP_401');
  assert.equal(JSON.stringify(r).includes('very-secret'),false);
});

test('returns fail result on network error',async()=>{
  const fetchFn=async()=>{throw new Error('boom');};
  const r=await sendEaseePhaseMode({fetchFn,serialNumber:'ECHM6B9F',phaseMode:1,accessToken:'token'});
  assert.equal(r.ok,false);
  assert.match(r.reason,/NETWORK_ERROR:boom/);
});
