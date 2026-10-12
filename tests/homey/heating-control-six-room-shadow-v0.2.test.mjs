import assert from 'node:assert/strict';
import fs from 'node:fs';

const IDS={intent:'intent',adapter:'adapter',gate:'gate'};
const ROOM_IDS={
  woonkamer:'6a79bb86-8c02-43db-be22-6f51e01efc6d',
  eetkamer:'dd7ef4a3-ed9f-4e4d-92bb-090502068421',
  keuken:'b7aec05b-953f-41e1-a7b4-ad09c9bf911e',
  serre:'13625cb2-8fb5-4466-a21f-7addd8d72a88',
  douwe_slaapkamer:'f74252a1-2879-4967-ba2d-41f56364e39b',
  erker_douwe:'f9db36cd-8c0f-4beb-aa28-0127597652cf'
};
const render=p=>fs.readFileSync(p,'utf8').replace(
  'const IDS=__EMS_HEATING_IDS__;',
  'const IDS='+JSON.stringify(IDS)+';'
);
const adapterText=render('src/homey/adapters/heating-control/heating-control-v0.2.six-room.shadow.js');
const gateText=render('src/homey/validation/heating-control-adapter-gate-v0.2.six-room.shadow.js');
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
assert(!adapterText.includes('const IDS=__EMS_HEATING_IDS__;'));
assert(!gateText.includes('const IDS=__EMS_HEATING_IDS__;'));
for(const text of [adapterText,gateText]){
  assert(!/setCapabilityValue|setCapabilityValues|set_devices_capabilities|runFlowCardAction/.test(text));
}
const adapterRun=new AsyncFunction('Homey',adapterText);
const gateRun=new AsyncFunction('Homey',gateText);

const now=Date.now();
const isoOffset=ms=>new Date(now+ms).toISOString();
function buildIntent(){
  const commands=Object.entries(ROOM_IDS).map(([roomKey,homeyDeviceId])=>{
    const overridden=roomKey.includes('douwe');
    return {
      roomKey,homeyDeviceId,
      displayName:roomKey,
      group:['woonkamer','eetkamer'].includes(roomKey)?'living_area':null,
      opportunityId:roomKey+'|x',
      action:roomKey==='woonkamer'?'SET_TEMP':'HOLD',
      sourceShadowAction:roomKey==='woonkamer'?'SET_TEMP':'HOLD',
      target_C:roomKey==='woonkamer'?16.5:null,
      baselineCurrentTarget_C:16,
      futureHoneywellTarget_C:18,
      scheduleChangeAt:overridden?null:isoOffset(3600000),
      reason:overridden?'HONEYWELL_OVERRIDE_ACTIVE':'TEST',
      holdReason:overridden?'HONEYWELL_OVERRIDE_ACTIVE':null,
      vendorSetpointMode:overridden?'permanent_override':'follow_schedule',
      vendorSystemMode:'auto',
      vendorTarget_C:16,
      vendorOverrideUntil:null,
      wouldWrite:roomKey==='woonkamer',
      physicalWrite:false,
      shadowOwnership:{
        wouldOwnOverride:roomKey==='woonkamer',
        simulatedRollback:false,
        physicalOwnershipProven:false
      }
    };
  });
  return {
    schema:'EMS_HEATING_CONTROL_INTENT_V0.2',generatedAt:isoOffset(-10000),
    validUntil:isoOffset(100000),controlRevision:'hcs2-test',
    valid:true,status:'OK',readOnly:true,controlMode:'SHADOW',
    deviceWrites:false,physicalWriteAllowed:false,liveExecutionAllowed:false,
    plannerAuthority:'SHADOW_ONLY',executor:'HOMEY_SHADOW',
    baselineAuthority:'HONEYWELL',commands,
    safety:{
      liveExecutionAllowed:false,
      productionPlannerHeatingGrantPresent:false,
      physicalOwnershipProven:false
    }
  };
}
const intent=buildIntent();
const vars={
  intent:{id:'intent',value:JSON.stringify(intent)},
  adapter:{id:'adapter',value:'{}'},
  gate:{id:'gate',value:'{}'}
};
let readIds=[];
let logicWrites=0;
const Homey={
  logic:{
    getVariable:async({id})=>vars[id],
    updateVariable:async({id,variable})=>{
      logicWrites++;
      vars[id]={...(vars[id]||{id}),value:variable.value};
      return vars[id];
    }
  },
  devices:{
    getDevice:async({id})=>{
      readIds.push(id);
      return {id,capabilitiesObj:{
        target_temperature:{value:16},
        measure_temperature:{value:18}
      }};
    }
  }
};
const runAdapter=async next=>{
  vars.intent.value=JSON.stringify(next);
  return await adapterRun(Homey);
};
assert.equal(await runAdapter(intent),true);
const adapter=JSON.parse(vars.adapter.value);
assert.equal(adapter.schema,'EMS_HEATING_CONTROL_ADAPTER_SHADOW_V0.2');
assert.equal(adapter.commands.length,6);
assert.equal(adapter.valid,true);
assert.equal(adapter.physicalWriteAllowed,false);
assert.equal(adapter.deviceWrites,false);
assert.equal(adapter.liveExecutionAllowed,false);
assert(adapter.commands.every(c=>c.physicalWrite===false));
assert.equal(adapter.commands.find(c=>c.roomKey==='woonkamer').action,'SET_TEMP');
for(const key of ['douwe_slaapkamer','erker_douwe']){
  const c=adapter.commands.find(c=>c.roomKey===key);
  assert.equal(c.action,'HOLD');
  assert.equal(c.holdReason,'HONEYWELL_OVERRIDE_ACTIVE');
  assert.equal(c.deviceId,ROOM_IDS[key]);
}
assert.equal(await gateRun(Homey),true);
const gate=JSON.parse(vars.gate.value);
assert.equal(gate.schema,'EMS_HEATING_CONTROL_ADAPTER_GATE_SHADOW_V0.2');
assert.equal(gate.finalStatus,'PASS');
assert.equal(gate.commands.length,6);
assert.equal(gate.deviceWrites,false);
assert.equal(gate.physicalWriteAllowed,false);
assert.equal(gate.liveExecutionAllowed,false);
assert.deepEqual(readIds,[ROOM_IDS.woonkamer]); // Only prospective non-HOLD gets targeted read
assert(gate.commands.every(c=>c.physicalWrite===false));
assert(gate.commands.filter(c=>c.roomKey.includes('douwe')).every(c=>c.edgeReadback.status==='NOT_REQUIRED'));
assert.equal(gate.commands.find(c=>c.roomKey==='woonkamer').edgeReadback.status,'OBSERVED');
assert.equal(logicWrites,2); // Two SHADOW Logic outputs, no device writes

const fake=JSON.parse(JSON.stringify(intent));
fake.commands.find(c=>c.roomKey==='douwe_slaapkamer').action='SET_TEMP';
fake.commands.find(c=>c.roomKey==='douwe_slaapkamer').target_C=16.5;
assert.equal(await runAdapter(fake),false);
let blocked=JSON.parse(vars.adapter.value);
assert.equal(blocked.valid,false);
assert(blocked.commands.every(c=>c.action==='HOLD'));
assert(blocked.errors.some(e=>e.includes('HUMANOVERRIDEHOLD')));
assert.equal(await gateRun(Homey),false);
assert.equal(JSON.parse(vars.gate.value).finalStatus,'FAIL');

const missing=JSON.parse(JSON.stringify(intent));
missing.commands.pop();
assert.equal(await runAdapter(missing),false);
assert(JSON.parse(vars.adapter.value).checks.commands===false);

const duplicate=JSON.parse(JSON.stringify(intent));
duplicate.commands[5].roomKey='woonkamer';
assert.equal(await runAdapter(duplicate),false);
assert(JSON.parse(vars.adapter.value).errors.some(e=>e.includes('UNIQUE')));

const wrongId=JSON.parse(JSON.stringify(intent));
wrongId.commands.find(c=>c.roomKey==='erker_douwe').homeyDeviceId='wrong';
assert.equal(await runAdapter(wrongId),false);
assert(JSON.parse(vars.adapter.value).errors.some(e=>e.includes('PINNEDID')));

const stale=JSON.parse(JSON.stringify(intent));
stale.generatedAt=isoOffset(-300000);
assert.equal(await runAdapter(stale),false);
assert(JSON.parse(vars.adapter.value).commands.every(c=>c.action==='HOLD'));

const live=JSON.parse(JSON.stringify(intent));
live.liveExecutionAllowed=true;
assert.equal(await runAdapter(live),false);
assert(JSON.parse(vars.adapter.value).commands.every(c=>c.physicalWrite===false));

console.log('PASS: Homey six-room Heating Adapter/Gate V0.2 SHADOW, six IDs, Douwe HOLD, no device writes');
