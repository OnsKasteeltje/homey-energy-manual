import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const src=fs.readFileSync(
  'apps/homey/control/ev/ev-power-v0.4.7.atomic-easee-tokens.js','utf8'
);
const start=src.indexOf("const EASEE_BUNDLE_SCHEMA='");
const end=src.indexOf('// Easee documents that tokens should be refreshed',start);
assert.ok(start>=0&&end>start);

const UUID='11111111-2222-4333-8444-555555555555';
const makeBundle=(overrides={})=>({
  schema:'EM2_EASEE_TOKEN_BUNDLE_V1',
  accessToken:'old-access',
  refreshToken:'old-refresh',
  expiresAt:new Date(Date.now()+3600000).toISOString(),
  revision:100,
  ...overrides
});

function fixture({bundle=makeBundle(),onWrite=null,postJson=async()=>({
  accessToken:'new-access',refreshToken:'new-refresh',expiresIn:3600
}),id=UUID}={}){
  let state=JSON.stringify(bundle);
  const calls=[];
  const Homey={logic:{
    getVariable:async({id})=>{
      calls.push('GET');
      assert.equal(id,UUID);
      return {value:state};
    },
    updateVariable:async({id,variable})=>{
      calls.push('PUT');
      assert.equal(id,UUID);
      state=variable.value;
      if(onWrite)state=JSON.stringify(onWrite(JSON.parse(state)));
    }
  }};
  const ctx={Homey,IDS:{easeeBundle:id},Date,
    parse:x=>{try{return JSON.parse(String(x??''));}catch{return null;}},
    postJson:async(...args)=>{calls.push('REFRESH');return postJson(...args);}
  };
  const manager=vm.runInNewContext(
    src.slice(start,end)+'\n({readEaseeVars,getAccessToken})',ctx
  );
  return {
    ...manager,calls,
    getState:()=>JSON.parse(state),
    setState:value=>{state=JSON.stringify(value);}
  };
}

test('v0.4.7 HomeyScript parses and preserves one physical writer and phase policy',()=>{
  const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
  assert.doesNotThrow(()=>new AsyncFunction(src));
  assert.match(src,/EM2_EV_ACTUATOR_V0\.4\.7_PHASE_WRITER/);
  assert.match(src,/RUN_LOCK_MS=35000/);
  assert.match(src,/EV_MIN_A=6,EV_MAX_A=16/);
  assert.match(src,/const withEasee401RefreshRetry=async/);
  assert.match(src,/hw=await restoreCircuit\(originalCircuitA\)/);
  assert.doesNotMatch(src,/setCapabilityValue\(/);
  assert.doesNotMatch(src,/triggerAdvancedFlow/);
  assert.doesNotMatch(src,/easeeVar1|easeeVar2|easeeVar3/);
});

test('fresh token is reused without refresh or Logic writes',async()=>{
  const f=fixture();
  const v=await f.readEaseeVars();
  assert.equal(await f.getAccessToken(v,false),'old-access');
  assert.deepEqual(f.calls,['GET']);
});

test('expired token rotates and persists access/refresh/expiry atomically',async()=>{
  const f=fixture({bundle:makeBundle({
    expiresAt:new Date(Date.now()-1000).toISOString()
  })});
  const v=await f.readEaseeVars();
  assert.equal(await f.getAccessToken(v,false),'new-access');
  const next=f.getState();
  assert.equal(next.accessToken,'new-access');
  assert.equal(next.refreshToken,'new-refresh');
  assert.equal(next.revision,101);
  assert.ok(Date.parse(next.expiresAt)>Date.now()+3000000);
  assert.deepEqual(f.calls,['GET','GET','REFRESH','PUT','GET']);
});

test('one-use refresh 401 recovers only from a separately rotated newer bundle',async()=>{
  let f;
  f=fixture({bundle:makeBundle({expiresAt:new Date(Date.now()-1000).toISOString()}),
    postJson:async()=>{
      f.setState(makeBundle({
        accessToken:'other-access',
        refreshToken:'other-refresh',
        revision:101
      }));
      const err=new Error('EASEE_REFRESH_HTTP_401');
      err.httpStatus=401;
      throw err;
    }
  });
  const v=await f.readEaseeVars();
  assert.equal(await f.getAccessToken(v,false),'other-access');
  assert.equal(f.calls.filter(x=>x==='REFRESH').length,1);
  assert.equal(f.calls.filter(x=>x==='PUT').length,0);
});

test('refresh 401 without a newer bundle fails closed, never retries old refresh',async()=>{
  const f=fixture({bundle:makeBundle({expiresAt:new Date(Date.now()-1000).toISOString()}),
    postJson:async()=>{
      const err=new Error('EASEE_REFRESH_HTTP_401');
      err.httpStatus=401;
      throw err;
    }
  });
  const v=await f.readEaseeVars();
  await assert.rejects(()=>f.getAccessToken(v,false),/EASEE_REFRESH_HTTP_401/);
  assert.equal(f.calls.filter(x=>x==='REFRESH').length,1);
  assert.equal(f.calls.filter(x=>x==='PUT').length,0);
});

test('missing bundle configuration and malformed bundle fail closed',async()=>{
  await assert.rejects(()=>fixture({id:'__EM2_EASEE_BUNDLE_ID__'}).readEaseeVars(),
    /EASEE_BUNDLE_NOT_CONFIGURED/);
  await assert.rejects(()=>fixture({bundle:{schema:'wrong'}}).readEaseeVars(),
    /EASEE_BUNDLE_INVALID/);
});

test('write/readback mismatch fails closed instead of certifying credentials',async()=>{
  const f=fixture({
    bundle:makeBundle({expiresAt:new Date(Date.now()-1000).toISOString()}),
    onWrite:next=>({...next,refreshToken:'unexpected-token'})
  });
  const v=await f.readEaseeVars();
  await assert.rejects(()=>f.getAccessToken(v,false),/EASEE_BUNDLE_WRITE_CONFLICT/);
  assert.equal(f.calls.filter(x=>x==='PUT').length,1);
});
