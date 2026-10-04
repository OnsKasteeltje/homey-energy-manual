// EM v2 | 60 Adapter | Heating Control v0.1 SHADOW
// Translation/validation only. Writes one Logic output; never writes a device.
// __EMS_HEATING_IDS__ is replaced once by the controlled commissioning renderer.

const VERSION='EMS_HEATING_CONTROL_ADAPTER_SHADOW_V0.1';
const INTENT_SCHEMA='EMS_HEATING_CONTROL_INTENT_V0.1';
const FRESH_MS=120000;
const IDS=__EMS_HEATING_IDS__;

const ROOM_DEVICES={
  woonkamer:'6a79bb86-8c02-43db-be22-6f51e01efc6d',
  eetkamer:'dd7ef4a3-ed9f-4e4d-92bb-090502068421',
  keuken:'b7aec05b-953f-41e1-a7b4-ad09c9bf911e',
  serre:'13625cb2-8fb5-4466-a21f-7addd8d72a88'
};
const ALLOWED_ACTIONS=new Set(['HOLD','SET_TEMP','KEEP_TEMP','RESET_TO_SCHEDULE']);

const parse=v=>{try{return JSON.parse(String(v??''));}catch{return null;}};
const num=v=>{if(v===null||v===undefined||v==='')return null;const n=Number(v);return Number.isFinite(n)?n:null;};
const age=v=>{const t=Date.parse(String(v||''));return Number.isFinite(t)?Date.now()-t:Infinity;};

const [intentVar,outVar]=await Promise.all([
  Homey.logic.getVariable({id:IDS.intent}),
  Homey.logic.getVariable({id:IDS.adapter})
]);
if(!outVar)return false;

const intent=parse(intentVar?.value);
const intentAgeMs=age(intent?.generatedAt);
const validUntilMs=Date.parse(String(intent?.validUntil||''));
const fresh=intentAgeMs>=0&&intentAgeMs<=FRESH_MS;
const withinValidity=Number.isFinite(validUntilMs)&&Date.now()<validUntilMs;

const topChecks={
  schema:intent?.schema===INTENT_SCHEMA,
  valid:intent?.valid===true&&intent?.status==='OK',
  shadow:intent?.readOnly===true&&intent?.controlMode==='SHADOW',
  noWrites:intent?.deviceWrites===false&&intent?.physicalWriteAllowed===false,
  authority:
    intent?.plannerAuthority==='SHADOW_ONLY'&&
    intent?.executor==='HOMEY_SHADOW'&&
    intent?.baselineAuthority==='HONEYWELL',
  liveBlocked:
    intent?.liveExecutionAllowed===false&&
    intent?.safety?.liveExecutionAllowed===false&&
    intent?.safety?.productionPlannerHeatingGrantPresent===false&&
    intent?.safety?.physicalOwnershipProven===false,
  fresh,
  withinValidity,
  controlRevision:typeof intent?.controlRevision==='string'&&intent.controlRevision.length>0,
  commands:Array.isArray(intent?.commands)&&intent.commands.length===4
};

let commandErrors=[];
let commands=[];

if(Array.isArray(intent?.commands)){
  const seen=new Set();
  for(const src of intent.commands){
    const key=String(src?.roomKey||'');
    const action=String(src?.action||'');
    const target=num(src?.target_C);
    const current=num(src?.baselineCurrentTarget_C);
    const future=num(src?.futureHoneywellTarget_C);
    const scheduleAt=Date.parse(String(src?.scheduleChangeAt||''));
    const deviceId=ROOM_DEVICES[key]||null;
    const actionOK=ALLOWED_ACTIONS.has(action);
    const targetOK=
      action==='SET_TEMP'||action==='KEEP_TEMP'
        ? target!==null&&current!==null&&future!==null&&target>current&&target<=future
        : target===null;
    const sourceWriteSafe=src?.physicalWrite===false;
    const ownershipSafe=src?.shadowOwnership?.physicalOwnershipProven===false;
    const ownershipSemantics=
      action==='SET_TEMP'||action==='KEEP_TEMP'
        ? src?.shadowOwnership?.wouldOwnOverride===true&&
          src?.shadowOwnership?.simulatedRollback===false
        : action==='RESET_TO_SCHEDULE'
          ? src?.shadowOwnership?.simulatedRollback===true&&
            src?.shadowOwnership?.wouldOwnOverride===false
          : true;
    const unique=!seen.has(key);
    if(key)seen.add(key);

    const checks={
      room:!!deviceId,
      unique,
      action:actionOK,
      target:targetOK,
      schedule:Number.isFinite(scheduleAt),
      sourceWriteSafe,
      ownershipSafe,
      ownershipSemantics
    };
    const errors=Object.entries(checks).filter(([,ok])=>!ok).map(([name])=>name.toUpperCase());
    commandErrors=commandErrors.concat(errors.map(e=>(key||'UNKNOWN')+':'+e));

    commands.push({
      roomKey:key,
      deviceId,
      action:errors.length?'HOLD':action,
      requestedTarget_C:errors.length?null:target,
      scheduleChangeAt:Number.isFinite(scheduleAt)?src.scheduleChangeAt:null,
      opportunityId:src?.opportunityId??null,
      reason:src?.reason??null,
      wouldWrite:errors.length?false:src?.wouldWrite===true,
      physicalWrite:false,
      checks,
      errors,
      futureWriter:'HOMEY_HONEYWELL_ACTUATOR_ONLY'
    });
  }
}

const errors=[
  ...Object.entries(topChecks).filter(([,ok])=>!ok).map(([name])=>name.toUpperCase()),
  ...commandErrors
];
const valid=errors.length===0;

if(!valid){
  commands=commands.map(c=>({
    ...c,
    action:'HOLD',
    requestedTarget_C:null,
    wouldWrite:false,
    physicalWrite:false
  }));
}

const out={
  schema:VERSION,
  generatedAt:new Date().toISOString(),
  sourceGeneratedAt:intent?.generatedAt??null,
  sourceControlRevision:String(intent?.controlRevision||''),
  valid,
  status:valid?'PASS':'FAIL_CLOSED',
  readOnly:true,
  controlMode:'SHADOW',
  deviceWrites:false,
  physicalWriteAllowed:false,
  liveExecutionAllowed:false,
  checks:topChecks,
  errors,
  commands,
  safety:{
    failClosed:true,
    targetedLogicReadsOnly:true,
    deviceReads:false,
    logicWrites:true,
    deviceWrites:false,
    physicalOwnershipProven:false,
    productionPlannerHeatingGrantPresent:false,
    singlePhysicalWriterRequired:true
  }
};

const value=JSON.stringify(out);
if(outVar.value!==value){
  await Homey.logic.updateVariable({id:IDS.adapter,variable:{value}});
}
return valid;
