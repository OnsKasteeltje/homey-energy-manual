// PI Dynamic Planner -> EM2 Power Intent bridge v1.3.0.
// Adds bounded realtime PV execution inside Pi envelope V0.3.
// No direct device writes: output remains EM2_Power_Intent; EV Adapter/Gate/Actuator own execution.
const SELECTOR_ID='ba9c22ba-4332-4b19-9bda-dfe476862176';
const IDS={state:'8e1efbb0-7999-494c-9429-7d274afacd79',intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',diag:'14e6c83f-e881-4ad5-8876-af1ce9e2a1a1',maxA:'4a7398bb-9253-49ab-8850-820d1a622bd6'};
const P1_ID='7a696d77-15fb-4b68-9bce-f1e39bff5045';
const EASEE_ID='4d0b6913-d940-474e-95d6-b43f194c4119';
const URLS=['http://192.168.1.42:3100/control/current'];
const POLICY='PI_DYNAMIC_PLANNER_BRIDGE_V1.3.0_REALTIME_PV_DEADLINE_GUARD';
const ENGINE='PI_DYNAMIC_PLANNER_V0.3_LAN_BRIDGE';
const RT_SCHEMA='EMS_PI_EV_REALTIME_ENVELOPE_V0.3';
const EV_W_PER_A=690, MIN_A=6, MAX_A=16, P1_FRESH_MS=180000, EV_POWER_FRESH_MS=180000;
const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};
const bool=x=>x===true||String(x).toLowerCase()==='true';
const cap=(d,id)=>d?.capabilitiesObj?.[id]?.value;
const capUpdated=(d,id)=>{const ms=Date.parse(String(d?.capabilitiesObj?.[id]?.lastUpdated||''));return Number.isFinite(ms)?ms:null;};
const connectedState=s=>['plugged_in','plugged_in_paused','plugged_in_charging'].includes(String(s||'').toLowerCase());
let devicesCache=null;
const getDevice=async id=>{if(typeof Homey.devices?.getDevice==='function')return await Homey.devices.getDevice({id});if(!devicesCache)devicesCache=await Homey.devices.getDevices();return devicesCache?.[id]||null;};
let stage='SELECTOR_READ',intentVar=null,diagVar=null,coreState=null,stateRev=null,plannerGeneratedAt=null,commandValidUntil=null,evW=0,evStatus='IDLE',wwOn=null,source='PI_FAIL_CLOSED',reason='UNINITIALIZED',valid=false,status='PI_BRIDGE_ERROR';
let deadlineGuardApplied=false,deadlineActive=false,deadlineTeslaConnected=false,deadlineChargeState='unknown',deadlineAt=null,latestStartAt=null,derivedLatestStartAt=null,forceFromAt=null,deadlineRemainingKWh=0,deadlineMaxA=null,deadlineOverdue=false;
let realtime={schema:'EM2_EV_REALTIME_EXECUTION_V0.1',eligible:false,applied:false,fallbackReason:null,envelopeSchema:null,envelopeAllowed:false,minA:0,maxA:0,p1W:null,p1AgeSec:null,chargeState:null,evActualW:null,evPowerAgeSec:null,counterfactualSurplusW:null,candidateA:null,candidateW:null,plannerTargetA:0,plannerTargetW:0};
const writeDiag=async(extra={})=>{try{if(!diagVar)diagVar=await Homey.logic.getVariable({id:IDS.diag});if(!diagVar)return;const obj={schema:'EM2_PI_BRIDGE_DIAGNOSTIC_V0.2',updatedAt:new Date().toISOString(),policyRevision:POLICY,stage,status,reason,valid,stateRevision:stateRev,plannerGeneratedAt,commandValidUntil,evTargetW:evW,evTargetStatus:evStatus,wwTargetOn:wwOn,authority:'PI',persistent:true,realtime,deadlineGuard:{active:deadlineActive,teslaConnected:deadlineTeslaConnected,chargeState:deadlineChargeState,applied:deadlineGuardApplied,deadlineAt,latestStartAt,derivedLatestStartAt,forceFromAt,remainingKWh:deadlineRemainingKWh,maxA:deadlineMaxA,overdue:deadlineOverdue},...extra};await Homey.logic.updateVariable({id:IDS.diag,variable:{value:JSON.stringify(obj)}});}catch(_){}};
const selectorV=await Homey.logic.getVariable({id:SELECTOR_ID});
if(!selectorV||selectorV.value!=='PI') return true;
const writeIntent=async()=>{if(!intentVar)return false;const now=new Date().toISOString();const out={schema:'EM2_POWER_INTENT_V0.2',policyRevision:POLICY,engineVersion:ENGINE,generatedAt:now,sourceRevision:stateRev,readOnly:true,controlMode:'SHADOW',deviceWrites:false,valid,status,inputSemanticKey:JSON.stringify({stateRev,plannerGeneratedAt,commandValidUntil,evW,evStatus,wwOn,valid,stage,realtime,deadlineGuardApplied,deadlineTeslaConnected,deadlineChargeState,deadlineAt,forceFromAt,deadlineRemainingKWh,deadlineMaxA}),inputRevisions:{state:stateRev,planner:plannerGeneratedAt},policyProjection:{plannerOwner:'PI',executor:'HOMEY',authoritySelector:'PI',contractMode:'FIXED',contractId:'ENGIE_3Y_2026_2029',reason,commandValidUntil,bridgeStage:stage,realtime,deadlineGuardApplied,deadlineTeslaConnected,deadlineChargeState,deadlineAt,latestStartAt,derivedLatestStartAt,forceFromAt,deadlineRemainingKWh,deadlineMaxA},targets:{ev:{target_W:valid?evW:0,status:valid?evStatus:'FAIL_CLOSED_PI_UNAVAILABLE',source},ww:{target_W:null,target_on:valid?wwOn:false,status:valid?'PI_BINARY_TARGET':'FAIL_CLOSED_PI_UNAVAILABLE',sourceAction:wwOn===true?'BOILER_ON':wwOn===false?'BOILER_OFF':'HOLD'},battery:{target_W:0,status:'NOT_INTEGRATED'}},safety:{logicOnly:true,noDeviceWrites:true,plannerOwner:'PI',homeyRole:'EXECUTOR_SAFETY',fixedContractEnforced:true,failClosed:true,staleCommandRejected:true,singleWriterGuard:true,requiredAuthority:'PI',authorityGate:'EM2_Planner_Authority',bridgeUrls:URLS,diagnosticStage:stage,persistentDiagnostic:true,realtimeEnvelopeSchema:RT_SCHEMA,boundedRealtimePv:true,deadlineGuard:true,deadlineRequiresConnectedTesla:true,deadlineConnectivitySource:'CORE_TESLA_CHARGE_STATE',deadlineBeforeLatestStartPreservesPiTarget:true}};const value=JSON.stringify(out);if(intentVar.value!==value)await Homey.logic.updateVariable({id:IDS.intent,variable:{value}});return true;};
try{
  stage='LOGIC_READ';
  const vars=await Promise.all([Homey.logic.getVariable({id:IDS.state}),Homey.logic.getVariable({id:IDS.intent}),Homey.logic.getVariable({id:IDS.diag}),Homey.logic.getVariable({id:IDS.maxA})]);
  const stateVar=vars[0],maxAVar=vars[3];intentVar=vars[1];diagVar=vars[2];
  if(!stateVar||!intentVar||!diagVar||!maxAVar)throw new Error('PI_BRIDGE_REQUIRED_VARIABLE_MISSING');
  stage='LOGIC_OK';
  coreState=parse(stateVar.value);stateRev=num(coreState?.revision);if(stateRev===null)throw new Error('STATE_REVISION_MISSING');
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
      const chargeState=String(cap(easee,'evcharger_charging_state')||coreState?.tesla?.chargeState||'unknown').toLowerCase();
      realtime.chargeState=chargeState;
      if(!connectedState(chargeState)){evW=0;evStatus='IDLE';source='HOMEY_BOUNDED_REALTIME_PV';reason='REALTIME_TESLA_NOT_CONNECTED';realtime.applied=true;realtime.fallbackReason=null;realtime.p1W=Math.round(p1W);realtime.candidateA=0;realtime.candidateW=0;}
      else{
        let evActualW=0,evAgeSec=null;
        if(chargeState==='plugged_in_charging'){
          const evP=num(cap(easee,'measure_power'));if(evP===null||evP<0)throw new Error('EV_ACTUAL_POWER_INVALID');
          const evTs=capUpdated(easee,'measure_power');if(evTs!==null){evAgeSec=Math.round((Date.now()-evTs)/1000);if(Date.now()-evTs>EV_POWER_FRESH_MS)throw new Error('EV_ACTUAL_POWER_STALE');}
          evActualW=evP;
        }
        const surplus=Math.max(0,-p1W+evActualW);
        const rawA=Math.floor(surplus/EV_W_PER_A);const candidateA=rawA<minA?0:Math.max(minA,Math.min(maxA,rawA));
        evW=candidateA*EV_W_PER_A;evStatus=candidateA>0?'NUMERIC_REALTIME_PV_TARGET':'IDLE';source='HOMEY_BOUNDED_REALTIME_PV';reason=candidateA>0?'REALTIME_PV_OPPORTUNITY':'REALTIME_PV_BELOW_START6';
        realtime.applied=true;realtime.fallbackReason=null;realtime.p1W=Math.round(p1W);realtime.p1AgeSec=p1Ts===null?null:Math.round((Date.now()-p1Ts)/1000);realtime.evActualW=Math.round(evActualW);realtime.evPowerAgeSec=evAgeSec;realtime.counterfactualSurplusW=Math.round(surplus);realtime.candidateA=candidateA;realtime.candidateW=evW;
      }
    }catch(rtErr){realtime.applied=false;realtime.fallbackReason=String(rtErr?.message||rtErr);evW=plannerEvW;evStatus=evW>0?'PI_NUMERIC_TARGET':'IDLE';source='PI_DYNAMIC_PLANNER_V0.3';reason=`REALTIME_FALLBACK_${realtime.fallbackReason}`;}
  }else realtime.fallbackReason=env.allowed===true?'INVALID_PRODUCTION_ENVELOPE':(env.blockReason||'REALTIME_NOT_ALLOWED');

  // Executor-side hard deadline guard runs last and always overrides opportunity logic when required.
  const goals=coreState?.goals||{};
  deadlineActive=bool(goals.teslaDeadlineActive);
  deadlineChargeState=String(coreState?.tesla?.chargeState||'unknown').toLowerCase();
  deadlineTeslaConnected=(coreState?.tesla?.connected===true)||connectedState(deadlineChargeState);
  deadlineRemainingKWh=Math.max(0,num(goals.teslaRemainingKWh)||0);
  deadlineAt=goals.teslaDeadline||null;latestStartAt=goals.teslaLatestStart||null;
  const goalMax=num(goals.teslaMaxA),configMax=num(maxAVar?.value);
  const goalCap=goalMax!==null?Math.max(0,Math.min(16,Math.floor(goalMax))):16;
  const configCap=configMax!==null?Math.max(0,Math.min(16,Math.floor(configMax))):16;
  deadlineMaxA=Math.min(goalCap,configCap);
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
