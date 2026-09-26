// Exact source captured from LIVE Homey Advanced Flow
// Flow: EM v2 | 60 Adapter | EV Power v0.1.10 STATE-RETRIGGER
// Flow ID: 953e9b18-3576-4557-b940-ed4a64eb2516
// Derived from live v0.1.9: 2026-09-25
// v0.1.10 invariant: Core/Easee chargeState is observability-only and cannot veto a fresh valid Power Intent.

// === HomeyScript card 1: 33333333-aaaa-4333-8333-333333333333 ===
// EV Power Adapter v0.1.11 PHASE-SHADOW
const IDS={intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',state:'8e1efbb0-7999-494c-9429-7d274afacd79',maxA:'4a7398bb-9253-49ab-8850-820d1a622bd6',output:'f2118322-d59d-4aa8-b478-234effc3983c'};
const [intentVar,stateVar,maxVar,outVar]=await Promise.all([Homey.logic.getVariable({id:IDS.intent}),Homey.logic.getVariable({id:IDS.state}),Homey.logic.getVariable({id:IDS.maxA}),Homey.logic.getVariable({id:IDS.output})]);
const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};const ageMs=x=>{const t=Date.parse(String(x||''));return Number.isFinite(t)?Date.now()-t:Infinity;};
const intent=parse(intentVar?.value),state=parse(stateVar?.value),prev=parse(outVar?.value),ev=intent?.targets?.ev||{};
const r=num(intent?.sourceRevision),sr=num(state?.revision),inputSchema=String(intent?.schema||''),targetW=num(ev?.target_W),targetStatus=String(ev?.status??''),targetSource=String(ev?.source??''),phaseModeShadow=String(ev?.phase_mode_shadow??'OFF'),phaseRequestedAShadow=num(ev?.phase_requested_A_shadow),phaseShadowSchema=String(ev?.phase_shadow_schema??'');
const semanticToken=()=>String(intent?.controlRevision||'')||JSON.stringify({policy:String(intent?.policyRevision||''),engine:String(intent?.engineVersion||''),valid:intent?.valid===true,status:String(intent?.status||''),evTargetW:targetW,evStatus:targetStatus,evSource:targetSource,wwTargetOn:intent?.targets?.ww?.target_on??null,wwStatus:String(intent?.targets?.ww?.status||''),authority:String(intent?.policyProjection?.authoritySelector||intent?.policyProjection?.plannerOwner||'')});
const controlRevision=semanticToken();
const PHASES=3,VOLTAGE_V=230,MIN_A=6,FRESH_MS=120000,OPPORTUNITY_MAX_A=16;const maxConfig=num(maxVar?.value),deadlineCapA=Math.floor(Math.min(16,maxConfig??16)),deadlineTarget=targetStatus==='NUMERIC_DEADLINE_TARGET'||targetSource==='REMAINING_KWH_OVER_TIME_TO_DEADLINE',MAX_A=deadlineTarget?deadlineCapA:OPPORTUNITY_MAX_A,maxPolicy=deadlineTarget?'DEADLINE_CAP':'OPPORTUNITY_16A';
const intentAgeMs=ageMs(intent?.generatedAt),stateAgeMs=ageMs(state?.sampledAt),intentFresh=intentAgeMs>=0&&intentAgeMs<=FRESH_MS,stateFresh=stateAgeMs>=0&&stateAgeMs<=FRESH_MS;const chargeState=String(state?.tesla?.chargeState??'unknown');const confirmedA=num(state?.tesla?.offeredA),deviceRequestedA=num(state?.tesla?.requestedA);
if(controlRevision&&prev?.schema==='EM2_EV_POWER_ADAPTER_V0.1'&&prev?.controlRevision===controlRevision&&num(prev?.input?.target_W)===targetW&&num(prev?.electrical?.max_A)===MAX_A&&prev?.safety?.mappingRevision==='FLOOR_3P230_START6_RUN6_FAIL_CLOSED'&&prev?.phaseShadow?.mode===phaseModeShadow&&num(prev?.phaseShadow?.requested_A)===phaseRequestedAShadow)return true;
const schemaOk=inputSchema==='EM2_POWER_INTENT_V0.2',aligned=!!controlRevision&&schemaOk&&intent?.valid===true&&intent?.status==='OK'&&intent?.readOnly===true&&intent?.controlMode==='SHADOW'&&intent?.deviceWrites===false;const wPerA=PHASES*VOLTAGE_V,minChargeW=wPerA*MIN_A,maxChargeW=MAX_A>=MIN_A?wPerA*MAX_A:0;
let requestedA=0,status='INVALID_INPUT',reason='Invalid control intent',valid=false,theoreticalA=targetW===null?null:targetW/wPerA;
if(!aligned){status='SEMANTIC_TOKEN_OR_SCHEMA_MISMATCH';reason='Power Intent semantic token/schema invalid';}else if(targetW===null||!Number.isInteger(targetW)||targetW<0){status='INVALID_NUMERIC_TARGET';reason='EV target_W invalid';}else if(MAX_A<MIN_A){status='MAX_CURRENT_BELOW_MINIMUM';reason=`Configured max ${MAX_A} A < ${MIN_A} A`;}else if(!intentFresh){status='STALE_INTENT';reason='Power Intent stale';}else if(targetW===0){requestedA=0;status='ZERO_INTENT';reason='0 W → idle';valid=true;}else if(targetW<minChargeW){requestedA=0;status='BELOW_MINIMUM_EXECUTABLE_POWER';reason='Below 6A minimum';valid=true;}else{requestedA=Math.min(MAX_A,Math.floor(theoreticalA+Number.EPSILON));if(requestedA<MIN_A)requestedA=0;valid=true;status=requestedA===MAX_A&&theoreticalA>MAX_A?'CLAMPED_TO_MAX_CURRENT':requestedA*wPerA<targetW?'QUANTIZED_DOWN':'EXECUTABLE';reason=`${targetW} W → ${requestedA} A`;}
const phaseModeAllowed=['OFF','1P','3P'].includes(phaseModeShadow);
const phaseShadowValid=
  phaseShadowSchema==='EM2_EV_PHASE_EXECUTION_SHADOW_V0.1' &&
  phaseModeAllowed &&
  Number.isInteger(phaseRequestedAShadow) &&
  phaseRequestedAShadow>=0 && phaseRequestedAShadow<=MAX_A &&
  (phaseModeShadow==='OFF'?phaseRequestedAShadow===0:phaseRequestedAShadow>=MIN_A);
const phaseShadow={
  schema:'EM2_EV_POWER_ADAPTER_PHASE_SHADOW_V0.1',
  valid:phaseShadowValid,
  mode:phaseShadowValid?phaseModeShadow:'OFF',
  requested_A:phaseShadowValid?phaseRequestedAShadow:0,
  physicalPhaseOwner:'EASEE_EQUALIZER',
  phaseCommand:null,
  readOnly:true,
  deviceWrites:false,
  physicalWrite:false
};
const executableW=requestedA*wPerA,out={schema:'EM2_EV_POWER_ADAPTER_V0.1',generatedAt:new Date().toISOString(),sourceRevision:r,stateRevision:sr,controlRevision,inputSchema,valid,status,reason,readOnly:true,controlMode:'SHADOW',deviceWrites:false,input:{target_W:targetW,chargeState,targetStatus,targetSource,phaseModeShadow,phaseRequestedAShadow,phaseShadowSchema,intentAgeSec:Math.round(intentAgeMs/1000),stateAgeSec:Math.round(stateAgeMs/1000)},electrical:{phase_count:PHASES,voltage_V:VOLTAGE_V,w_per_A:wPerA,min_A:MIN_A,max_A:MAX_A,max_policy:maxPolicy,deadline_cap_A:deadlineCapA,opportunity_max_A:OPPORTUNITY_MAX_A,min_charge_W:minChargeW,max_charge_W:maxChargeW,theoretical_A:theoreticalA===null?null:Math.round(theoreticalA*10000)/10000,executable_W:executableW,delta_W:targetW===null?null:executableW-targetW},command:{capability:'setDynamicChargerCurrent',requested_A:requestedA,commanded_A:null,confirmed_A:confirmedA,device_requested_A:deviceRequestedA,physicalWrite:false},phaseShadow,ownership:{policy:'ENERGY_CORE_P1_OR_PI',translation:'EV_POWER_ADAPTER',physicalWriter:'DISABLED'},safety:{logicOnly:true,noDeviceWrites:true,failClosed:true,intentFresh,stateFresh,chargeStateObservabilityOnly:true,rawCoreRevisionIsObservabilityOnly:true,semanticTokenGuard:true,mappingRevision:'FLOOR_3P230_START6_RUN6_FAIL_CLOSED',neverIncreaseUpstreamPower:true}};await Homey.logic.updateVariable({id:IDS.output,variable:{value:JSON.stringify(out)}});return out.valid;
