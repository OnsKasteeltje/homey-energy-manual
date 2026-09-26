// EV Power Adapter v0.2.0 PHASE-AWARE
// Pure translation/validation. No physical writes.

const VERSION='EM2_EV_POWER_ADAPTER_V0.2';
const MAPPING='PHASE_MODE_A_230V_V0.1';
const FRESH_MS=120000;
const MIN_A=6,MAX_OPPORTUNITY_A=16,VOLTAGE_V=230;

const IDS={
  intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',
  state:'8e1efbb0-7999-494c-9429-7d274afacd79',
  maxA:'4a7398bb-9253-49ab-8850-820d1a622bd6',
  output:'f2118322-d59d-4aa8-b478-234effc3983c'
};

const [intentVar,stateVar,maxVar,outVar]=await Promise.all([
  Homey.logic.getVariable({id:IDS.intent}),
  Homey.logic.getVariable({id:IDS.state}),
  Homey.logic.getVariable({id:IDS.maxA}),
  Homey.logic.getVariable({id:IDS.output})
]);

const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};
const age=x=>{const t=Date.parse(String(x||''));return Number.isFinite(t)?Date.now()-t:Infinity;};

const intent=parse(intentVar?.value);
const state=parse(stateVar?.value);
const ev=intent?.targets?.ev||{};

const targetW=num(ev?.target_W);
const mode=String(ev?.phase_mode||'OFF');
const requestedA=num(ev?.phase_requested_A);
const requestedW=num(ev?.phase_requested_W);
const phaseSchema=String(ev?.phase_control_schema||'');
const phaseAuthoritative=ev?.phase_control_authoritative===true;
const controlRevision=String(intent?.controlRevision||'');

const targetStatus=String(ev?.status??'');
const targetSource=String(ev?.source??'');
const deadlineTarget=
  targetStatus==='NUMERIC_DEADLINE_TARGET' ||
  targetSource==='REMAINING_KWH_OVER_TIME_TO_DEADLINE';

const maxConfig=num(maxVar?.value);
const deadlineCapA=Math.floor(Math.min(16,maxConfig??16));
const maxA=deadlineTarget?deadlineCapA:MAX_OPPORTUNITY_A;

const intentAgeMs=age(intent?.generatedAt);
const stateAgeMs=age(state?.sampledAt);
const intentFresh=intentAgeMs>=0&&intentAgeMs<=FRESH_MS;
const stateFresh=stateAgeMs>=0&&stateAgeMs<=FRESH_MS;

const modeAllowed=['OFF','1P','3P'].includes(mode);
const ampRangeOK=
  Number.isInteger(requestedA) &&
  requestedA>=0 &&
  requestedA<=maxA &&
  (mode==='OFF'?requestedA===0:requestedA>=MIN_A);

const expectedW=
  mode==='1P'&&Number.isInteger(requestedA)?requestedA*VOLTAGE_V:
  mode==='3P'&&Number.isInteger(requestedA)?requestedA*3*VOLTAGE_V:
  0;

const powerAligned=
  Number.isInteger(targetW) &&
  Number.isInteger(requestedW) &&
  targetW===requestedW &&
  requestedW===expectedW;

const aligned=
  intent?.schema==='EM2_POWER_INTENT_V0.2' &&
  intent?.valid===true &&
  intent?.status==='OK' &&
  intent?.readOnly===true &&
  intent?.deviceWrites===false &&
  phaseSchema==='EM2_EV_PHASE_CONTROL_V0.1' &&
  phaseAuthoritative &&
  !!controlRevision;

let valid=false,status='INVALID_PHASE_CONTROL',reason='Phase-aware control contract invalid';

if(!aligned){
  status='SEMANTIC_OR_SCHEMA_MISMATCH';
  reason='Power Intent / phase control schema invalid';
}else if(!intentFresh){
  status='STALE_INTENT';
  reason='Power Intent stale';
}else if(!modeAllowed){
  status='INVALID_PHASE_MODE';
  reason='Phase mode must be OFF, 1P or 3P';
}else if(!ampRangeOK){
  status='INVALID_PHASE_CURRENT';
  reason='Phase current outside executable range';
}else if(!powerAligned){
  status='PHASE_POWER_MISMATCH';
  reason='target_W must equal phase mode × requested current × 230V';
}else{
  valid=true;
  status=mode==='OFF'?'ZERO_INTENT':'EXECUTABLE';
  reason=mode==='OFF'
    ?'OFF + 0 A'
    :`${mode} + ${requestedA} A -> ${requestedW} W`;
}

const legacyShadow={
  schema:String(ev?.phase_shadow_schema||''),
  mode:String(ev?.phase_mode_shadow||'OFF'),
  requested_A:num(ev?.phase_requested_A_shadow),
  observabilityOnly:true
};

const out={
  schema:VERSION,
  generatedAt:new Date().toISOString(),
  sourceRevision:num(intent?.sourceRevision),
  stateRevision:num(state?.revision),
  controlRevision,
  inputSchema:String(intent?.schema||''),
  valid,
  status,
  reason,
  readOnly:true,
  deviceWrites:false,
  input:{
    target_W:targetW,
    targetStatus,
    targetSource,
    phaseSchema,
    phaseAuthoritative,
    mode,
    requested_A:requestedA,
    requested_W:requestedW,
    intentAgeSec:Math.round(intentAgeMs/1000),
    stateAgeSec:Math.round(stateAgeMs/1000)
  },
  electrical:{
    voltage_V:VOLTAGE_V,
    phase_count:mode==='1P'?1:mode==='3P'?3:0,
    w_per_A:mode==='1P'?VOLTAGE_V:mode==='3P'?3*VOLTAGE_V:0,
    min_A:MIN_A,
    max_A:maxA,
    deadline_cap_A:deadlineCapA,
    opportunity_max_A:MAX_OPPORTUNITY_A,
    executable_W:valid?expectedW:0
  },
  command:{
    schema:'EM2_EV_PHASE_COMMAND_V0.1',
    mode:valid?mode:'OFF',
    requested_A:valid?requestedA:0,
    requested_W:valid?expectedW:0,
    physicalPhaseOwner:'EASEE_EQUALIZER',
    physicalWrite:false
  },
  legacyPhaseShadow:legacyShadow,
  ownership:{
    policy:'PI_POWER_INTENT',
    translation:'EV_POWER_ADAPTER_V0.2',
    physicalWriter:'EV_ACTUATOR_ONLY'
  },
  safety:{
    failClosed:true,
    intentFresh,
    stateFresh,
    stateObservabilityOnly:true,
    semanticTokenGuard:true,
    exactPhasePowerMapping:true,
    mappingRevision:MAPPING,
    noDeviceWrites:true
  }
};

const value=JSON.stringify(out);
if(outVar?.value!==value){
  await Homey.logic.updateVariable({id:IDS.output,variable:{value}});
}
return out.valid;
