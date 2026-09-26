// EV Actuator v0.3.0 PHASE-CANDIDATE
// Candidate-only HomeyScript source. NO physical writes.
//
// Purpose:
// - consume the already validated Bridge -> Adapter -> Gate phase SHADOW contract;
// - resolve the desired OFF | 1P+A | 3P+A actuator request;
// - force active deadline charging to locked 3P semantics;
// - read live Easee charge state, current/circuit targets and phaseMode;
// - report the next v0.4 transition action into EM2_EV_Actuator_Status.
//
// This file intentionally contains no fetch(), no runFlowCardAction() and no
// setCapabilityValue(). It can therefore be deployed for observability without
// creating a second/early writer.

const VERSION='EM2_EV_ACTUATOR_V0.3.0_PHASE_CANDIDATE';
const TRANSITION_SCHEMA='EM2_EV_PHASE_TRANSITION_STATE_V0.4';
const PHASE_EXECUTION_ENABLED=false;
const CHARGER_ID='4d0b6913-d940-474e-95d6-b43f194c4119';
const FRESH_MS=120000;

const IDS={
  live:'8d47e98d-e4bc-4f47-8c02-c2aca7f7a978',
  status:'ea1f8a44-2f6c-490e-9b86-bae761886cf9',
  intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',
  adapter:'f2118322-d59d-4aa8-b478-234effc3983c',
  gate:'4c66836b-77ae-43b5-b8e0-b32af15b57bc'
};

const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};
const age=x=>{const t=Date.parse(String(x||''));return Number.isFinite(t)?Date.now()-t:Infinity;};
const cap=(d,id)=>d?.capabilitiesObj?.[id]?.value;

const normalizePhaseMode=raw=>{
  const s=String(raw??'').trim().toLowerCase();
  if(s==='1'||s==='1p'||s.includes('locked to single'))return '1P';
  if(s==='3'||s==='3p'||s.includes('locked to three'))return '3P';
  if(s==='2'||s==='auto')return 'AUTO';
  return 'UNKNOWN';
};

const findSettingValue=(node,id)=>{
  if(!node||typeof node!=='object')return null;
  if(node.id===id&&node.value!==undefined&&node.value!==null)return node.value;
  if(Array.isArray(node)){
    for(const child of node){const v=findSettingValue(child,id);if(v!==null)return v;}
  }else{
    for(const child of Object.values(node)){const v=findSettingValue(child,id);if(v!==null)return v;}
  }
  return null;
};

const readPhaseMode=async charger=>{
  const direct=charger?.settings?.phaseMode;
  if(direct!==undefined&&direct!==null&&String(direct).trim()!=='')return String(direct);
  if(typeof Homey.devices?.getDeviceSettingsObj==='function'){
    try{
      const obj=await Homey.devices.getDeviceSettingsObj({id:CHARGER_ID});
      const v=findSettingValue(obj,'phaseMode');
      if(v!==null)return String(v);
    }catch(_){}
  }
  return null;
};

const [liveVar,statusVar,intentVar,adapterVar,gateVar]=await Promise.all([
  Homey.logic.getVariable({id:IDS.live}),
  Homey.logic.getVariable({id:IDS.status}),
  Homey.logic.getVariable({id:IDS.intent}),
  Homey.logic.getVariable({id:IDS.adapter}),
  Homey.logic.getVariable({id:IDS.gate})
]);

const intent=parse(intentVar?.value);
const adapter=parse(adapterVar?.value);
const gate=parse(gateVar?.value);
const ev=intent?.targets?.ev||{};
const phase=adapter?.phaseShadow||{};
const gatePhase=gate?.phaseShadow||{};

const targetW=num(ev?.target_W);
const targetStatus=String(ev?.status??'');
const targetSource=String(ev?.source??'');
const productionRequestedA=num(adapter?.command?.requested_A);

const deadlineTarget=
  targetStatus==='NUMERIC_DEADLINE_TARGET' ||
  targetSource==='REMAINING_KWH_OVER_TIME_TO_DEADLINE';

const phaseContractValid=
  phase?.schema==='EM2_EV_POWER_ADAPTER_PHASE_SHADOW_V0.1' &&
  phase?.valid===true &&
  gatePhase?.status==='PASS' &&
  gatePhase?.observabilityOnly===true &&
  gatePhase?.doesNotAffectProductionGate===true &&
  ['OFF','1P','3P'].includes(String(phase?.mode||'')) &&
  Number.isInteger(num(phase?.requested_A));

let desiredMode='OFF';
let desiredA=0;
let desiredSource='FAIL_CLOSED';

if(deadlineTarget){
  if(Number.isInteger(productionRequestedA) && productionRequestedA>=6 && productionRequestedA<=16){
    desiredMode='3P';
    desiredA=productionRequestedA;
    desiredSource='DEADLINE_FORCE_3P';
  }
}else if(phaseContractValid){
  const m=String(phase.mode);
  const a=num(phase.requested_A);
  const validA=
    (m==='OFF' && a===0) ||
    ((m==='1P'||m==='3P') && Number.isInteger(a) && a>=6 && a<=16);
  if(validA){
    desiredMode=m;
    desiredA=a;
    desiredSource='PHASE_SHADOW_CANDIDATE';
  }
}

const gateFresh=age(gate?.updatedAt)<=FRESH_MS;
const intentFresh=age(intent?.generatedAt)<=FRESH_MS;
const gatePass=gate?.finalStatus==='PASS';
const controlFresh=gateFresh&&intentFresh;

const devices=await Homey.devices.getDevices();
const charger=devices?.[CHARGER_ID];
if(!charger)throw new Error('CHARGER_MISSING');

const chargeState=String(cap(charger,'evcharger_charging_state')||'unknown').toLowerCase();
const charging=cap(charger,'evcharger_charging')===true;
const chargerTargetA=num(cap(charger,'target_charger_current'));
const circuitTargetA=num(cap(charger,'target_circuit_current'));
const offeredA=num(cap(charger,'measure_current.offered'));
const powerW=num(cap(charger,'measure_power'));
const phaseRaw=await readPhaseMode(charger);
const confirmedMode=normalizePhaseMode(phaseRaw);

const paused=
  charging!==true &&
  chargeState==='plugged_in_paused' &&
  offeredA!==null && offeredA<=1 &&
  powerW!==null && powerW<=250;

let nextAction='NOOP';
let reason='STABLE';

if(!gatePass||!controlFresh){
  nextAction='PAUSE_SESSION';
  reason=!gatePass?'GATE_NOT_PASS':'CONTROL_NOT_FRESH';
}else if(desiredMode==='OFF'){
  nextAction=paused?'NOOP':'PAUSE_SESSION';
  reason=paused?'ALREADY_PAUSED':'OFF_REQUIRES_PAUSE';
}else if(!['1P','3P'].includes(desiredMode) || !Number.isInteger(desiredA) || desiredA<6 || desiredA>16){
  nextAction='PAUSE_SESSION';
  reason='INVALID_PHASE_REQUEST';
}else if(confirmedMode!==desiredMode){
  nextAction=paused?'SET_PHASE_MODE':'PAUSE_SESSION';
  reason=paused?'PAUSE_CONFIRMED_PHASE_CHANGE_REQUIRED':'PHASE_CHANGE_REQUIRES_PAUSE';
}else if(paused){
  nextAction='SET_TRANSITION_CIRCUIT_CAP';
  reason='PAUSED_RESUME_REQUIRES_SAFETY_CAP';
}else if(chargeState==='plugged_in_charging'||charging){
  nextAction=chargerTargetA===desiredA?'NOOP':'SET_CURRENT';
  reason=chargerTargetA===desiredA?'STABLE':'CURRENT_TARGET_MISMATCH';
}else{
  nextAction='PAUSE_SESSION';
  reason='UNEXPECTED_CONNECTED_STATE';
}

const candidate={
  schema:TRANSITION_SCHEMA,
  candidateOnly:true,
  physicalWriteAllowed:false,
  desiredMode,
  desiredA,
  desiredSource,
  nextAction,
  reason,
  confirmedMode,
  confirmedPhaseRaw:phaseRaw,
  chargeState,
  charging,
  paused,
  chargerTargetA,
  circuitTargetA,
  offeredA,
  powerW,
  gatePass,
  gateFresh,
  intentFresh,
  phaseContractValid,
  deadlineTarget
};

const value=JSON.stringify({
  schema:VERSION,
  status:'PHASE_CANDIDATE',
  at:new Date().toISOString(),
  live:liveVar?.value===true,
  phaseExecutionEnabled:PHASE_EXECUTION_ENABLED,
  physicalWritePerformed:false,
  targetW,
  productionRequestedA,
  phaseTransition:candidate
});

if(statusVar?.value!==value){
  await Homey.logic.updateVariable({id:IDS.status,variable:{value}});
}

return true;
