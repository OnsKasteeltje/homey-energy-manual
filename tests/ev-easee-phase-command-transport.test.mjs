import test from 'node:test';
import assert from 'node:assert/strict';
import {
  refreshEaseeTokenPair,
  sendEaseePhaseMode,
} from '../src/homey/actuators/ev-power/easee-phase-cloud-v0.3.mjs';

test('sends official set_phase_mode command for locked 1P',async()=>{
  const calls=[];
  const fetchFn=async(url,opts)=>{
    calls.push({url,opts});
    return {ok:true,status:200,json:async()=>({})};
  };
  const r=await sendEaseePhaseMode({
    fetchFn,serialNumber:'ECHM6B9F',phaseMode:1,
    accessToken:'secret-token',transitionId:'t1',
    now:()=>new Date('2026-09-26T10:00:00Z'),
  });
  assert.equal(r.ok,true);
  assert.equal(calls[0].url,'https://api.easee.com/api/chargers/ECHM6B9F/commands/set_phase_mode');
  assert.deepEqual(JSON.parse(calls[0].opts.body),{phaseMode:1});
  assert.equal(JSON.stringify(r).includes('secret-token'),false);
  assert.equal(r.secretMaterialPersisted,false);
});

test('only locked 1P and locked 3P command values are accepted',async()=>{
  const fetchFn=async()=>({ok:true,status:200,json:async()=>({})});
  await assert.rejects(()=>sendEaseePhaseMode({fetchFn,serialNumber:'X',phaseMode:2,accessToken:'x'}),/PHASE_MODE_INVALID/);
});

test('refresh uses access plus rotating refresh token',async()=>{
  const calls=[];
  const fetchFn=async(url,opts)=>{
    calls.push({url,opts});
    return {
      ok:true,status:200,
      json:async()=>({accessToken:'new-access',refreshToken:'new-refresh',expiresIn:3600})
    };
  };
  const r=await refreshEaseeTokenPair({
    fetchFn,accessToken:'old-access',refreshToken:'old-refresh',
    now:()=>new Date('2026-09-26T10:00:00Z')
  });
  assert.equal(r.ok,true);
  assert.equal(calls[0].url,'https://api.easee.com/api/accounts/refresh_token');
  assert.deepEqual(JSON.parse(calls[0].opts.body),{accessToken:'old-access',refreshToken:'old-refresh'});
  assert.equal(r.tokens.accessToken,'new-access');
  assert.equal(r.tokens.refreshToken,'new-refresh');
  assert.equal(r.tokens.expiresIn,3600);
});

test('custom cloud transport has no current or circuit control',async()=>{
  const fs=await import('node:fs');
  const s=fs.readFileSync('src/homey/actuators/ev-power/easee-phase-cloud-v0.3.mjs','utf8');
  assert.doesNotMatch(s,/dynamicChargerCurrent/);
  assert.doesNotMatch(s,/dynamicCurrent/);
  assert.doesNotMatch(s,/phase1/);
  assert.doesNotMatch(s,/phase2/);
  assert.doesNotMatch(s,/phase3/);
});

test('HTTP error does not leak supplied access token',async()=>{
  const fetchFn=async()=>({ok:false,status:401,json:async()=>({})});
  const r=await sendEaseePhaseMode({fetchFn,serialNumber:'ECHM6B9F',phaseMode:1,accessToken:'very-secret'});
  assert.equal(r.ok,false);
  assert.equal(r.reason,'HTTP_401');
  assert.equal(JSON.stringify(r).includes('very-secret'),false);
});
