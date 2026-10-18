import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const maintenance=fs.readFileSync('apps/homey/control/ev/easee-auth-maintenance-v0.1.homeyscript.js','utf8');
const writer=fs.readFileSync('apps/homey/control/ev/ev-power-v0.4.7.atomic-easee-tokens.js','utf8');

const expired=()=>new Date(Date.now()-60000).toISOString();
const soon=()=>new Date(Date.now()+5*60000).toISOString();
const far=()=>new Date(Date.now()+50*60000).toISOString();
const bundle=expiresAt=>({schema:'EM2_EASEE_TOKEN_BUNDLE_V1',
 accessToken:'OLD_ACCESS',refreshToken:'OLD_REFRESH',expiresAt,revision:10});
async function run({expiresAt=soon(),fetchImpl,priorAlert=null}={}){
 const BUNDLE_ID='11111111-2222-4333-8444-555555555555';
 const STATUS_ID='ea1f8a44-2f6c-490e-9b86-bae761886cf9';
 const vars={
   [BUNDLE_ID]:bundle(expiresAt),
   [STATUS_ID]:{schema:'EM2_EV_ACTUATOR_V0.4.7_PHASE_WRITER',
     status:'STABLE',reason:'OFF_ZERO_A_HOLD',
     ...(priorAlert?{authAlert:priorAlert}:{})}
 };
 const calls=[];
 const Homey={
  logic:{
   getVariable:async({id})=>({value:JSON.stringify(vars[id])}),
   updateVariable:async({id,variable})=>{
     calls.push('LOGIC_WRITE:'+id);
     vars[id]=JSON.parse(variable.value);
   }
  },
  users:{getUsers:async()=>({x:{id:'x',athomId:'y',role:'owner'}})},
  flow:{runFlowCardAction:async data=>{calls.push('PUSH:'+data.id);return true;}}
 };
 const source=maintenance.replace('__EM2_EASEE_BUNDLE_ID__',BUNDLE_ID);
 const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
 const main=new AsyncFunction('Homey','fetch',source);
 const result=await main(Homey,async(url,options)=>{
    calls.push('REFRESH');
    return fetchImpl?fetchImpl(url,options):{
      ok:true,status:200,
      json:async()=>({accessToken:'NEW_ACCESS',refreshToken:'NEW_REFRESH',expiresIn:3600})};
 });
 return {result,calls,vars,BUNDLE_ID,STATUS_ID};
}
test('maintenance is auth-only and same Homey bundle contract',()=>{
 assert.match(maintenance,/EARLY_REFRESH_MS=20\*60\*1000/);
 assert.match(maintenance,/refresh_token/);
 assert.doesNotMatch(maintenance,/setDynamicChargerCurrent|pauseCharging|resumeCharging|circuitCurrentControl|set_phase_mode|triggerAdvancedFlow/);
 assert.match(writer,/easeeCloudAuthenticatedAt/);
 assert.match(writer,/stickyAlert/);
 assert.match(writer,/prior\?\.active===true/);
});
test('valid token requires no HTTP or writes',async()=>{
 const r=await run({expiresAt:far()});
 assert.equal(r.result,true);
 assert.deepEqual(r.calls,[]);
});
test('near-expiry token refreshes the atomic bundle without physical commands',async()=>{
 const r=await run();
 assert.equal(r.result,true);
 assert.equal(r.calls.filter(x=>x==='REFRESH').length,1);
 assert.equal(r.vars[r.BUNDLE_ID].revision,11);
 assert.equal(r.vars[r.BUNDLE_ID].accessToken,'NEW_ACCESS');
 assert.equal(r.vars[r.BUNDLE_ID].refreshToken,'NEW_REFRESH');
 assert.equal(r.vars[r.STATUS_ID].status,'STABLE');
 assert.equal(r.vars[r.STATUS_ID].authMaintenance.result,'REFRESHED');
});
test('401 persists sticky alert and sends one owner push',async()=>{
 const denied=async()=>({ok:false,status:401});
 const r=await run({expiresAt:expired(),fetchImpl:denied});
 assert.equal(r.result,false);
 assert.equal(r.vars[r.BUNDLE_ID].revision,10);
 assert.equal(r.vars[r.STATUS_ID].authAlert.code,'EASEE_REFRESH_HTTP_401');
 assert.equal(r.vars[r.STATUS_ID].authAlert.active,true);
 assert.equal(r.calls.filter(x=>x.startsWith('PUSH:')).length,1);
 assert.equal(r.vars[r.STATUS_ID].status,'STABLE');
});
test('401 deduplicates prior delivered alert even if physical writer is STABLE',async()=>{
 const denied=async()=>({ok:false,status:401});
 const priorAlert={active:true,delivered:true,code:'EASEE_REFRESH_HTTP_401',
   attemptedAt:new Date().toISOString()};
 const r=await run({expiresAt:expired(),fetchImpl:denied,priorAlert});
 assert.equal(r.result,false);
 assert.equal(r.calls.filter(x=>x.startsWith('PUSH:')).length,0);
 assert.equal(r.vars[r.STATUS_ID].authAlert.deduped,true);
});
test('successful authenticated refresh resolves previous alert',async()=>{
 const priorAlert={active:true,delivered:true,code:'EASEE_REFRESH_HTTP_401'};
 const r=await run({priorAlert});
 assert.equal(r.result,true);
 assert.equal(r.vars[r.STATUS_ID].authAlert.active,false);
 assert.equal(r.vars[r.STATUS_ID].authAlert.resolution,'EASEE_REFRESH_HTTP_SUCCESS');
});
test('refresh POST contract has both tokens, no Authorization Bearer',async()=>{
 let observed;
 await run({fetchImpl:async(url,options)=>{
   observed={url,headers:options.headers,body:JSON.parse(options.body)};
   return {ok:true,json:async()=>({
      accessToken:'NEW_ACCESS',refreshToken:'NEW_REFRESH',expiresIn:3600})};
 }});
 assert.equal(observed.url,'https://api.easee.com/api/accounts/refresh_token');
 assert.deepEqual(observed.body,{accessToken:'OLD_ACCESS',refreshToken:'OLD_REFRESH'});
 assert.equal(observed.headers.Authorization,undefined);
});

test('STABLE writer cannot erase auth alert published after writer start',async()=>{
 const start=writer.indexOf('const saveStatus=async');
 const end=writer.indexOf('const waitHardware=async',start);
 assert.ok(start>=0&&end>start);
 const submitted=[];
 const liveStatus={status:'STABLE',authAlert:{
   active:true,code:'EASEE_REFRESH_HTTP_401',delivered:true
 }};
 const context={
   VERSION:'EM2_EV_ACTUATOR_V0.4.7_PHASE_WRITER',
   PHASE_EXECUTION_ENABLED:true,
   IDS:{status:'test-status'},
   previous:{status:'STABLE'},
   parse:s=>JSON.parse(s),
   iso:()=>new Date().toISOString(),
   easeeCloudAuthenticatedAt:null,
   transitionObject:()=>({stage:'STABLE'}),
   Homey:{logic:{
     getVariable:async()=>({value:JSON.stringify(liveStatus)}),
     updateVariable:async({variable})=>submitted.push(JSON.parse(variable.value))
   }}
 };
 const fn=vm.runInNewContext(writer.slice(start,end)+'\n saveStatus',context);
 await fn('STABLE','OFF_ZERO_A_HOLD','STABLE',
   {controlRevision:'x',mode:'OFF',requestedA:0,targetW:0},
   {confirmedMode:'OFF'},null,{live:true});
 assert.equal(submitted.length,1);
 assert.equal(submitted[0].authAlert.active,true);
 assert.equal(submitted[0].authAlert.code,'EASEE_REFRESH_HTTP_401');
});

test('STABLE writer respects newer resolved alert after maintenance refresh',async()=>{
 const start=writer.indexOf('const saveStatus=async');
 const end=writer.indexOf('const waitHardware=async',start);
 const submitted=[];
 const current={authAlert:{active:false,code:'EASEE_REFRESH_HTTP_401',
    resolution:'EASEE_REFRESH_HTTP_SUCCESS'}};
 const context={
   VERSION:'EM2_EV_ACTUATOR_V0.4.7_PHASE_WRITER',
   PHASE_EXECUTION_ENABLED:true,
   IDS:{status:'test-status'},
   previous:{authAlert:{active:true,code:'EASEE_REFRESH_HTTP_401'}},
   parse:s=>JSON.parse(s),
   iso:()=>new Date().toISOString(),
   easeeCloudAuthenticatedAt:null,
   transitionObject:()=>({stage:'STABLE'}),
   Homey:{logic:{
     getVariable:async()=>({value:JSON.stringify(current)}),
     updateVariable:async({variable})=>submitted.push(JSON.parse(variable.value))
   }}
 };
 const fn=vm.runInNewContext(writer.slice(start,end)+'\n saveStatus',context);
 await fn('STABLE','OFF_ZERO_A_HOLD','STABLE',
   {controlRevision:'x',mode:'OFF',requestedA:0,targetW:0},
   {confirmedMode:'OFF'},null,{live:true});
 assert.equal(submitted[0].authAlert.active,false);
 assert.equal(submitted[0].authAlert.resolution,'EASEE_REFRESH_HTTP_SUCCESS');
});

test('normal actuator status updates retain newest independent auth-maintenance record',async()=>{
 const start=writer.indexOf('const saveStatus=async');
 const end=writer.indexOf('const waitHardware=async',start);
 assert.ok(start>=0&&end>start);
 const maintenance={schema:'EMS_EASEE_AUTH_MAINTENANCE_V0.1',
   at:'2026-10-18T19:00:00Z',result:'REFRESHED',revision:42};
 const published=[];
 const context={
   VERSION:'EM2_EV_ACTUATOR_V0.4.7_PHASE_WRITER',
   PHASE_EXECUTION_ENABLED:true,
   IDS:{status:'test-status'},
   previous:{status:'STABLE',authMaintenance:{result:'OLDER',revision:41}},
   parse:s=>JSON.parse(s),iso:()=>new Date().toISOString(),
   easeeCloudAuthenticatedAt:null,
   transitionObject:()=>({stage:'STABLE'}),
   Homey:{logic:{
     getVariable:async()=>({value:JSON.stringify({status:'STABLE',authMaintenance:maintenance})}),
     updateVariable:async({variable})=>published.push(JSON.parse(variable.value))
   }}
 };
 const fn=vm.runInNewContext(writer.slice(start,end)+'\n saveStatus',context);
 await fn('STABLE','OFF_ZERO_A_HOLD','STABLE',
   {controlRevision:'x',mode:'OFF',requestedA:0,targetW:0},
   {confirmedMode:'OFF'},null,{live:true});
 assert.equal(published.length,1);
 assert.deepEqual(published[0].authMaintenance,maintenance);
 assert.equal(published[0].status,'STABLE');
 assert.equal(published[0].reason,'OFF_ZERO_A_HOLD');
});
