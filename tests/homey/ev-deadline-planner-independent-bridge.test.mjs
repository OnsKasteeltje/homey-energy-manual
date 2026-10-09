// Offline Homey Bridge deadline-only contract regression.
// Run: node tests/homey/ev-deadline-planner-independent-bridge.test.mjs
// No Homey connection, EV actuator, Pi call, device write or live state changes.
import {readFileSync} from 'node:fs';
import {strict as assert} from 'node:assert';
import {resolve} from 'node:path';

const code=readFileSync(resolve('apps/homey/control/ev/pi-dynamic-planner-bridge-v1.5.9.adaptive-upscale.js'),'utf8');
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
const run=new AsyncFunction('Homey','fetch',code);
const IDS={
  selector:'ba9c22ba-4332-4b19-9bda-dfe476862176',
  state:'8e1efbb0-7999-494c-9429-7d274afacd79',
  intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',
  diag:'14e6c83f-e881-4ad5-8876-af1ce9e2a1a1'
};
const iso=t=>new Date(t).toISOString();

function command(changes={}){
  const now=Date.now();
  const base={
    schema:'EMS_PI_CONTROL_COMMAND_V0.1',
    status:'READY',readyForCutover:true,
    executionMode:'DEADLINE_ONLY',
    planner:{valid:false,reason:'PLAN_STALE'},
    plannerOwner:'PI',executor:'HOMEY',
    contract:{mode:'FIXED',id:'ENGIE_3Y_2026_2029'},
    validUntil:iso(now+90000),
    targets:{
      ev:{target_W:0,target_A:0},
      ww:{target_W:0,target_on:false},
      quooker:{mode:'OFF',target_on:false,opportunity_allowed:false},
      battery:{target_W:0}
    },
    realtime:{ev:{
      schema:'EMS_PI_EV_REALTIME_ENVELOPE_V0.4',
      allowed:false,productionConsumerAllowed:false,mode:'DISABLED'
    }},
    deadline:{
      schema:'EMS_PI_EV_DEADLINE_EXECUTION_V0.1',
      authority:'PI',valid:true,active:true,status:'TRACKING',
      requestId:'test-request',deadlineAt:iso(now+3600000),
      latestStartAt:iso(now-5000),remainingKWh:8,maxA:10
    }
  };
  return {...base,...changes};
}

async function scenario(cmd,connected=true){
  const data={
    [IDS.selector]:'PI',
    [IDS.state]:JSON.stringify({
      revision:1,tesla:{connected,chargeState:connected?'plugged_in_paused':'plugged_out'}
    }),
    [IDS.intent]:'{}',
    [IDS.diag]:'{}'
  };
  const Homey={
    logic:{
      getVariable:async ({id})=>({id,value:data[id]}),
      updateVariable:async ({id,variable})=>{data[id]=variable.value;}
    },
    devices:{getDevice:async()=>({settings:{phaseMode:3},capabilitiesObj:{}})}
  };
  const fetch=async()=>({ok:true,json:async()=>cmd});
  await run(Homey,fetch);
  return JSON.parse(data[IDS.intent]);
}

const urgent=await scenario(command());
assert.equal(urgent.valid,true);
assert.equal(urgent.status,'OK');
assert.equal(urgent.targets.ev.status,'NUMERIC_DEADLINE_TARGET');
assert.equal(urgent.targets.ev.phase_mode,'3P');
assert.equal(urgent.targets.ev.phase_requested_A,10);
assert.equal(urgent.targets.ev.target_W,6900);
assert.equal(urgent.targets.ww.target_on,false);
assert.equal(urgent.targets.quooker.mode,'OFF');
console.log('PASS: urgent deadline makes a 3P/10A intent despite stale planner');

const disconnected=await scenario(command(),false);
assert.equal(disconnected.targets.ev.target_W,0);
assert.equal(disconnected.targets.ev.phase_mode,'OFF');
console.log('PASS: disconnected car cannot start deadline charge');

const unsafeWW=await scenario(command({targets:{
  ...command().targets,ww:{target_W:1600,target_on:true}
}}));
assert.equal(unsafeWW.valid,false);
assert.equal(unsafeWW.targets.ev.target_W,0);
console.log('PASS: deadline-only contract cannot enable WW');

const unsafePV=await scenario(command({realtime:{ev:{
  schema:'EMS_PI_EV_REALTIME_ENVELOPE_V0.4',
  allowed:true,productionConsumerAllowed:true,mode:'PV_OPPORTUNITY'
}}}));
assert.equal(unsafePV.valid,false);
assert.equal(unsafePV.targets.ev.target_W,0);
console.log('PASS: deadline-only contract cannot enable opportunistic PV');

const invalidDeadline=await scenario(command({deadline:{
  ...command().deadline,active:false
}}));
assert.equal(invalidDeadline.valid,false);
console.log('PASS: inactive deadline cannot enable fallback');
