// EM v2 | 80 Validation | Heating Control Gate v0.1 SHADOW
// Validates the Homey edge contract and performs targeted thermostat READS only.
// It writes one Logic result and cannot change a Honeywell capability.
// __EMS_HEATING_IDS__ is replaced once by the controlled commissioning renderer.

const VERSION='EMS_HEATING_CONTROL_ADAPTER_GATE_SHADOW_V0.1';
const INTENT_SCHEMA='EMS_HEATING_CONTROL_INTENT_V0.1';
const ADAPTER_SCHEMA='EMS_HEATING_CONTROL_ADAPTER_SHADOW_V0.1';
const FRESH_MS=120000;
const IDS=__EMS_HEATING_IDS__;

const parse=v=>{try{return JSON.parse(String(v??''));}catch{return null;}};
const num=v=>{if(v===null||v===undefined||v==='')return null;const n=Number(v);return Number.isFinite(n)?n:null;};
const age=v=>{const t=Date.parse(String(v||''));return Number.isFinite(t)?Date.now()-t:Infinity;};
const cap=(device,name)=>{
  const obj=device?.capabilitiesObj?.[name];
  if(obj&&Object.prototype.hasOwnProperty.call(obj,'value'))return obj.value;
  return null;
};

const [intentVar,adapterVar,gateVar]=await Promise.all([
  Homey.logic.getVariable({id:IDS.intent}),
  Homey.logic.getVariable({id:IDS.adapter}),
  Homey.logic.getVariable({id:IDS.gate})
]);
if(!gateVar)return false;

const intent=parse(intentVar?.value);
const adapter=parse(adapterVar?.value);
const intentAge=age(intent?.generatedAt);
const adapterAge=age(adapter?.generatedAt);
const intentFresh=intentAge>=0&&intentAge<=FRESH_MS;
const adapterFresh=adapterAge>=0&&adapterAge<=FRESH_MS;
const validUntilMs=Date.parse(String(intent?.validUntil||''));

const checks={
  schema:
    intent?.schema===INTENT_SCHEMA&&
    adapter?.schema===ADAPTER_SCHEMA,
  sourceValid:
    intent?.valid===true&&intent?.status==='OK'&&
    adapter?.valid===true&&adapter?.status==='PASS',
  revision:
    typeof intent?.controlRevision==='string'&&
    intent.controlRevision.length>0&&
    adapter?.sourceControlRevision===intent.controlRevision,
  fresh:intentFresh&&adapterFresh,
  withinValidity:Number.isFinite(validUntilMs)&&Date.now()<validUntilMs,
  shadow:
    intent?.controlMode==='SHADOW'&&
    adapter?.controlMode==='SHADOW',
  noWrites:
    intent?.deviceWrites===false&&
    intent?.physicalWriteAllowed===false&&
    adapter?.deviceWrites===false&&
    adapter?.physicalWriteAllowed===false&&
    adapter?.liveExecutionAllowed===false,
  noProductionGrant:
    intent?.safety?.productionPlannerHeatingGrantPresent===false&&
    adapter?.safety?.productionPlannerHeatingGrantPresent===false,
  ownershipUnproven:
    intent?.safety?.physicalOwnershipProven===false&&
    adapter?.safety?.physicalOwnershipProven===false
};

let commandErrors=[];
const evaluated=[];

for(const cmd of Array.isArray(adapter?.commands)?adapter.commands:[]){
  const action=String(cmd?.action||'HOLD');
  const requiresRead=action!=='HOLD';
  let readback={
    required:requiresRead,
    status:requiresRead?'PENDING':'NOT_REQUIRED',
    targetTemperature_C:null,
    measureTemperature_C:null,
    physicalOwnershipProven:false
  };

  if(requiresRead){
    try{
      const device=await Homey.devices.getDevice({id:cmd.deviceId});
      const target=num(cap(device,'target_temperature'));
      const measured=num(cap(device,'measure_temperature'));
      readback={
        required:true,
        status:target===null?'CAPABILITY_MISSING':'OBSERVED',
        targetTemperature_C:target,
        measureTemperature_C:measured,
        physicalOwnershipProven:false
      };
      if(target===null)commandErrors.push(cmd.roomKey+':READBACK_TARGET_MISSING');
    }catch(e){
      readback={
        required:true,
        status:'READ_FAILED',
        targetTemperature_C:null,
        measureTemperature_C:null,
        physicalOwnershipProven:false,
        error:String(e?.message||e).slice(0,160)
      };
      commandErrors.push(cmd.roomKey+':READBACK_FAILED');
    }
  }

  const commandSafe=
    cmd?.physicalWrite===false&&
    ['HOLD','SET_TEMP','KEEP_TEMP','RESET_TO_SCHEDULE'].includes(action)&&
    (
      action==='SET_TEMP'||action==='KEEP_TEMP'
        ? Number.isFinite(num(cmd?.requestedTarget_C))
        : cmd?.requestedTarget_C===null
    );
  if(!commandSafe)commandErrors.push((cmd?.roomKey||'UNKNOWN')+':COMMAND_INVALID');

  evaluated.push({
    roomKey:cmd?.roomKey??null,
    deviceId:cmd?.deviceId??null,
    action:commandSafe?action:'HOLD',
    requestedTarget_C:commandSafe?cmd?.requestedTarget_C:null,
    scheduleChangeAt:cmd?.scheduleChangeAt??null,
    opportunityId:cmd?.opportunityId??null,
    wouldWrite:commandSafe&&cmd?.wouldWrite===true,
    physicalWrite:false,
    edgeReadback:readback
  });
}

checks.commands=
  Array.isArray(adapter?.commands)&&
  adapter.commands.length===4&&
  commandErrors.length===0;

const errors=[
  ...Object.entries(checks).filter(([,ok])=>!ok).map(([name])=>name.toUpperCase()),
  ...commandErrors
];

const out={
  schema:VERSION,
  generatedAt:new Date().toISOString(),
  sourceControlRevision:String(intent?.controlRevision||''),
  adapterControlRevision:String(adapter?.sourceControlRevision||''),
  finalStatus:errors.length?'FAIL':'PASS',
  checks,
  errors,
  commands:evaluated,
  readOnly:true,
  controlMode:'SHADOW',
  deviceWrites:false,
  physicalWriteAllowed:false,
  liveExecutionAllowed:false,
  authority:{
    plannerAuthority:'SHADOW_ONLY',
    executor:'HOMEY_SHADOW',
    baselineAuthority:'HONEYWELL',
    singlePhysicalWriterRequired:true,
    physicalWriter:'NOT_PRESENT'
  },
  safety:{
    failClosed:true,
    targetedDeviceReadsOnly:true,
    logicWrites:true,
    deviceWrites:false,
    physicalOwnershipProven:false,
    productionPlannerHeatingGrantPresent:false,
    actuatorPresent:false
  },
  promotion:{
    blocked:true,
    reasons:[
      'PRODUCTION_DYNAMIC_PLANNER_HEATING_GRANT',
      'HOMEY_ACTUATOR_ACK_AND_HONEYWELL_READBACK'
    ]
  }
};

const value=JSON.stringify(out);
if(gateVar.value!==value){
  await Homey.logic.updateVariable({id:IDS.gate,variable:{value}});
}
return out.finalStatus==='PASS';
