// PI Dynamic Planner -> EM2 Power Intent bridge v1.5.9 ADAPTIVE-UPSCALE.
// Adaptive 3P current tuning prepared 2026-10-04 for stable Bridge flow 8bf53fdb-76f4-47db-8ccb-773ac515f06e.
// Keeps one phase selector/current regulator; allows larger 3P current steps only when current export and the 2-minute rolling signal jointly support them.
// Adds bounded realtime PV execution inside Pi envelope V0.3.
// No direct device writes: output remains EM2_Power_Intent; EV Adapter/Gate/Actuator own execution.
const SELECTOR_ID='ba9c22ba-4332-4b19-9bda-dfe476862176';
const IDS={state:'8e1efbb0-7999-494c-9429-7d274afacd79',intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',diag:'14e6c83f-e881-4ad5-8876-af1ce9e2a1a1'};
const P1_ID='7a696d77-15fb-4b68-9bce-f1e39bff5045';
const EASEE_ID='4d0b6913-d940-474e-95d6-b43f194c4119';
const URLS=['http://192.168.1.42:3100/control/current'];
const POLICY='PI_DYNAMIC_PLANNER_BRIDGE_V1.5.9_ADAPTIVE_UPSCALE';
const ENGINE='PI_DYNAMIC_PLANNER_V0.3_LAN_BRIDGE';
const RT_SCHEMA='EMS_PI_EV_REALTIME_ENVELOPE_V0.4';
const EV_W_PER_A=690, MIN_A=6, MAX_A=16, P1_FRESH_MS=180000;
const EVPC_ROLLING_WINDOW_MS=120000, EVPC_ROLLING_MIN_COVERAGE_MS=90000;
const EVPC_OFF_REENTRY_DWELL_MS=120000, EVPC_1P_TO_3P_DWELL_MS=180000, EVPC_MAX_UPSTEP_1P_A=3, EVPC_MAX_UPSTEP_3P_A=2, EVPC_MAX_ADAPTIVE_UPSTEP_3P_A=4, EVPC_UPSCALE_IMPORT_TARGET_W=300, EVPC_IMPORT_DEADBAND_W=250;
const EVPC_CURRENT_IMPORT_LIMIT_W=Math.max(EVPC_IMPORT_DEADBAND_W,EVPC_UPSCALE_IMPORT_TARGET_W);
const EVPC_MAX_ROLLING_SAMPLES=240;
const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};
const bool=x=>x===true||String(x).toLowerCase()==='true';
const cap=(d,id)=>d?.capabilitiesObj?.[id]?.value;
const capUpdated=(d,id)=>{const ms=Date.parse(String(d?.capabilitiesObj?.[id]?.lastUpdated||''));return Number.isFinite(ms)?ms:null;};
const connectedState=s=>['plugged_in','plugged_in_paused','plugged_in_charging'].includes(String(s||'').toLowerCase());
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
const readPhaseMode=async easee=>{
  const direct=easee?.settings?.phaseMode;
  if(direct!==undefined&&direct!==null&&String(direct).trim()!=='')return String(direct);
  if(typeof Homey.devices?.getDeviceSettingsObj==='function'){
    try{
      const obj=await Homey.devices.getDeviceSettingsObj({id:EASEE_ID});
      const v=findSettingValue(obj,'phaseMode');
      if(v!==null)return String(v);
    }catch(_){}
  }
  return null;
};
const evpcWPerA=mode=>mode==='1P'?230:mode==='3P'?690:0;
const evpcCanSustainMin=(mode,availableW)=>{
  const wpa=evpcWPerA(mode);
  return wpa>0&&availableW+EVPC_IMPORT_DEADBAND_W>=MIN_A*wpa;
};
const evpcNormalizeSamples=(rawSamples,nowMs)=>{
  const clean=[];
  for(const raw of Array.isArray(rawSamples)?rawSamples:[]){
    const at=Date.parse(String(raw?.at||''));
    const w=num(raw?.w);
    if(!Number.isFinite(at)||w===null||w<0||at>nowMs)continue;
    clean.push({atMs:at,w});
  }
  clean.sort((a,b)=>a.atMs-b.atMs);
  const dedup=[];
  for(const s of clean){
    if(dedup.length&&dedup[dedup.length-1].atMs===s.atMs)dedup[dedup.length-1]=s;
    else dedup.push(s);
  }
  const windowStart=nowMs-EVPC_ROLLING_WINDOW_MS;
  let anchor=null;
  const inside=[];
  for(const s of dedup){
    if(s.atMs<windowStart)anchor=s;
    else inside.push(s);
  }
  return (anchor?[anchor,...inside]:inside).slice(-EVPC_MAX_ROLLING_SAMPLES);
};
const evpcAppendSample=(rawSamples,nowMs,availableW)=>{
  const samples=evpcNormalizeSamples(rawSamples,nowMs);
  const current={atMs:nowMs,w:Math.max(0,availableW)};
  if(samples.length&&samples[samples.length-1].atMs===nowMs)samples[samples.length-1]=current;
  else samples.push(current);
  return samples.slice(-EVPC_MAX_ROLLING_SAMPLES).map(s=>({at:new Date(s.atMs).toISOString(),w:Math.round(s.w)}));
};
const evpcRolling=(rawSamples,nowMs)=>{
  const samples=evpcNormalizeSamples(rawSamples,nowMs);
  if(!samples.length)return {avgW:null,coverageMs:0,ready:false,sampleCount:0};
  const windowStart=nowMs-EVPC_ROLLING_WINDOW_MS;
  let weighted=0,covered=0;
  for(let i=0;i<samples.length;i++){
    const s=samples[i];
    const nextAt=i+1<samples.length?samples[i+1].atMs:nowMs;
    const from=Math.max(windowStart,s.atMs);
    const to=Math.min(nowMs,nextAt);
    if(to<=from)continue;
    const dt=to-from;
    weighted+=s.w*dt;
    covered+=dt;
  }
  return {
    avgW:covered>0?weighted/covered:samples[samples.length-1].w,
    coverageMs:covered,
    ready:covered>=EVPC_ROLLING_MIN_COVERAGE_MS&&samples.length>=2,
    sampleCount:samples.length
  };
};
let devicesCache=null;
const getDevice=async id=>{if(typeof Homey.devices?.getDevice==='function')return await Homey.devices.getDevice({id});if(!devicesCache)devicesCache=await Homey.devices.getDevices();return devicesCache?.[id]||null;};
let stage='SELECTOR_READ',intentVar=null,diagVar=null,coreState=null,stateRev=null,plannerGeneratedAt=null,commandValidUntil=null,evW=0,evStatus='IDLE',wwOn=null,quooker={mode:'OFF',target_on:false,opportunity_allowed:false,modeled_power_W:1580,start_export_W:1250,stop_import_W:600,reason:'FAIL_CLOSED'},source='PI_FAIL_CLOSED',reason='UNINITIALIZED',valid=false,status='PI_BRIDGE_ERROR';
let deadlineGuardApplied=false,deadlineActive=false,deadlineTeslaConnected=false,deadlineChargeState='unknown',deadlineAt=null,latestStartAt=null,derivedLatestStartAt=null,forceFromAt=null,deadlineRemainingKWh=0,deadlineMaxA=null,deadlineOverdue=false;
let evV2Shadow={schema:'EM2_EV_V2_ROLLING_SHADOW_V0.1',readOnly:true,samples:[],rolling5mW:null,lastSampleAt:null};
let realtime={schema:'EM2_EV_REALTIME_EXECUTION_V0.1',eligible:false,applied:false,fallbackReason:null,envelopeSchema:null,envelopeAllowed:false,minA:0,maxA:0,p1W:null,p1AgeSec:null,chargeState:null,evActualW:null,evPowerAgeSec:null,counterfactualSurplusW:null,candidateA:null,candidateW:null,importReductionA:0,plannerTargetA:0,plannerTargetW:0,confirmedPhaseRaw:null,confirmedPhaseMode:'UNKNOWN',actualProductionPhaseCount:null,phasePolicy:null,phaseShadow:{schema:'EM2_EV_PHASE_EXECUTION_SHADOW_V0.1',mode:'OFF',requestedA:0,requestedW:0,reason:'NOT_EVALUATED',modeSinceAt:null,shadow:true,deviceWrites:false,controlWrites:false}};
const writeDiag=async(extra={})=>{try{if(!diagVar)diagVar=await Homey.logic.getVariable({id:IDS.diag});if(!diagVar)return;const obj={schema:'EM2_PI_BRIDGE_DIAGNOSTIC_V0.2',updatedAt:new Date().toISOString(),policyRevision:POLICY,stage,status,reason,valid,stateRevision:stateRev,plannerGeneratedAt,commandValidUntil,evTargetW:evW,evTargetStatus:evStatus,wwTargetOn:wwOn,authority:'PI',persistent:true,realtime,evV2Shadow,deadlineGuard:{active:deadlineActive,teslaConnected:deadlineTeslaConnected,chargeState:deadlineChargeState,applied:deadlineGuardApplied,deadlineAt,latestStartAt,derivedLatestStartAt,forceFromAt,remainingKWh:deadlineRemainingKWh,maxA:deadlineMaxA,overdue:deadlineOverdue},...extra};await Homey.logic.updateVariable({id:IDS.diag,variable:{value:JSON.stringify(obj)}});}catch(_){}};
const buildPhaseControl=()=>{
  if(!valid)return {schema:'EM2_EV_PHASE_CONTROL_V0.1',authoritative:true,mode:'OFF',requestedA:0,requestedW:0,source:'INVALID_CONTROL'};
  if(deadlineGuardApplied&&Number.isInteger(deadlineMaxA)&&deadlineMaxA>=MIN_A&&deadlineMaxA<=MAX_A){
    return {schema:'EM2_EV_PHASE_CONTROL_V0.1',authoritative:true,mode:'3P',requestedA:deadlineMaxA,requestedW:deadlineMaxA*EV_W_PER_A,source:'DEADLINE_FORCE_3P'};
  }
  const ps=realtime?.phaseShadow||{};
  const pm=String(ps?.mode||'OFF');
  const pa=num(ps?.requestedA);
  const psValid=
    ps?.schema==='EM2_EV_PHASE_EXECUTION_SHADOW_V0.1' &&
    ['OFF','1P','3P'].includes(pm) &&
    Number.isInteger(pa) &&
    ((pm==='OFF'&&pa===0)||((pm==='1P'||pm==='3P')&&pa>=MIN_A&&pa<=MAX_A));
  if(realtime?.applied===true&&psValid){
    return {
      schema:'EM2_EV_PHASE_CONTROL_V0.1',
      authoritative:true,
      mode:pm,
      requestedA:pa,
      requestedW:pm==='1P'?pa*230:pm==='3P'?pa*EV_W_PER_A:0,
      source:'REALTIME_PHASE_CURRENT_CONTROLLER'
    };
  }
  const fallbackA=Math.max(0,Math.min(MAX_A,Math.floor(Math.max(0,num(evW)||0)/EV_W_PER_A)));
  if(fallbackA>=MIN_A){
    return {schema:'EM2_EV_PHASE_CONTROL_V0.1',authoritative:true,mode:'3P',requestedA:fallbackA,requestedW:fallbackA*EV_W_PER_A,source:'PI_3P_FALLBACK'};
  }
  return {schema:'EM2_EV_PHASE_CONTROL_V0.1',authoritative:true,mode:'OFF',requestedA:0,requestedW:0,source:'IDLE'};
};
let executionMode='PLANNER';
const selectorV=await Homey.logic.getVariable({id:SELECTOR_ID});
if(!selectorV||selectorV.value!=='PI') return true;
const writeIntent=async()=>{
  if(!intentVar)return false;
  const now=new Date().toISOString();
  const phaseControl=buildPhaseControl();
  evW=phaseControl.requestedW;
  if(!deadlineGuardApplied)evStatus=phaseControl.requestedA>0?'NUMERIC_REALTIME_PV_TARGET':'IDLE';
  realtime.phaseControl=phaseControl;
  const controlRevision=JSON.stringify({
    policy:POLICY,
    engine:ENGINE,
    valid,
    status,
    evTargetW:evW,
    evStatus,
    evSource:source,
    evPhaseMode:phaseControl.mode,
    evRequestedA:phaseControl.requestedA,
    wwTargetOn:wwOn,
    wwStatus:valid?'PI_BINARY_TARGET':'FAIL_CLOSED_PI_UNAVAILABLE',
    quookerMode:valid?quooker.mode:'OFF',
    quookerTargetOn:valid?quooker.target_on:false,
    authority:'PI'
  });
  const out={
    schema:'EM2_POWER_INTENT_V0.2',
    policyRevision:POLICY,
    engineVersion:ENGINE,
    generatedAt:now,
    sourceRevision:stateRev,
    controlRevision,
    readOnly:true,
    controlMode:'SHADOW',
    deviceWrites:false,
    valid,
    status,
    inputSemanticKey:JSON.stringify({stateRev,plannerGeneratedAt,commandValidUntil,evW,evStatus,wwOn,quooker,valid,stage,realtime,deadlineGuardApplied,deadlineTeslaConnected,deadlineChargeState,deadlineAt,forceFromAt,deadlineRemainingKWh,deadlineMaxA}),
    inputRevisions:{state:stateRev,planner:plannerGeneratedAt},
    policyProjection:{
      plannerOwner:'PI',
      plannerValid:executionMode==='PLANNER',
      executionMode,
      executor:'HOMEY',
      authoritySelector:'PI',
      contractMode:'FIXED',
      contractId:'ENGIE_3Y_2026_2029',
      reason,
      commandValidUntil,
      bridgeStage:stage,
      realtime,
      deadlineGuardApplied,
      deadlineTeslaConnected,
      deadlineChargeState,
      deadlineAt,
      latestStartAt,
      derivedLatestStartAt,
      forceFromAt,
      deadlineRemainingKWh,
      deadlineMaxA
    },
    targets:{
      ev:{
        target_W:valid?phaseControl.requestedW:0,
        status:valid?evStatus:'FAIL_CLOSED_PI_UNAVAILABLE',
        source,
        phase_control_schema:'EM2_EV_PHASE_CONTROL_V0.1',
        phase_control_authoritative:true,
        phase_mode:valid?phaseControl.mode:'OFF',
        phase_requested_A:valid?phaseControl.requestedA:0,
        phase_requested_W:valid?phaseControl.requestedW:0,
        phase_source:phaseControl.source,
        phase_mode_shadow:valid?(realtime?.phaseShadow?.mode||'OFF'):'OFF',
        phase_requested_A_shadow:valid?(num(realtime?.phaseShadow?.requestedA)||0):0,
        phase_shadow_schema:'EM2_EV_PHASE_EXECUTION_SHADOW_V0.1'
      },
      ww:{
        target_W:null,
        target_on:valid?wwOn:false,
        status:valid?'PI_BINARY_TARGET':'FAIL_CLOSED_PI_UNAVAILABLE',
        sourceAction:wwOn===true?'BOILER_ON':wwOn===false?'BOILER_OFF':'HOLD'
      },
      quooker:{
        mode:valid?quooker.mode:'OFF',
        target_on:valid?quooker.target_on:false,
        opportunity_allowed:valid?quooker.opportunity_allowed:false,
        modeled_power_W:valid?quooker.modeled_power_W:1580,
        start_export_W:valid?quooker.start_export_W:1250,
        stop_import_W:valid?quooker.stop_import_W:600,
        reason:valid?quooker.reason:'FAIL_CLOSED_PI_UNAVAILABLE',
        status:valid?'PI_QUOOKER_ENVELOPE':'FAIL_CLOSED_PI_UNAVAILABLE'
      },
      battery:{target_W:0,status:'NOT_INTEGRATED'}
    },
    safety:{
      logicOnly:true,
      noDeviceWrites:true,
      plannerOwner:'PI',
      homeyRole:'EXECUTOR_SAFETY',
      fixedContractEnforced:true,
      failClosed:true,
      staleCommandRejected:true,
      singleWriterGuard:true,
      requiredAuthority:'PI',
      authorityGate:'EM2_Planner_Authority',
      bridgeUrls:URLS,
      diagnosticStage:stage,
      persistentDiagnostic:true,
      realtimeEnvelopeSchema:RT_SCHEMA,
      boundedRealtimePv:true,
      deadlineGuard:true,
      deadlineRequiresConnectedTesla:true,
      deadlineConnectivitySource:'HOMEY_EASEE_CHARGE_STATE',
      deadlineStateSource:'PI_CONTROL_COMMAND',
      deadlineBeforeLatestStartPreservesPiTarget:true,
      phaseControlSchema:'EM2_EV_PHASE_CONTROL_V0.1',
      phaseControlAuthoritative:true
    }
  };
  const value=JSON.stringify(out);
  if(intentVar.value!==value)await Homey.logic.updateVariable({id:IDS.intent,variable:{value}});
  return true;
};
try{
  stage='LOGIC_READ';
  const vars=await Promise.all([Homey.logic.getVariable({id:IDS.state}),Homey.logic.getVariable({id:IDS.intent}),Homey.logic.getVariable({id:IDS.diag})]);
  const stateVar=vars[0];intentVar=vars[1];diagVar=vars[2];
  if(!stateVar||!intentVar||!diagVar)throw new Error('PI_BRIDGE_REQUIRED_VARIABLE_MISSING');
  stage='LOGIC_OK';
  coreState=parse(stateVar.value);stateRev=num(coreState?.revision);if(stateRev===null)throw new Error('STATE_REVISION_MISSING');
  const priorDiag=parse(diagVar.value);const priorSamples=Array.isArray(priorDiag?.evV2Shadow?.samples)?priorDiag.evV2Shadow.samples:[];evV2Shadow.samples=priorSamples.slice(-4);
  await writeDiag();
  let cmd=null,lastError=null;
  stage='FETCH_START';await writeDiag();
  for(const url of URLS){try{const r=await fetch(url,{headers:{Accept:'application/json'}});stage='FETCH_RESPONSE';await writeDiag();let j=null;try{j=await r.json();}catch(e){throw new Error('JSON_PARSE:'+String(e?.message||e));}if(r.ok){cmd=j;break;}lastError=`${url}:HTTP_${r.status}:${String(j?.reason||'')}`;}catch(e){lastError=`${url}:${String(e?.message||e)}`;}}
  if(!cmd)throw new Error(lastError||'NO_RESPONSE');
  stage='FETCH_OK';plannerGeneratedAt=cmd.plannerGeneratedAt||null;commandValidUntil=cmd.validUntil||null;await writeDiag();
  const contract=cmd.contract||{},t=cmd.targets||{};
  const schemaOK=cmd.schema==='EMS_PI_CONTROL_COMMAND_V0.1';
  const readyOK=cmd.readyForCutover===true;
  const ownerOK=cmd.plannerOwner==='PI'&&cmd.executor==='HOMEY';
  const contractOK=contract.mode==='FIXED'&&contract.id==='ENGIE_3Y_2026_2029';
  const until=Date.parse(String(cmd.validUntil||''));const fresh=Number.isFinite(until)&&until>Date.now();
  stage='VALIDATION';await writeDiag();
  if(!schemaOK)throw new Error('SCHEMA_MISMATCH');
  if(!readyOK)throw new Error('PI_NOT_READY');
  if(!ownerOK)throw new Error('OWNER_MISMATCH');
  if(!contractOK)throw new Error('CONTRACT_MISMATCH');
  if(!fresh)throw new Error('STALE_PI_COMMAND');

  // A planner failure is allowed only for a strictly bounded, Pi-owned
  // deadline-only command. It must never enable PV, WW or Quooker targets.
  executionMode=String(cmd.executionMode||'PLANNER');
  if(!['PLANNER','DEADLINE_ONLY'].includes(executionMode))throw new Error('UNKNOWN_EXECUTION_MODE');
  const deadlineOnly=executionMode==='DEADLINE_ONLY';
  if(deadlineOnly){
    const dl=cmd.deadline||{},rt=cmd.realtime?.ev||{};
    const deadlineMs=Date.parse(String(dl.deadlineAt||''));
    const latestMs=Date.parse(String(dl.latestStartAt||''));
    const cap=num(dl.maxA),remaining=num(dl.remainingKWh);
    const safelyIsolated=
      cmd.planner?.valid===false &&
      dl.schema==='EMS_PI_EV_DEADLINE_EXECUTION_V0.1' &&
      dl.authority==='PI' && dl.valid===true && dl.active===true &&
      dl.status==='TRACKING' && !!dl.requestId &&
      Number.isFinite(deadlineMs) && deadlineMs>Date.now() &&
      Number.isFinite(latestMs) &&
      Number.isInteger(cap) && cap>=MIN_A && cap<=MAX_A &&
      remaining!==null && remaining>0 &&
      num(t.ev?.target_W)===0 && num(t.ev?.target_A)===0 &&
      num(t.ww?.target_W)===0 && t.ww?.target_on===null &&
      t.quooker?.mode==='OFF' && t.quooker?.target_on===false &&
      t.quooker?.opportunity_allowed===false &&
      num(t.battery?.target_W)===0 &&
      rt.schema===RT_SCHEMA && rt.allowed===false &&
      rt.productionConsumerAllowed===false && rt.mode==='DISABLED';
    if(!safelyIsolated)throw new Error('DEADLINE_ONLY_CONTRACT_INVALID');
  }
  stage='VALIDATION_OK';
  const plannerEvW=Math.max(0,Math.round(num(t?.ev?.target_W)||0));
  const plannerEvA=Math.max(0,Math.round(num(t?.ev?.target_A)||0));
  evW=plannerEvW;evStatus=evW>0?'PI_NUMERIC_TARGET':'IDLE';
  wwOn=t?.ww?.target_on===true?true:t?.ww?.target_on===false?false:null;
  const q=t?.quooker||{};
  const qMode=['OPPORTUNITY','FORCED_ON','OFF'].includes(String(q.mode||'').toUpperCase())?String(q.mode).toUpperCase():'OFF';
  quooker={
    mode:qMode,
    target_on:qMode==='FORCED_ON'&&q.target_on===true,
    opportunity_allowed:qMode==='OPPORTUNITY'&&q.opportunity_allowed===true,
    modeled_power_W:Math.max(0,Math.round(num(q.modeled_power_W)||1580)),
    start_export_W:Math.max(0,Math.round(num(q.start_export_W)||1250)),
    stop_import_W:Math.max(0,Math.round(num(q.stop_import_W)||600)),
    reason:String(q.reason||('TIME_ENVELOPE_'+qMode))
  };
  valid=true;status='OK';
  source=deadlineOnly?'PI_DEADLINE_ONLY':'PI_DYNAMIC_PLANNER_V0.3';
  reason=deadlineOnly?'PLANNER_UNAVAILABLE_'+String(cmd.planner?.reason||'UNKNOWN'):
    (t?.ev?.reason||t?.ww?.reason||t?.quooker?.reason||'PI_DYNAMIC_SLOT');
  realtime.plannerTargetA=plannerEvA;realtime.plannerTargetW=plannerEvW;

  // Bounded realtime PV execution. Invalid live inputs fall back to the exact Pi slot target.
  const env=cmd?.realtime?.ev||{};
  realtime.envelopeSchema=env.schema||null;realtime.envelopeAllowed=env.allowed===true;
  const minA=Math.round(num(env.min_A)||0),maxA=Math.round(num(env.max_A)||0),envDeadlineMax=Math.round(num(env.deadlineMax_A)||0);
  realtime.minA=minA;realtime.maxA=maxA;
  const phasePolicy=env?.phasePolicy||{};
  const phaseAllowed=Array.isArray(phasePolicy.allowedModes)?phasePolicy.allowedModes:[];
  const phasePolicyValid=
    phasePolicy.schema==='EMS_PI_EV_PHASE_POLICY_V0.1' &&
    phasePolicy.shadowOnly===true &&
    phasePolicy.failClosed===true &&
    phasePolicy.physicalPhaseOwner==='EASEE_EQUALIZER' &&
    phasePolicy.phaseCommand===null &&
    phaseAllowed.includes('OFF') && phaseAllowed.includes('1P') && phaseAllowed.includes('3P') &&
    num(phasePolicy.start1p_W)!==null && num(phasePolicy.stop1p_W)!==null &&
    num(phasePolicy.enter3p_W)!==null && num(phasePolicy.leave3p_W)!==null &&
    num(phasePolicy.minModeDwellSec)!==null;
  realtime.phasePolicy={
    schema:phasePolicy.schema||null,
    valid:phasePolicyValid,
    shadowOnly:phasePolicy.shadowOnly===true,
    allowedModes:phaseAllowed,
    physicalPhaseOwner:phasePolicy.physicalPhaseOwner||null
  };
  // Phase-mode readback is observability and must not depend on Pi realtime
  // eligibility/connected-state. This keeps requested/commanded/confirmed
  // separation visible even when the Pi currently says NOT_CONNECTED.
  let easeeObs=null;
  try{
    easeeObs=await getDevice(EASEE_ID);
    if(easeeObs){
      const phaseRawObs=await readPhaseMode(easeeObs);
      realtime.confirmedPhaseRaw=phaseRawObs;
      realtime.confirmedPhaseMode=normalizePhaseMode(phaseRawObs);
    }
  }catch(_){}

  const envValid=env.schema===RT_SCHEMA&&env.shadowOnly===false&&env.productionConsumerAllowed===true&&env.allowed===true&&env.mode==='PV_OPPORTUNITY'&&env.failClosed===true&&env.deadlineRequiredSlot!==true&&minA===MIN_A&&maxA>=MIN_A&&maxA<=MAX_A&&(!env.deadlineActive||(envDeadlineMax>=MIN_A&&maxA<=envDeadlineMax));
  if(envValid){
    realtime.eligible=true;
    try{
      stage='REALTIME_DEVICE_READ';
      const [p1,easee]=await Promise.all([getDevice(P1_ID),getDevice(EASEE_ID)]);
      if(!p1||!easee)throw new Error('REALTIME_DEVICE_MISSING');
      if(p1.available===false)throw new Error('P1_UNAVAILABLE');
      if(easee.available===false)throw new Error('EASEE_UNAVAILABLE');
      if(cap(p1,'alarm_connectivity')===true)throw new Error('P1_CONNECTIVITY_ALARM');
      const p1W=num(cap(p1,'measure_power'));if(p1W===null)throw new Error('P1_POWER_INVALID');
      const p1Ts=capUpdated(p1,'measure_power');if(p1Ts!==null&&Date.now()-p1Ts>P1_FRESH_MS)throw new Error('P1_POWER_STALE');
      const previousIntent=parse(intentVar?.value);
      const rawChargeState=String(cap(easee,'evcharger_charging_state')||'unknown').toLowerCase();
      const offeredNow=num(cap(easee,'measure_current.offered'));
      const chargerPowerNow=num(cap(easee,'measure_power'));
      const chargerChargingNow=cap(easee,'evcharger_charging')===true;

      // Connection authority stays simple and immediate:
      // - native connected states mean connected;
      // - if Homey briefly reports a contradictory non-connected state while
      //   current/power/charging proves the EV is active, keep it connected.
      // No time-based disconnect grace is used.
      const electricalConnectedEvidence=
        chargerChargingNow ||
        (offeredNow!==null&&offeredNow>1) ||
        (chargerPowerNow!==null&&chargerPowerNow>250);
      const effectiveConnected=
        connectedState(rawChargeState) ||
        electricalConnectedEvidence;

      realtime.chargeState=rawChargeState;
      realtime.connectionGuard={
        rawChargeState,
        effectiveConnected,
        evidence:{
          homeyConnectedState:connectedState(rawChargeState),
          charging:chargerChargingNow,
          offeredA:offeredNow,
          powerW:chargerPowerNow,
          electricalConnectedEvidence
        }
      };

      if(!effectiveConnected){evW=0;evStatus='IDLE';source='HOMEY_BOUNDED_REALTIME_PV';reason='REALTIME_TESLA_NOT_CONNECTED';realtime.applied=true;realtime.fallbackReason=null;realtime.p1W=Math.round(p1W);realtime.candidateA=0;realtime.candidateW=0;}
      else{
        // v1.5.8 production controller: one authoritative realtime controller.
        // Phase selector owns OFF|1P|3P; current regulator owns 6..16 A inside
        // the selected phase. There is no parallel legacy candidateA controller.
        const previousPhase=previousIntent?.policyProjection?.realtime?.phaseShadow||{};
        const previousMode=['1P','3P'].includes(String(previousPhase?.mode||''))
          ?String(previousPhase.mode)
          :'OFF';
        const previousA=Math.max(
          0,
          Math.min(maxA,Math.round(num(previousPhase?.requestedA)||0))
        );
        const previousSinceParsed=Date.parse(String(previousPhase?.modeSinceAt||''));
        const previousModeSinceMs=Number.isFinite(previousSinceParsed)
          ?previousSinceParsed
          :null;
        const previousUpscaleParsed=Date.parse(String(previousPhase?.upscaleSinceAt||''));
        const previousUpscaleSinceMs=Number.isFinite(previousUpscaleParsed)
          ?previousUpscaleParsed
          :null;

        const confirmedPhaseRaw=
          realtime.confirmedPhaseRaw!==null
            ?realtime.confirmedPhaseRaw
            :await readPhaseMode(easee);
        const confirmedPhaseMode=normalizePhaseMode(confirmedPhaseRaw);

        // Physical add-back follows what Easee is actually offering while
        // charging. Previous requested current is only a bounded fallback when
        // offered current is unavailable.
        const offeredA=num(cap(easee,'measure_current.offered'));
        const offeredAUsable=offeredA!==null&&offeredA>=0&&offeredA<=MAX_A;
        const phasePhysicalA=
          rawChargeState==='plugged_in_charging'
            ?(offeredAUsable?Math.round(offeredA):previousA)
            :0;
        const actualProductionPhaseCount=phasePhysicalA<=0
          ?0
          :confirmedPhaseMode==='1P'
            ?1
            :confirmedPhaseMode==='3P'
              ?3
              :null;
        realtime.confirmedPhaseRaw=confirmedPhaseRaw;
        realtime.confirmedPhaseMode=confirmedPhaseMode;
        realtime.actualProductionPhaseCount=actualProductionPhaseCount;

        if(!phasePolicyValid)throw new Error('PHASE_POLICY_INVALID');

        const phaseReadbackValid=
          phasePhysicalA===0||
          actualProductionPhaseCount===1||
          actualProductionPhaseCount===3;
        const actualEvW=phaseReadbackValid
          ?phasePhysicalA*230*(actualProductionPhaseCount||0)
          :0;
        const availableTotalW=phaseReadbackValid
          ?Math.max(0,-p1W+actualEvW)
          :0;
        const sampleMs=p1Ts!==null?p1Ts:Date.now();
        const availableTotalSamples=evpcAppendSample(
          previousPhase?.availableTotalSamples,
          sampleMs,
          availableTotalW
        );
        const rolling=evpcRolling(availableTotalSamples,sampleMs);

        const pp=phasePolicy;
        const start1pW=Math.max(0,Math.round(num(pp.start1p_W)||0));
        const stop1pW=Math.max(0,Math.round(num(pp.stop1p_W)||0));
        const enter3pW=Math.max(0,Math.round(num(pp.enter3p_W)||0));
        const leave3pW=Math.max(0,Math.round(num(pp.leave3p_W)||0));

        let phaseMode=phaseReadbackValid?previousMode:'OFF';
        let phaseReason=phaseReadbackValid?'HOLD_MODE':'PHASE_READBACK_UNCONFIRMED';
        const offReentryDwellOK=
          !Number.isFinite(previousModeSinceMs)||
          sampleMs-previousModeSinceMs>=EVPC_OFF_REENTRY_DWELL_MS;
        const onePTo3pDwellOK=
          !Number.isFinite(previousModeSinceMs)||
          sampleMs-previousModeSinceMs>=EVPC_1P_TO_3P_DWELL_MS;

        if(phaseReadbackValid&&rolling.ready){
          const rollingW=rolling.avgW;
          if(previousMode==='3P'){
            // Downward transitions use sustained evidence and are deliberately
            // not trapped behind either upward dwell.
            if(rollingW<start1pW){
              phaseMode='OFF';
              phaseReason='3P_TO_OFF_ROLLING_LOW';
            }else if(rollingW<leave3pW){
              phaseMode='1P';
              phaseReason='3P_TO_1P_ROLLING_LOW';
            }
          }else if(previousMode==='1P'){
            if(rollingW<stop1pW){
              phaseMode='OFF';
              phaseReason='1P_TO_OFF_ROLLING_LOW';
            }else if(
              rollingW>=enter3pW&&
              onePTo3pDwellOK&&
              evpcCanSustainMin('3P',availableTotalW)
            ){
              phaseMode='3P';
              phaseReason='1P_TO_3P_ROLLING_HIGH';
            }
          }else if(offReentryDwellOK){
            if(
              rollingW>=enter3pW&&
              evpcCanSustainMin('3P',availableTotalW)
            ){
              phaseMode='3P';
              phaseReason='OFF_TO_3P_ROLLING_HIGH';
            }else if(
              rollingW>=start1pW&&
              evpcCanSustainMin('1P',availableTotalW)
            ){
              phaseMode='1P';
              phaseReason='OFF_TO_1P_ROLLING_HIGH';
            }
          }
        }else if(phaseReadbackValid&&!rolling.ready){
          phaseReason='ROLLING_NOT_READY';
        }

        const phaseChanged=phaseMode!==previousMode;
        let requestedA=0;
        let upscaleSinceMs=previousUpscaleSinceMs;
        let currentReason='MODE_OFF';

        if(phaseMode!=='OFF'){
          const wpa=evpcWPerA(phaseMode);
          if(phaseChanged||previousA<MIN_A){
            requestedA=Math.max(
              MIN_A,
              Math.min(
                maxA,
                Math.floor((availableTotalW+EVPC_IMPORT_DEADBAND_W)/wpa)
              )
            );
            upscaleSinceMs=null;
            currentReason=phaseChanged?'MODE_ENTRY_INITIAL_A':'INITIAL_A';
          }else{
            requestedA=Math.max(MIN_A,Math.min(maxA,previousA));
            if(requestedA!==previousA){
              upscaleSinceMs=null;
              currentReason='ENVELOPE_CAP_DOWN';
            }else{
              const syntheticP1W=requestedA*wpa-availableTotalW;
              if(syntheticP1W>EVPC_CURRENT_IMPORT_LIMIT_W){
                const excessImportW=syntheticP1W-EVPC_CURRENT_IMPORT_LIMIT_W;
                const reductionA=Math.max(1,Math.ceil(excessImportW/wpa));
                const nextA=Math.max(MIN_A,requestedA-reductionA);
                realtime.importReductionA=requestedA-nextA;
                requestedA=nextA;
                upscaleSinceMs=null;
                currentReason='FAST_IMPORT_DOWN';
              }else{
                const desiredA=Math.max(
                  MIN_A,
                  Math.min(
                    maxA,
                    Math.floor((availableTotalW+EVPC_UPSCALE_IMPORT_TARGET_W)/wpa)
                  )
                );
                const rollingDesiredA=rolling.ready
                  ?Math.max(
                    MIN_A,
                    Math.min(
                      maxA,
                      Math.floor((rolling.avgW+EVPC_UPSCALE_IMPORT_TARGET_W)/wpa)
                    )
                  )
                  :requestedA;
                const currentExportW=Math.max(0,-p1W);
                const physicalTargetSettled=
                  Number.isFinite(phasePhysicalA)&&phasePhysicalA===requestedA;
                realtime.predictiveDesiredA=desiredA;
                realtime.rollingDesiredA=rollingDesiredA;
                realtime.currentExportW=Math.round(currentExportW);
                realtime.physicalTargetSettled=physicalTargetSettled;
                realtime.adaptive3pCandidateStepA=0;
                realtime.appliedUpscaleStepA=0;
                if(desiredA>requestedA){
                  if(!physicalTargetSettled){
                    upscaleSinceMs=null;
                    currentReason='PREDICTIVE_UP_WAIT_PHYSICAL';
                  }else{
                    let maxStepA=phaseMode==='1P'?EVPC_MAX_UPSTEP_1P_A:EVPC_MAX_UPSTEP_3P_A;
                    let adaptive3pStepA=0;
                    if(phaseMode==='3P'&&rolling.ready&&currentExportW>0){
                      const currentExportSupportedStepA=Math.max(
                        0,
                        Math.floor((currentExportW+EVPC_UPSCALE_IMPORT_TARGET_W)/wpa)
                      );
                      const rollingSupportedStepA=Math.max(0,rollingDesiredA-requestedA);
                      const desiredStepA=Math.max(0,desiredA-requestedA);
                      adaptive3pStepA=Math.min(
                        EVPC_MAX_ADAPTIVE_UPSTEP_3P_A,
                        currentExportSupportedStepA,
                        rollingSupportedStepA,
                        desiredStepA
                      );
                      realtime.adaptive3pCandidateStepA=adaptive3pStepA;
                      if(adaptive3pStepA>EVPC_MAX_UPSTEP_3P_A){
                        maxStepA=adaptive3pStepA;
                      }
                    }
                    const nextA=Math.min(desiredA,requestedA+maxStepA,maxA);
                    realtime.appliedUpscaleStepA=Math.max(0,nextA-requestedA);
                    const adaptive3pApplied=
                      phaseMode==='3P'&&
                      realtime.appliedUpscaleStepA>EVPC_MAX_UPSTEP_3P_A;
                    requestedA=nextA;
                    upscaleSinceMs=null;
                    currentReason=adaptive3pApplied
                      ?'PREDICTIVE_UP_ADAPTIVE_EXPORT'
                      :'PREDICTIVE_UP_BOUNDED';
                  }
                }else{
                  upscaleSinceMs=null;
                  currentReason='HOLD_A';
                }
              }
            }
          }
        }else{
          requestedA=0;
          upscaleSinceMs=null;
        }

        const requestedW=requestedA*evpcWPerA(phaseMode);
        const currentChanged=requestedA!==previousA;
        const modeSinceAt=phaseChanged
          ?new Date(sampleMs).toISOString()
          :(previousPhase?.modeSinceAt||null);

        realtime.phaseShadow={
          schema:'EM2_EV_PHASE_EXECUTION_SHADOW_V0.1',
          controllerVersion:'EM2_EV_PHASE_CURRENT_CONTROLLER_V0.4',
          mode:phaseMode,
          requestedA,
          requestedW,
          reason:phaseReason,
          phaseReason,
          currentReason,
          phaseChanged,
          currentChanged,
          currentOnlyChange:currentChanged&&!phaseChanged,
          requiresPhysicalPhaseTransition:phaseChanged,
          availableTotalW:Math.round(availableTotalW),
          availableTotalAvg2mW:rolling.avgW===null?null:Math.round(rolling.avgW),
          rollingCoverageMs:Math.round(rolling.coverageMs),
          rollingReady:rolling.ready,
          rollingSampleCount:rolling.sampleCount,
          availableTotalSamples,
          controllerStateA:requestedA,
          upscaleSinceAt:Number.isFinite(upscaleSinceMs)
            ?new Date(upscaleSinceMs).toISOString()
            :null,
          actualProductionA:phasePhysicalA,
          actualProductionCurrentSource:
            rawChargeState==='plugged_in_charging'&&offeredAUsable
              ?'EASEE_OFFERED_CURRENT'
              :'CONTROLLER_STATE_FALLBACK',
          actualProductionPhaseCount,
          confirmedPhaseMode,
          confirmedPhaseRaw,
          physicalPhaseOwner:'EASEE_EQUALIZER',
          phaseCommand:null,
          modeSinceAt,
          upwardModeDwellMs:previousMode==='OFF'?EVPC_OFF_REENTRY_DWELL_MS:previousMode==='1P'?EVPC_1P_TO_3P_DWELL_MS:null,
          offReentryDwellMs:EVPC_OFF_REENTRY_DWELL_MS,
          onePTo3pDwellMs:EVPC_1P_TO_3P_DWELL_MS,
          predictiveDesiredA:Number.isFinite(realtime.predictiveDesiredA)?realtime.predictiveDesiredA:requestedA,
          rollingDesiredA:Number.isFinite(realtime.rollingDesiredA)?realtime.rollingDesiredA:requestedA,
          currentExportW:Number.isFinite(realtime.currentExportW)?realtime.currentExportW:Math.max(0,Math.round(-p1W)),
          physicalTargetSettled:realtime.physicalTargetSettled!==false,
          adaptive3pCandidateStepA:Number.isFinite(realtime.adaptive3pCandidateStepA)?realtime.adaptive3pCandidateStepA:0,
          appliedUpscaleStepA:Number.isFinite(realtime.appliedUpscaleStepA)?realtime.appliedUpscaleStepA:0,
          maxUpscaleStep1pA:EVPC_MAX_UPSTEP_1P_A,
          maxUpscaleStep3pA:EVPC_MAX_UPSTEP_3P_A,
          maxAdaptiveUpscaleStep3pA:EVPC_MAX_ADAPTIVE_UPSTEP_3P_A,
          upscaleImportTargetW:EVPC_UPSCALE_IMPORT_TARGET_W,
          importDeadbandW:EVPC_IMPORT_DEADBAND_W,
          currentImportLimitW:EVPC_CURRENT_IMPORT_LIMIT_W,
          shadow:true,
          deviceWrites:false,
          controlWrites:false
        };

        const sampleAt=new Date().toISOString();
        const exportW=Math.max(0,-p1W);
        const kept=evV2Shadow.samples
          .filter(s=>s&&Number.isFinite(num(s.availablePvW))&&Date.parse(String(s.at||''))<Date.parse(sampleAt))
          .slice(-4);
        kept.push({at:sampleAt,availablePvW:Math.round(exportW)});
        evV2Shadow.samples=kept;
        evV2Shadow.lastSampleAt=sampleAt;
        evV2Shadow.rolling5mW=Math.round(
          kept.reduce((sum,s)=>sum+num(s.availablePvW),0)/kept.length
        );

        evW=requestedW;
        evStatus=requestedA>0?'NUMERIC_REALTIME_PV_TARGET':'IDLE';
        source='HOMEY_PHASE_CURRENT_CONTROLLER_V0.1';
        reason=phaseChanged
          ?phaseReason
          :currentChanged
            ?currentReason
            :'REALTIME_P1_HOLD';

        realtime.applied=true;
        realtime.fallbackReason=null;
        realtime.p1W=Math.round(p1W);
        realtime.p1AgeSec=p1Ts===null?null:Math.round((Date.now()-p1Ts)/1000);
        realtime.evActualW=Math.round(actualEvW);
        realtime.evPowerAgeSec=null;
        realtime.counterfactualSurplusW=Math.round(availableTotalW);
        // Compatibility aliases now mirror the single authoritative controller;
        // they are no longer produced by a second current-control loop.
        realtime.candidateA=requestedA;
        realtime.candidateW=requestedW;
      }
    }catch(rtErr){realtime.applied=false;realtime.fallbackReason=String(rtErr?.message||rtErr);evW=plannerEvW;evStatus=evW>0?'PI_NUMERIC_TARGET':'IDLE';source='PI_DYNAMIC_PLANNER_V0.3';reason=`REALTIME_FALLBACK_${realtime.fallbackReason}`;}
  }else realtime.fallbackReason=env.allowed===true?'INVALID_PRODUCTION_ENVELOPE':(env.blockReason||'REALTIME_NOT_ALLOWED');

  // Executor-side hard deadline guard runs last. Deadline planning state is
  // authoritative from Pi; Homey contributes only live connection/charge state
  // and the local configured hardware cap.
  const dl=cmd?.deadline||{};
  const dlSchemaOK=dl.schema==='EMS_PI_EV_DEADLINE_EXECUTION_V0.1';
  const dlAuthorityOK=dl.authority==='PI';
  const dlValid=dl.valid===true;
  deadlineActive=dlSchemaOK&&dlAuthorityOK&&dlValid&&dl.active===true;
  deadlineChargeState=String(coreState?.tesla?.chargeState||'unknown').toLowerCase();
  deadlineTeslaConnected=(coreState?.tesla?.connected===true)||connectedState(deadlineChargeState);
  deadlineRemainingKWh=Math.max(0,num(dl.remainingKWh)||0);
  deadlineAt=dl.deadlineAt||null;latestStartAt=dl.latestStartAt||null;
  // Pi deadline contract owns the request-specific maxA. The former Homey
  // 'EV Max laadstroom A' variable was written by the now-disabled legacy
  // deadline adapter and can therefore be stale across a new request.
  // Physical safety remains independently enforced by the actuator against
  // the live Easee circuit limit before any current write.
  const piMax=num(dl.maxA);
  const piCap=piMax!==null?Math.max(0,Math.min(16,Math.floor(piMax))):0;
  deadlineMaxA=piCap;
  const deadlineMs=Date.parse(String(deadlineAt||'')),explicitLatestMs=Date.parse(String(latestStartAt||'')),maxKw=deadlineMaxA*0.69;
  const derivedLatestMs=Number.isFinite(deadlineMs)&&maxKw>0?deadlineMs-(deadlineRemainingKWh/maxKw)*3600000:NaN;
  derivedLatestStartAt=Number.isFinite(derivedLatestMs)?new Date(derivedLatestMs).toISOString():null;
  let forceFromMs=Number.isFinite(explicitLatestMs)?explicitLatestMs:derivedLatestMs;if(Number.isFinite(explicitLatestMs)&&Number.isFinite(derivedLatestMs))forceFromMs=Math.min(explicitLatestMs,derivedLatestMs);
  forceFromAt=Number.isFinite(forceFromMs)?new Date(forceFromMs).toISOString():null;
  deadlineOverdue=deadlineActive&&deadlineRemainingKWh>0&&Number.isFinite(deadlineMs)&&Date.now()>=deadlineMs;
  if(deadlineActive&&deadlineTeslaConnected&&deadlineRemainingKWh>0&&deadlineMaxA>0&&Number.isFinite(deadlineMs)&&deadlineMs>Date.now()&&Number.isFinite(forceFromMs)&&Date.now()>=forceFromMs){evW=deadlineMaxA*EV_W_PER_A;evStatus='NUMERIC_DEADLINE_TARGET';source='REMAINING_KWH_OVER_TIME_TO_DEADLINE';reason='HOMEY_EXECUTOR_DEADLINE_GUARD';deadlineGuardApplied=true;}

  stage='INTENT_WRITE';await writeDiag();await writeIntent();stage='INTENT_WRITE_OK';await writeDiag({result:'SUCCESS'});return true;
}catch(e){
  valid=false;status='PI_BRIDGE_ERROR';source='PI_FAIL_CLOSED';evStatus='FAIL_CLOSED_PI_UNAVAILABLE';reason=`${stage}:${String(e?.message||e)}`;
  const failedStage=stage;stage=`ERROR_${failedStage}`;await writeDiag({result:'FAIL'});
  try{await writeIntent();}catch(writeErr){await writeDiag({result:'FAIL_CLOSED_WRITE_FAILED',writeError:String(writeErr?.message||writeErr)});throw new Error(`PI_BRIDGE_FAIL_CLOSED_WRITE_FAILED:${reason}:WRITE:${String(writeErr?.message||writeErr)}`);}return false;
}
