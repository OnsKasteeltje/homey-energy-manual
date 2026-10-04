import fs from 'node:fs';
import assert from 'node:assert/strict';

const IDS={intent:'intent',adapter:'adapter',gate:'gate'};
const render=p=>fs.readFileSync(p,'utf8').replace(
  'const IDS=__EMS_HEATING_IDS__;',
  'const IDS='+JSON.stringify(IDS)+';'
);
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;

const adapterSource=render('src/homey/adapters/heating-control/heating-control-v0.1.shadow.js');
const gateSource=render('src/homey/validation/heating-control-adapter-gate-v0.1.shadow.js');

assert(!adapterSource.includes('const IDS=__EMS_HEATING_IDS__;'));
assert(!gateSource.includes('const IDS=__EMS_HEATING_IDS__;'));
assert(!/setCapabilityValue|setCapabilityValues|set_devices_capabilities/.test(adapterSource));
assert(!/setCapabilityValue|setCapabilityValues|set_devices_capabilities/.test(gateSource));

new AsyncFunction('Homey',adapterSource);
new AsyncFunction('Homey',gateSource);

const now=new Date();
const generatedAt=new Date(now.getTime()-10000).toISOString();
const validUntil=new Date(now.getTime()+100000).toISOString();

const commands=['woonkamer','eetkamer','keuken','serre'].map(roomKey=>({
  roomKey,
  displayName:roomKey,
  group:['woonkamer','eetkamer'].includes(roomKey)?'living_area':null,
  opportunityId:roomKey+'|x',
  action:roomKey==='woonkamer'?'SET_TEMP':'HOLD',
  target_C:roomKey==='woonkamer'?17.5:null,
  baselineCurrentTarget_C:16,
  futureHoneywellTarget_C:19,
  scheduleChangeAt:new Date(now.getTime()+3600000).toISOString(),
  reason:'TEST',
  wouldWrite:roomKey==='woonkamer',
  physicalWrite:false,
  shadowOwnership:{
    wouldOwnOverride:roomKey==='woonkamer',
    simulatedRollback:false,
    physicalOwnershipProven:false
  }
}));

const intent={
  schema:'EMS_HEATING_CONTROL_INTENT_V0.1',
  generatedAt,
  validUntil,
  controlRevision:'hcs1-test',
  valid:true,
  status:'OK',
  readOnly:true,
  controlMode:'SHADOW',
  deviceWrites:false,
  physicalWriteAllowed:false,
  plannerAuthority:'SHADOW_ONLY',
  executor:'HOMEY_SHADOW',
  baselineAuthority:'HONEYWELL',
  commands,
  safety:{
    liveExecutionAllowed:false,
    productionPlannerHeatingGrantPresent:false,
    physicalOwnershipProven:false
  }
};

const vars={
  intent:{id:'intent',value:JSON.stringify(intent)},
  adapter:{id:'adapter',value:'{}'},
  gate:{id:'gate',value:'{}'}
};

const Homey={
  logic:{
    getVariable:async({id})=>vars[id],
    updateVariable:async({id,variable})=>{
      vars[id]={...(vars[id]||{id}),value:variable.value};
      return vars[id];
    }
  },
  devices:{
    getDevice:async({id})=>({
      id,
      capabilitiesObj:{
        target_temperature:{value:16},
        measure_temperature:{value:18}
      }
    })
  }
};

const adapterRun=new AsyncFunction('Homey',adapterSource);
assert.equal(await adapterRun(Homey),true);
const adapter=JSON.parse(vars.adapter.value);
assert.equal(adapter.schema,'EMS_HEATING_CONTROL_ADAPTER_SHADOW_V0.1');
assert.equal(adapter.valid,true);
assert.equal(adapter.physicalWriteAllowed,false);
assert.equal(adapter.deviceWrites,false);
assert.equal(adapter.commands.find(x=>x.roomKey==='woonkamer').action,'SET_TEMP');

const gateRun=new AsyncFunction('Homey',gateSource);
assert.equal(await gateRun(Homey),true);
const gate=JSON.parse(vars.gate.value);
assert.equal(gate.schema,'EMS_HEATING_CONTROL_ADAPTER_GATE_SHADOW_V0.1');
assert.equal(gate.finalStatus,'PASS');
assert.equal(gate.liveExecutionAllowed,false);
assert.equal(gate.deviceWrites,false);
assert.equal(gate.physicalWriteAllowed,false);
const living=gate.commands.find(x=>x.roomKey==='woonkamer');
assert.equal(living.edgeReadback.status,'OBSERVED');
assert.equal(living.edgeReadback.targetTemperature_C,16);
assert.equal(living.edgeReadback.physicalOwnershipProven,false);

intent.generatedAt=new Date(now.getTime()-300000).toISOString();
vars.intent.value=JSON.stringify(intent);
assert.equal(await adapterRun(Homey),false);
const staleAdapter=JSON.parse(vars.adapter.value);
assert.equal(staleAdapter.valid,false);
assert(staleAdapter.commands.every(x=>x.action==='HOLD'));
assert(staleAdapter.commands.every(x=>x.physicalWrite===false));

console.log('PASS: Homey Heating Adapter/Gate v0.1 SHADOW contract');
