// PI Dynamic Planner -> EM2 Power Intent bridge v1.5.2 PHASE-AUTHORITY.
// Adds bounded realtime PV execution inside Pi envelope V0.3.
// No direct device writes: output remains EM2_Power_Intent; EV Adapter/Gate/Actuator own execution.
const SELECTOR_ID='ba9c22ba-4332-4b19-9bda-dfe476862176';
const IDS={state:'8e1efbb0-7999-494c-9429-7d274afacd79',intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',diag:'14e6c83f-e881-4ad5-8876-af1ce9e2a1a1',maxA:'4a7398bb-9253-49ab-8850-820d1a622bd6'};
const P1_ID='7a696d77-15fb-4b68-9bce-f1e39bff5045';
const EASEE_ID='4d0b6913-d940-474e-95d6-b43f194c4119';
const URLS=['http://192.168.1.42:3100/control/current'];
const POLICY='PI_DYNAMIC_PLANNER_BRIDGE_V1.5.2_PHASE_AUTHORITY';
const ENGINE='PI_DYNAMIC_PLANNER_V0.3_LAN_BRIDGE';
const RT_SCHEMA='EMS_PI_EV_REALTIME_ENVELOPE_V0.4';
const EV_W_PER_A=690, MIN_A=6, MAX_A=16, P1_FRESH_MS=180000;
const P1_UP_THRESHOLD_W=EV_W_PER_A, P1_DOWN_THRESHOLD_W=250, DISCONNECT_GRACE_MS=180000;
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
let devicesCache=null;
const getDevice=async id=>{if(typeof Homey.devices?.getDevice==='function')return await Homey.devices.getDevice({id});if(!devicesCache)devicesCache=await Homey.devices.getDevices();return devicesCache?.[id]||null;};
let stage='SELECTOR_READ',intentVar=null,diagVar=null,coreState=null,stateRev=null,plannerGeneratedAt=null,commandValidUntil=null,evW=0,evStatus='IDLE',wwOn=null,source='PI_FAIL_CLOSED',reason='UNINITIALIZED',valid=false,status='PI_BRIDGE_ERROR';
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
      source:'REALTIME_PHASE_SELECTOR'
    };
  }
  const fallbackA=Math.max(0,Math.min(MAX_A,Math.floor(Math.max(0,num(evW)||0)/EV_W_PER_A)));
  if(fallbackA>=MIN_A){
    return {schema:'EM2_EV_PHASE_CONTROL_V0.1',authoritative:true,mode:'3P',requestedA:fallbackA,requestedW:fallbackA*EV_W_PER_A,source:'PI_3P_FALLBACK'};
  }
  return {schema:'EM2_EV_PHASE_CONTROL_V0.1',authoritative:true,mode:'OFF',requestedA:0,requestedW:0,source:'IDLE'};
};
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
    inputSemanticKey:JSON.stringify({stateRev,plannerGeneratedAt,commandValidUntil,evW,evStatus,wwOn,valid,stage,realtime,deadlineGuardApplied,deadlineTeslaConnected,deadlineChargeState,deadlineAt,forceFromAt,deadlineRemainingKWh,deadlineMaxA}),
    inputRevisions:{state:stateRev,planner:plannerGeneratedAt},
    policyProjection:{
      plannerOwner:'PI',
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
  const vars=await Promise.all([Homey.logic.getVariable({id:IDS.state}),Homey.logic.getVariable({id:IDS.intent}),Homey.logic.getVariable({id:IDS.diag}),Homey.logic.getVariable({id:IDS.maxA})]);
  const stateVar=vars[0],maxAVar=vars[3];intentVar=vars[1];diagVar=vars[2];
  if(!stateVar||!intentVar||!diagVar||!maxAVar)throw new Error('PI_BRIDGE_REQUIRED_VARIABLE_MISSING');
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
  stage='VALIDATION_OK';
  const plannerEvW=Math.max(0,Math.round(num(t?.ev?.target_W)||0));
  const plannerEvA=Math.max(0,Math.round(num(t?.ev?.target_A)||0));
  evW=plannerEvW;evStatus=evW>0?'PI_NUMERIC_TARGET':'IDLE';
  wwOn=t?.ww?.target_on===true?true:t?.ww?.target_on===false?false:null;
  valid=true;status='OK';source='PI_DYNAMIC_PLANNER_V0.3';reason=t?.ev?.reason||t?.ww?.reason||'PI_DYNAMIC_SLOT';
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
      const coreChargeState=String(coreState?.tesla?.chargeState||'unknown').toLowerCase();
      const offeredNow=num(cap(easee,'measure_current.offered'));
      const chargerPowerNow=num(cap(easee,'measure_power'));
      const chargerChargingNow=cap(easee,'evcharger_charging')===true;

      const directConnectedEvidence=
        connectedState(rawChargeState) ||
        chargerChargingNow ||
        (offeredNow!==null&&offeredNow>1) ||
        (chargerPowerNow!==null&&chargerPowerNow>250) ||
        coreState?.tesla?.connected===true ||
        connectedState(coreChargeState);

      const previousGuard=previousIntent?.policyProjection?.realtime?.connectionGuard||{};
      const previousEv=previousIntent?.targets?.ev||{};
      const previousIntentAt=Date.parse(String(previousIntent?.generatedAt||''));
      const previousIntentAgeMs=Number.isFinite(previousIntentAt)?Date.now()-previousIntentAt:Infinity;
      const previousNonOff=
        ['1P','3P'].includes(String(previousEv?.phase_mode||'')) &&
        (num(previousEv?.phase_requested_A)||0)>=MIN_A &&
        previousIntentAgeMs<=DISCONNECT_GRACE_MS;
      const previouslyConnected=
        previousGuard?.effectiveConnected===true ||
        previousNonOff;

      let disconnectObservedAt=
        directConnectedEvidence
          ?null
          :(previousGuard?.disconnectObservedAt||null);
      if(!directConnectedEvidence&&previouslyConnected&&!disconnectObservedAt){
        disconnectObservedAt=new Date().toISOString();
      }
      const disconnectObservedMs=Date.parse(String(disconnectObservedAt||''));
      const disconnectAgeMs=
        Number.isFinite(disconnectObservedMs)
          ?Math.max(0,Date.now()-disconnectObservedMs)
          :null;
      const disconnectGraceActive=
        !directConnectedEvidence &&
        previouslyConnected &&
        disconnectAgeMs!==null &&
        disconnectAgeMs<DISCONNECT_GRACE_MS;
      const effectiveConnected=
        directConnectedEvidence ||
        disconnectGraceActive;

      realtime.chargeState=rawChargeState;
      realtime.connectionGuard={
        rawChargeState,
        coreChargeState,
        directConnectedEvidence,
        effectiveConnected,
        disconnectGraceActive,
        disconnectObservedAt,
        disconnectAgeSec:disconnectAgeMs===null?null:Math.round(disconnectAgeMs/1000),
        graceSec:Math.round(DISCONNECT_GRACE_MS/1000),
        evidence:{
          homeyConnectedState:connectedState(rawChargeState),
          charging:chargerChargingNow,
          offeredA:offeredNow,
          powerW:chargerPowerNow,
          coreConnected:coreState?.tesla?.connected===true,
          coreChargeStateConnected:connectedState(coreChargeState)
        }
      };

      if(!effectiveConnected){evW=0;evStatus='IDLE';source='HOMEY_BOUNDED_REALTIME_PV';reason='REALTIME_TESLA_NOT_CONNECTED_CONFIRMED';realtime.applied=true;realtime.fallbackReason=null;realtime.p1W=Math.round(p1W);realtime.candidateA=0;realtime.candidateW=0;}
      else{
        // P1 is authoritative for realtime EV feedback.
        // A single transient plugged_out cannot immediately remove EV authority:
        // connection loss must persist beyond the bounded grace window unless
        // fresh charging/current/power/core evidence says the car is connected.
        const previousRealtimeA=num(
          previousIntent?.policyProjection?.realtime?.candidateA
        );
        const previousRealtimeApplied=
          previousIntent?.policyProjection?.realtime?.applied===true;

        const currentA=Math.max(
          0,
          Math.min(
            maxA,
            Math.round(
              previousRealtimeApplied && previousRealtimeA!==null
                ? previousRealtimeA
                : plannerEvA
            )
          )
        );

        const confirmedPhaseRaw=
          realtime.confirmedPhaseRaw!==null
            ?realtime.confirmedPhaseRaw
            :await readPhaseMode(easee);
        const confirmedPhaseMode=normalizePhaseMode(confirmedPhaseRaw);

        // SHADOW physical reconstruction must not treat the previous realtime
        // controller command as physical EV load while the session is paused
        // or merely plugged in. That command remains controller state for the
        // proven fixed-3P production loop below, but physical add-back for
        // phase SHADOW is zero unless Homey observes active charging.
        // Physical EV reconstruction for phase selection must follow the
        // charger state actually being offered, not a stale previous controller
        // command. P1 remains the authoritative grid signal; Easee offered
        // current is used only to add back the EV load already consuming PV.
        const offeredA=num(cap(easee,'measure_current.offered'));
        const offeredAUsable=
          offeredA!==null &&
          offeredA>=0 &&
          offeredA<=MAX_A;
        const phaseShadowPhysicalA=
          chargeState==='plugged_in_charging'
            ?(offeredAUsable?Math.round(offeredA):currentA)
            :0;
        const actualProductionPhaseCount=phaseShadowPhysicalA<=0
          ?0
          :confirmedPhaseMode==='1P'
            ?1
            :confirmedPhaseMode==='3P'
              ?3
              :null;
        realtime.confirmedPhaseRaw=confirmedPhaseRaw;
        realtime.confirmedPhaseMode=confirmedPhaseMode;
        realtime.actualProductionPhaseCount=actualProductionPhaseCount;

        let candidateA=currentA;

        // SHADOW only: evaluate OFF | 1P+A | 3P+A from fresh total P1 while
        // production remains the proven fixed-3P controller below.
        if(phasePolicyValid){
          const pp=phasePolicy;
          const previousPhase=previousIntent?.policyProjection?.realtime?.phaseShadow||{};
          const previousMode=['1P','3P'].includes(String(previousPhase?.mode||''))?String(previousPhase.mode):'OFF';
          const previousSinceMs=Date.parse(String(previousPhase?.modeSinceAt||''));
          const dwellMs=Math.max(0,Math.round(num(pp.minModeDwellSec)||0))*1000;
          const dwellOK=!Number.isFinite(previousSinceMs)||(Date.now()-previousSinceMs)>=dwellMs;
          const phaseReadbackValid=phaseShadowPhysicalA===0||actualProductionPhaseCount===1||actualProductionPhaseCount===3;
          const actualEvW=phaseReadbackValid
            ?phaseShadowPhysicalA*230*(actualProductionPhaseCount||0)
            :0;
          const availableTotalW=phaseReadbackValid?Math.max(0,-p1W+actualEvW):0;
          const start1pW=Math.max(0,Math.round(num(pp.start1p_W)||0));
          const stop1pW=Math.max(0,Math.round(num(pp.stop1p_W)||0));
          const enter3pW=Math.max(0,Math.round(num(pp.enter3p_W)||0));
          const leave3pW=Math.max(0,Math.round(num(pp.leave3p_W)||0));
          let phaseMode=phaseReadbackValid?previousMode:'OFF';
          let phaseReason=phaseReadbackValid?'HOLD':'PHASE_READBACK_UNCONFIRMED';
          if(phaseReadbackValid&&previousMode==='3P'){
            if(availableTotalW<leave3pW&&dwellOK){
              if(availableTotalW>=start1pW){phaseMode='1P';phaseReason='3P_TO_1P_TOTAL_SURPLUS_LOW';}
              else{phaseMode='OFF';phaseReason='3P_TO_OFF_SURPLUS_LOW';}
            }
          }else if(phaseReadbackValid&&previousMode==='1P'){
            if(availableTotalW>=enter3pW&&dwellOK){phaseMode='3P';phaseReason='1P_TO_3P_TOTAL_SURPLUS_HIGH';}
            else if(availableTotalW<stop1pW&&dwellOK){phaseMode='OFF';phaseReason='1P_TO_OFF_TOTAL_SURPLUS_LOW';}
          }else if(phaseReadbackValid){
            if(availableTotalW>=enter3pW){phaseMode='3P';phaseReason='OFF_TO_3P_TOTAL_SURPLUS';}
            else if(availableTotalW>=start1pW){phaseMode='1P';phaseReason='OFF_TO_1P_TOTAL_SURPLUS';}
          }
          let phaseA=0;
          if(phaseMode==='1P')phaseA=Math.max(MIN_A,Math.min(maxA,Math.floor(availableTotalW/230)));
          if(phaseMode==='3P')phaseA=Math.max(MIN_A,Math.min(maxA,Math.floor(availableTotalW/690)));
          const phaseChanged=phaseMode!==previousMode;
          realtime.phaseShadow={
            schema:'EM2_EV_PHASE_EXECUTION_SHADOW_V0.1',
            mode:phaseMode,
            requestedA:phaseA,
            requestedW:phaseMode==='1P'?phaseA*230:phaseMode==='3P'?phaseA*690:0,
            reason:phaseReason,
            availableTotalW:Math.round(availableTotalW),
            controllerStateA:currentA,
            actualProductionA:phaseShadowPhysicalA,
            actualProductionCurrentSource:
              chargeState==='plugged_in_charging'&&offeredAUsable
                ?'EASEE_OFFERED_CURRENT'
                :'CONTROLLER_STATE_FALLBACK',
            actualProductionPhaseCount,
            confirmedPhaseMode,
            confirmedPhaseRaw,
            physicalPhaseOwner:'EASEE_EQUALIZER',
            phaseCommand:null,
            modeSinceAt:phaseChanged?new Date().toISOString():(previousPhase?.modeSinceAt||new Date().toISOString()),
            shadow:true,
            deviceWrites:false,
            controlWrites:false
          };
        }

        if(currentA>=MIN_A){
          // P1 convention: negative = export, positive = import.
          // Upward movement stays deliberately one amp per cycle to avoid
          // overshoot while the car/charger is still ramping.
          //
          // Import cutback is proportional: remove enough 3-phase amps in
          // one control cycle to absorb the measured import above the
          // deadband. If the sustainable result falls below the 6A hardware
          // minimum, stop opportunity charging immediately.
          if(p1W<=-P1_UP_THRESHOLD_W && currentA<maxA){
            candidateA=currentA+1;
          }else if(p1W>P1_DOWN_THRESHOLD_W){
            const excessImportW=Math.max(0,p1W-P1_DOWN_THRESHOLD_W);
            const reductionA=Math.max(1,Math.ceil(excessImportW/EV_W_PER_A));
            realtime.importReductionA=reductionA;
            const reducedA=currentA-reductionA;
            candidateA=reducedA>=MIN_A?reducedA:0;
          }
        }else if(p1W<=-(MIN_A*EV_W_PER_A)){
          // Starting from zero still requires enough measured P1 export
          // for the complete 6A minimum charging load.
          candidateA=MIN_A;
        }else{
          candidateA=0;
        }

        candidateA=Math.max(0,Math.min(maxA,candidateA));

        const sampleAt=new Date().toISOString();
        const exportW=Math.max(0,-p1W);
        const kept=evV2Shadow.samples
          .filter(s=>s&&Number.isFinite(num(s.availablePvW))&&Date.parse(String(s.at||''))<Date.parse(sampleAt))
          .slice(-4);
        kept.push({at:sampleAt,availablePvW:Math.round(exportW)});
        evV2Shadow.samples=kept;
        evV2Shadow.lastSampleAt=sampleAt;
        evV2Shadow.rolling5mW=Math.round(
          kept.reduce((a,s)=>a+num(s.availablePvW),0)/kept.length
        );

        evW=candidateA*EV_W_PER_A;
        evStatus=candidateA>0?'NUMERIC_REALTIME_PV_TARGET':'IDLE';
        source='HOMEY_BOUNDED_REALTIME_PV';
        reason=candidateA>currentA
          ?'REALTIME_P1_EXPORT_STEP_UP'
          :candidateA<currentA
            ?'REALTIME_P1_IMPORT_PROPORTIONAL_DOWN'
            :'REALTIME_P1_HOLD';

        realtime.applied=true;
        realtime.fallbackReason=null;
        realtime.p1W=Math.round(p1W);
        realtime.p1AgeSec=p1Ts===null?null:Math.round((Date.now()-p1Ts)/1000);
        realtime.evActualW=null;
        realtime.evPowerAgeSec=null;
        realtime.counterfactualSurplusW=null;
        realtime.candidateA=candidateA;
        realtime.candidateW=evW;
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
  const piMax=num(dl.maxA),configMax=num(maxAVar?.value);
  const piCap=piMax!==null?Math.max(0,Math.min(16,Math.floor(piMax))):0;
  const configCap=configMax!==null?Math.max(0,Math.min(16,Math.floor(configMax))):16;
  deadlineMaxA=Math.min(piCap,configCap);
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
