// EV Actuator v0.4.4 PHASE-WRITER LIVE
// Bounded physical transaction: a required 1P<->3P transition is completed
// inside one HomeyScript invocation. No self-retrigger is used between stages.
//
// Transaction:
// PAUSE -> confirm paused -> set locked phase -> confirm phase -> 5 s deadtime
// -> temporary symmetric circuit cap -> RESUME -> set charger current
// -> confirm Easee accepted the opportunity -> restore original circuit cap -> STABLE.
//
// OPPORTUNITY CONTRACT: EMS offers charging capacity; Tesla decides whether to
// consume it. Actual Tesla current/power is observability only and MUST NOT be a
// success condition, timeout source or fail-closed trigger for opportunity charging.
//
// Bridge/Adapter/Gate remain command authority. P1/phase thresholds are unchanged.
// The writer only executes an already validated command and re-reads that command
// while safely paused so a PV-driven mode/current change can be absorbed before
// resume. Any Easee command/contract failure pauses the session and restores the
// captured circuit limit.

const VERSION='EM2_EV_ACTUATOR_V0.4.4_PHASE_WRITER';
const TRANSITION_SCHEMA='EM2_EV_PHASE_TRANSITION_STATE_V0.4';
const PHASE_EXECUTION_ENABLED=true;

const FLOW_ID='fea23193-a03f-49dd-9780-7e72ee48747d';
const CHARGER_ID='4d0b6913-d940-474e-95d6-b43f194c4119';
const CHARGER_SERIAL='ECHM6B9F';

const FRESH_MS=120000;
const RUN_LOCK_MS=35000;
const POLL_MS=500;
const PAUSE_TIMEOUT_MS=6000;
const PHASE_CONFIRM_TIMEOUT_MS=9000;
const PHASE_CLOUD_CONFIRM_INTERVAL_MS=2500;
const DEADTIME_MS=5000;
const CIRCUIT_CONFIRM_TIMEOUT_MS=5000;
const CURRENT_CONFIRM_TIMEOUT_MS=5000;
const PHASE_OBSERVATION_ID=38;
const EV_MIN_A=6,EV_MAX_A=16;
const MAX_REPLANS_WHILE_PAUSED=3;

const IDS={
  live:'8d47e98d-e4bc-4f47-8c02-c2aca7f7a978',
  status:'ea1f8a44-2f6c-490e-9b86-bae761886cf9',
  intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',
  adapter:'f2118322-d59d-4aa8-b478-234effc3983c',
  gate:'4c66836b-77ae-43b5-b8e0-b32af15b57bc',
  easeeVar1:'9bc21974-4863-4471-b9ac-a55b252fdfbd',
  easeeVar2:'2855a2ee-caa1-43b3-a9ef-ce91acd2ad42',
  easeeVar3:'832f3227-f2f6-4c95-9032-39c6160e966d'
};

const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const num=x=>{
  if(x===null||x===undefined||x==='')return null;
  const n=Number(x);
  return Number.isFinite(n)?n:null;
};
const age=x=>{
  const t=Date.parse(String(x||''));
  return Number.isFinite(t)?Date.now()-t:Infinity;
};
const iso=()=>new Date().toISOString();
// HomeyScript exposes global wait(ms); browser/node timers such as setTimeout are unavailable.
const sleep=ms=>wait(ms);
const cap=(d,id)=>d?.capabilitiesObj?.[id]?.value;

const normalizePhaseMode=raw=>{
  const s=String(raw??'').trim().toLowerCase();
  if(s==='1'||s==='1p'||s.includes('locked to single'))return '1P';
  if(s==='3'||s==='3p'||s.includes('locked to three'))return '3P';
  if(s==='2'||s==='auto')return 'AUTO';
  return 'UNKNOWN';
};
const phaseValue=mode=>mode==='1P'?1:mode==='3P'?3:null;

const findSettingValue=(node,id)=>{
  if(!node||typeof node!=='object')return null;
  if(node.id===id&&node.value!==undefined&&node.value!==null)return node.value;
  if(Array.isArray(node)){
    for(const child of node){
      const v=findSettingValue(child,id);
      if(v!==null)return v;
    }
  }else{
    for(const child of Object.values(node)){
      const v=findSettingValue(child,id);
      if(v!==null)return v;
    }
  }
  return null;
};

const readPhaseSetting=async charger=>{
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

const ACTION_IDS={
  pause:'homey:device:'+CHARGER_ID+':pauseCharging',
  resume:'homey:device:'+CHARGER_ID+':resumeCharging',
  circuit:'homey:device:'+CHARGER_ID+':circuitCurrentControl',
  current:'homey:device:'+CHARGER_ID+':setDynamicChargerCurrent'
};

const runNative=async(id,args={})=>Homey.flow.runFlowCardAction({id,args});
const pauseSession=()=>runNative(ACTION_IDS.pause,{});
const resumeSession=()=>runNative(ACTION_IDS.resume,{});
const setCircuitA=a=>runNative(ACTION_IDS.circuit,{current:a});
const setCurrentA=a=>runNative(ACTION_IDS.current,{current:a});

const postJson=async(url,body,accessToken)=>{
  const r=await fetch(url,{
    method:'POST',
    headers:{
      'Authorization':'Bearer '+accessToken,
      'Accept':'application/json',
      'Content-Type':'application/json'
    },
    body:JSON.stringify(body)
  });
  let payload=null;
  try{payload=await r.json();}catch(_){}
  if(!r.ok)throw new Error('EASEE_HTTP_'+r.status);
  return payload||{};
};

const getJson=async(url,accessToken)=>{
  const r=await fetch(url,{
    method:'GET',
    headers:{
      'Authorization':'Bearer '+accessToken,
      'Accept':'application/json'
    }
  });
  let payload=null;
  try{payload=await r.json();}catch(_){}
  if(!r.ok)throw new Error('EASEE_HTTP_'+r.status);
  return payload;
};

const findObservationValue=(node,id)=>{
  if(node===null||node===undefined)return null;
  if(Array.isArray(node)){
    for(const child of node){
      const v=findObservationValue(child,id);
      if(v!==null)return v;
    }
    return null;
  }
  if(typeof node!=='object')return null;
  const oid=Number(node.id??node.observationId??node.observationID);
  if(oid===id&&node.value!==undefined&&node.value!==null)return node.value;
  for(const child of Object.values(node)){
    const v=findObservationValue(child,id);
    if(v!==null)return v;
  }
  return null;
};

const readEaseeVars=async()=>{
  const [a,r,e]=await Promise.all([
    Homey.logic.getVariable({id:IDS.easeeVar1}),
    Homey.logic.getVariable({id:IDS.easeeVar2}),
    Homey.logic.getVariable({id:IDS.easeeVar3})
  ]);
  return {a,r,e};
};

const getAccessToken=async vars=>{
  let access=String(vars.a?.value||'').trim();
  let refresh=String(vars.r?.value||'').trim();
  const expiresAt=Date.parse(String(vars.e?.value||''));
  if(!access||!refresh)throw new Error('EASEE_TOKEN_MISSING');

  if(!Number.isFinite(expiresAt)||expiresAt<=Date.now()+60000){
    const payload=await postJson(
      'https://api.easee.com/api/accounts/refresh_token',
      {refreshToken:refresh},
      access
    );
    const nextAccess=String(payload?.accessToken||'').trim();
    const nextRefresh=String(payload?.refreshToken||'').trim();
    const expiresIn=Number(payload?.expiresIn);
    if(!nextAccess||!nextRefresh||!Number.isFinite(expiresIn)||expiresIn<=0){
      throw new Error('EASEE_REFRESH_INVALID');
    }
    const nextExpiry=new Date(Date.now()+Math.max(60,expiresIn-60)*1000).toISOString();
    await Promise.all([
      Homey.logic.updateVariable({id:IDS.easeeVar1,variable:{value:nextAccess}}),
      Homey.logic.updateVariable({id:IDS.easeeVar2,variable:{value:nextRefresh}}),
      Homey.logic.updateVariable({id:IDS.easeeVar3,variable:{value:nextExpiry}})
    ]);
    access=nextAccess;
  }
  return access;
};

const setPhaseMode=async(mode,vars)=>{
  const pv=phaseValue(mode);
  if(![1,3].includes(pv))throw new Error('PHASE_MODE_INVALID');
  const access=await getAccessToken(vars);
  await postJson(
    'https://api.easee.com/api/chargers/'+encodeURIComponent(CHARGER_SERIAL)+'/commands/set_phase_mode',
    {phaseMode:pv},
    access
  );
};

const readCloudPhaseMode=async vars=>{
  const access=await getAccessToken(vars);
  const payload=await getJson(
    'https://api.easee.com/state/'+encodeURIComponent(CHARGER_SERIAL)+'/observations?ids='+PHASE_OBSERVATION_ID,
    access
  );
  return findObservationValue(payload,PHASE_OBSERVATION_ID);
};

const readControl=async()=>{
  const [intentVar,adapterVar,gateVar]=await Promise.all([
    Homey.logic.getVariable({id:IDS.intent}),
    Homey.logic.getVariable({id:IDS.adapter}),
    Homey.logic.getVariable({id:IDS.gate})
  ]);
  const intent=parse(intentVar?.value);
  const adapter=parse(adapterVar?.value);
  const gate=parse(gateVar?.value);
  const cmd=adapter?.command||{};
  const ev=intent?.targets?.ev||{};

  const controlRevision=String(intent?.controlRevision||'');
  const mode=String(cmd?.mode||'OFF');
  const requestedA=num(cmd?.requested_A);
  const requestedW=num(cmd?.requested_W);
  const targetW=num(ev?.target_W);

  const aligned=
    intent?.schema==='EM2_POWER_INTENT_V0.2' &&
    adapter?.schema==='EM2_EV_POWER_ADAPTER_V0.2' &&
    gate?.schema==='EM2_EV_ADAPTER_GATE_V0.3' &&
    cmd?.schema==='EM2_EV_PHASE_COMMAND_V0.1' &&
    !!controlRevision &&
    String(adapter?.controlRevision||'')===controlRevision &&
    String(gate?.controlRevision||'')===controlRevision &&
    String(gate?.adapterControlRevision||'')===controlRevision &&
    adapter?.valid===true &&
    gate?.finalStatus==='PASS';

  const requestValid=
    ['OFF','1P','3P'].includes(mode) &&
    Number.isInteger(requestedA) &&
    Number.isInteger(requestedW) &&
    requestedW===targetW &&
    (
      (mode==='OFF'&&requestedA===0&&requestedW===0) ||
      (mode==='1P'&&requestedA>=EV_MIN_A&&requestedA<=EV_MAX_A&&requestedW===requestedA*230) ||
      (mode==='3P'&&requestedA>=EV_MIN_A&&requestedA<=EV_MAX_A&&requestedW===requestedA*690)
    );

  const fresh=
    age(intent?.generatedAt)<=FRESH_MS &&
    age(adapter?.generatedAt)<=FRESH_MS &&
    age(gate?.updatedAt)<=FRESH_MS;

  const deadlineTarget=
    String(ev?.status||'')==='NUMERIC_DEADLINE_TARGET' ||
    String(ev?.source||'')==='REMAINING_KWH_OVER_TIME_TO_DEADLINE';
  const deadlinePhaseOK=!deadlineTarget||mode==='3P';

  let error=null;
  if(!aligned)error='CONTROL_CONTRACT_NOT_ALIGNED';
  else if(!fresh)error='CONTROL_NOT_FRESH';
  else if(!requestValid)error='INVALID_PHASE_REQUEST';
  else if(!deadlinePhaseOK)error='DEADLINE_MUST_USE_3P';

  return {
    ok:error===null,
    error,
    controlRevision,
    mode,
    requestedA,
    requestedW,
    targetW,
    deadlineTarget,
    generatedAt:intent?.generatedAt,
    adapterGeneratedAt:adapter?.generatedAt,
    gateUpdatedAt:gate?.updatedAt
  };
};

const readHardware=async()=>{
  const devices=await Homey.devices.getDevices();
  const charger=devices?.[CHARGER_ID];
  if(!charger)throw new Error('CHARGER_MISSING');

  const chargeState=String(cap(charger,'evcharger_charging_state')||'unknown').toLowerCase();
  const charging=cap(charger,'evcharger_charging')===true;
  const sessionEnabled=cap(charger,'onoff')===true;
  const chargerTargetA=num(cap(charger,'target_charger_current'));
  const circuitTargetA=num(cap(charger,'target_circuit_current'));
  const offeredA=num(cap(charger,'measure_current.offered'));
  const powerW=num(cap(charger,'measure_power'));
  const p1A=num(cap(charger,'measure_current.p1'));
  const p2A=num(cap(charger,'measure_current.p2'));
  const p3A=num(cap(charger,'measure_current.p3'));
  const phaseRaw=await readPhaseSetting(charger);
  const homeyMode=normalizePhaseMode(phaseRaw);
  const activeElectricalPhases=[p1A,p2A,p3A].filter(x=>x!==null&&Math.abs(x)>=2).length;
  const electricalMode=
    charging===true && powerW!==null && powerW>500 && offeredA!==null && offeredA>=5.5
      ?(activeElectricalPhases>=2?'3P':activeElectricalPhases===1?'1P':'UNKNOWN')
      :'UNKNOWN';
  const confirmedMode=electricalMode!=='UNKNOWN'?electricalMode:homeyMode;
  const phaseConfirmationSource=
    electricalMode!=='UNKNOWN'?'ELECTRICAL_TELEMETRY':
    homeyMode!=='UNKNOWN'?'HOMEY_SETTINGS':'NONE';
  const paused=
    charging!==true &&
    chargeState==='plugged_in_paused' &&
    offeredA!==null && offeredA<=1 &&
    powerW!==null && powerW<=250;

  return {
    chargeState,charging,sessionEnabled,paused,
    chargerTargetA,circuitTargetA,offeredA,powerW,p1A,p2A,p3A,
    phaseRaw,homeyMode,electricalMode,confirmedMode,phaseConfirmationSource
  };
};

const transitionObject=(stage,control,originalCircuitA,extra={})=>({
  schema:TRANSITION_SCHEMA,
  stage,
  transitionId:extra.transitionId||null,
  requestedMode:control?.mode||'OFF',
  requestedA:control?.requestedA??0,
  originalCircuitA:Number.isInteger(originalCircuitA)?originalCircuitA:null,
  startedAt:extra.startedAt||null,
  stageSince:iso(),
  failure:extra.failure||null,
  phaseConfirmedMode:extra.phaseConfirmedMode||null,
  phaseConfirmedAt:extra.phaseConfirmedAt||null,
  phaseConfirmationSource:extra.phaseConfirmationSource||null,
  bounded:true
});

const saveStatus=async(status,reason,stage,control,hw,originalCircuitA,extra={})=>{
  const transition=transitionObject(stage,control,originalCircuitA,extra);
  const value=JSON.stringify({
    schema:VERSION,
    status,
    at:iso(),
    reason,
    live:extra.live===true,
    phaseExecutionEnabled:PHASE_EXECUTION_ENABLED,
    physicalWritePerformed:extra.physicalWritePerformed===true,
    controlRevision:control?.controlRevision||'',
    targetW:control?.targetW??0,
    targetA:control?.requestedA??0,
    phaseMode:control?.mode||'OFF',
    candidateAction:extra.action||'NOOP',
    confirmedMode:hw?.confirmedMode||'UNKNOWN',
    transition,
    boundedTransition:true,
    opportunityOnly:true,
    teslaConsumptionRequired:false,
    observed:hw||null,
    ...extra.statusExtra
  });
  await Homey.logic.updateVariable({id:IDS.status,variable:{value}});
};

const waitHardware=async(predicate,timeoutMs,errorCode)=>{
  const deadline=Date.now()+timeoutMs;
  let hw=null;
  while(Date.now()<=deadline){
    hw=await readHardware();
    if(predicate(hw))return hw;
    await sleep(POLL_MS);
  }
  const err=new Error(errorCode);
  err.lastHardware=hw;
  throw err;
};

const restoreCircuit=async(originalCircuitA)=>{
  if(!Number.isInteger(originalCircuitA)||originalCircuitA<EV_MIN_A||originalCircuitA>64){
    throw new Error('ORIGINAL_CIRCUIT_LIMIT_INVALID');
  }
  let hw=await readHardware();
  if(hw.circuitTargetA!==originalCircuitA){
    await setCircuitA(originalCircuitA);
    hw=await waitHardware(
      x=>x.circuitTargetA===originalCircuitA,
      CIRCUIT_CONFIRM_TIMEOUT_MS,
      'CIRCUIT_RESTORE_TIMEOUT'
    );
  }
  return hw;
};

const pauseAndConfirm=async()=>{
  let hw=await readHardware();
  if(hw.paused)return hw;
  await pauseSession();
  return waitHardware(x=>x.paused,PAUSE_TIMEOUT_MS,'PAUSE_CONFIRM_TIMEOUT');
};

const confirmLockedPhase=async(mode,vars)=>{
  const deadline=Date.now()+PHASE_CONFIRM_TIMEOUT_MS;
  let nextCloudAt=Date.now()+PHASE_CLOUD_CONFIRM_INTERVAL_MS;
  let lastHw=null;
  while(Date.now()<=deadline){
    lastHw=await readHardware();
    if(lastHw.confirmedMode===mode){
      return {
        hw:lastHw,
        source:lastHw.phaseConfirmationSource,
        raw:lastHw.phaseRaw
      };
    }
    if(Date.now()>=nextCloudAt){
      try{
        const raw=await readCloudPhaseMode(vars);
        const cloudMode=normalizePhaseMode(raw);
        if(cloudMode===mode){
          return {hw:lastHw,source:'EASEE_CLOUD_OBSERVATION_38',raw};
        }
      }catch(_){}
      nextCloudAt=Date.now()+PHASE_CLOUD_CONFIRM_INTERVAL_MS;
    }
    await sleep(POLL_MS);
  }
  const err=new Error('PHASE_CONFIRM_TIMEOUT');
  err.lastHardware=lastHw;
  throw err;
};

const safeAbort=async(reason,control,originalCircuitA,live,startedAt)=>{
  let hw=null;
  let restoreError=null;
  try{
    hw=await pauseAndConfirm();
  }catch(err){
    restoreError=String(err?.message||err);
  }
  if(Number.isInteger(originalCircuitA)){
    try{
      hw=await restoreCircuit(originalCircuitA);
    }catch(err){
      restoreError=(restoreError?restoreError+';':'')+String(err?.message||err);
    }
  }
  if(!hw){
    try{hw=await readHardware();}catch(_){}
  }
  const finalReason=restoreError?reason+':RECOVERY='+restoreError:reason;
  await saveStatus(
    'FAILED',
    finalReason,
    'FAILED',
    control,
    hw,
    originalCircuitA,
    {
      live,
      physicalWritePerformed:true,
      action:'PAUSE_AND_RESTORE',
      startedAt,
      failure:finalReason
    }
  );
  return true;
};

const liveVar=await Homey.logic.getVariable({id:IDS.live});
const statusVar=await Homey.logic.getVariable({id:IDS.status});
const previous=parse(statusVar?.value);
const liveEnabled=liveVar?.value===true;

if(previous?.schema===VERSION&&previous?.status==='RUNNING'&&age(previous?.at)<RUN_LOCK_MS){
  return true;
}

let control=await readControl();
let hw=await readHardware();

if(!control.ok){
  return await safeAbort(control.error,control,null,liveEnabled,null);
}

if(!liveEnabled||!PHASE_EXECUTION_ENABLED){
  await saveStatus(
    'ARMED_DISABLED',
    liveEnabled?'PHASE_EXECUTION_DISABLED':'LIVE_FLAG_DISABLED',
    'STABLE',
    control,
    hw,
    null,
    {live:liveEnabled,physicalWritePerformed:false,action:'NOOP'}
  );
  return true;
}

// If a previous v0.4.4 invocation died after applying a temporary cap, recover
// its captured baseline before evaluating a new command.
const previousOriginal=num(previous?.transition?.originalCircuitA);
const previousNeedsRecovery=
  previous?.schema===VERSION &&
  ['RUNNING','FAILED','RECOVERY'].includes(String(previous?.status||'')) &&
  Number.isInteger(previousOriginal) &&
  previousOriginal>=EV_MIN_A &&
  previousOriginal<=64;

if(previousNeedsRecovery&&hw.circuitTargetA!==previousOriginal){
  try{
    hw=await pauseAndConfirm();
    hw=await restoreCircuit(previousOriginal);
  }catch(err){
    return await safeAbort(
      'STARTUP_CIRCUIT_RECOVERY_FAILED:'+String(err?.message||err),
      control,
      previousOriginal,
      liveEnabled,
      previous?.transition?.startedAt||null
    );
  }
  control=await readControl();
  if(!control.ok){
    return await safeAbort(control.error,control,previousOriginal,liveEnabled,null);
  }
  hw=await readHardware();
}

if(control.mode==='OFF'){
  try{
    hw=await pauseAndConfirm();
    await saveStatus(
      'STABLE','OFF_PAUSED','STABLE',control,hw,null,
      {live:true,physicalWritePerformed:!hw.paused,action:'PAUSE_SESSION'}
    );
    return true;
  }catch(err){
    return await safeAbort(
      'OFF_PAUSE_FAILED:'+String(err?.message||err),
      control,
      null,
      liveEnabled,
      null
    );
  }
}

// If Easee already exposes the requested same-phase opportunity, Tesla draw is
// irrelevant: 0 W is a valid healthy state (for example when the car is full).
if(
  hw.confirmedMode===control.mode &&
  hw.sessionEnabled===true &&
  hw.chargerTargetA===control.requestedA &&
  hw.circuitTargetA!==null &&
  hw.circuitTargetA>=control.requestedA
){
  await saveStatus(
    'STABLE',
    hw.charging===true?'STABLE':'OPPORTUNITY_ARMED',
    'STABLE',
    control,
    hw,
    null,
    {live:true,physicalWritePerformed:false,action:'NOOP'}
  );
  return true;
}

// Same-phase current adjustment while the opportunity is already enabled.
if(hw.confirmedMode===control.mode&&hw.sessionEnabled===true){
  if(hw.circuitTargetA===null||hw.circuitTargetA<control.requestedA){
    return await safeAbort('CIRCUIT_LIMIT_BELOW_REQUEST',control,null,liveEnabled,null);
  }
  await setCurrentA(control.requestedA);
  try{
    hw=await waitHardware(
      x=>x.chargerTargetA===control.requestedA,
      CURRENT_CONFIRM_TIMEOUT_MS,
      'CURRENT_TARGET_CONFIRM_TIMEOUT'
    );
  }catch(err){
    return await safeAbort(
      'STABLE_CURRENT_ADJUST_FAILED:'+String(err?.message||err),
      control,
      null,
      liveEnabled,
      null
    );
  }
  await saveStatus(
    'STABLE',
    hw.charging===true?'STABLE_CURRENT_ADJUST':'OPPORTUNITY_CURRENT_ADJUST',
    'STABLE',
    control,
    hw,
    null,
    {live:true,physicalWritePerformed:true,action:'SET_CURRENT'}
  );
  return true;
}

const originalCircuitA=hw.circuitTargetA;
if(!Number.isInteger(originalCircuitA)||originalCircuitA<EV_MIN_A||originalCircuitA>64){
  return await safeAbort('CIRCUIT_TARGET_UNKNOWN',control,null,liveEnabled,null);
}
if(originalCircuitA<control.requestedA){
  return await safeAbort('CIRCUIT_LIMIT_BELOW_REQUEST',control,originalCircuitA,liveEnabled,null);
}

const startedAt=iso();
const transitionId=Date.now()+':'+control.mode+':'+control.requestedA;

await saveStatus(
  'RUNNING',
  'BOUNDED_TRANSITION_START',
  'PAUSING',
  control,
  hw,
  originalCircuitA,
  {
    live:true,
    physicalWritePerformed:false,
    action:'PAUSE_SESSION',
    transitionId,
    startedAt
  }
);

try{
  // Capture the electrically proven mode before pausing; once paused, electrical
  // telemetry is zero and Homey settings may lag behind the physical state.
  let phaseLatch=hw.confirmedMode;
  hw=await pauseAndConfirm();
  await saveStatus(
    'RUNNING','PAUSE_CONFIRMED','PAUSED',
    control,hw,originalCircuitA,
    {live:true,physicalWritePerformed:true,action:'PAUSE_SESSION',transitionId,startedAt}
  );

  const vars=await readEaseeVars();

  for(let replan=0;replan<=MAX_REPLANS_WHILE_PAUSED;replan++){
    control=await readControl();
    if(!control.ok)throw new Error(control.error);

    if(control.mode==='OFF'){
      hw=await restoreCircuit(originalCircuitA);
      await saveStatus(
        'STABLE','OFF_DURING_BOUNDED_TRANSITION','STABLE',
        control,hw,null,
        {
          live:true,physicalWritePerformed:true,action:'RESTORE_CIRCUIT_CAP',
          transitionId,startedAt,statusExtra:{replansWhilePaused:replan}
        }
      );
      return true;
    }

    if(control.requestedA>originalCircuitA){
      throw new Error('CIRCUIT_LIMIT_BELOW_REQUEST');
    }

    if(phaseLatch!==control.mode){
      await saveStatus(
        'RUNNING','PHASE_COMMAND','PHASE_COMMAND',
        control,hw,originalCircuitA,
        {
          live:true,physicalWritePerformed:false,action:'SET_PHASE_MODE',
          transitionId,startedAt,statusExtra:{replansWhilePaused:replan}
        }
      );
      await setPhaseMode(control.mode,vars);
      const confirmation=await confirmLockedPhase(control.mode,vars);
      hw=confirmation.hw;
      phaseLatch=control.mode;

      await saveStatus(
        'RUNNING','PHASE_CONFIRMED','DEADTIME',
        control,hw,originalCircuitA,
        {
          live:true,physicalWritePerformed:true,action:'WAIT_DEADTIME',
          transitionId,startedAt,
          phaseConfirmedMode:control.mode,
          phaseConfirmedAt:iso(),
          phaseConfirmationSource:confirmation.source,
          statusExtra:{phaseConfirmationRaw:confirmation.raw,replansWhilePaused:replan}
        }
      );
      await sleep(DEADTIME_MS);
    }

    const afterDeadtime=await readControl();
    if(!afterDeadtime.ok)throw new Error(afterDeadtime.error);
    if(afterDeadtime.mode!==control.mode){
      control=afterDeadtime;
      if(replan===MAX_REPLANS_WHILE_PAUSED){
        throw new Error('MODE_UNSTABLE_DURING_TRANSITION');
      }
      continue;
    }
    control=afterDeadtime;

    await setCircuitA(control.requestedA);
    hw=await waitHardware(
      x=>x.paused&&x.circuitTargetA===control.requestedA,
      CIRCUIT_CONFIRM_TIMEOUT_MS,
      'TRANSITION_CIRCUIT_CAP_CONFIRM_TIMEOUT'
    );

    await saveStatus(
      'RUNNING','TRANSITION_CIRCUIT_CAP_CONFIRMED','ARMING_CIRCUIT_CAP',
      control,hw,originalCircuitA,
      {
        live:true,physicalWritePerformed:true,action:'SET_TRANSITION_CIRCUIT_CAP',
        transitionId,startedAt,statusExtra:{replansWhilePaused:replan}
      }
    );

    const beforeResume=await readControl();
    if(!beforeResume.ok)throw new Error(beforeResume.error);
    if(beforeResume.mode!==control.mode){
      hw=await restoreCircuit(originalCircuitA);
      control=beforeResume;
      phaseLatch=hw.confirmedMode==='UNKNOWN'?phaseLatch:hw.confirmedMode;
      if(replan===MAX_REPLANS_WHILE_PAUSED){
        throw new Error('MODE_UNSTABLE_DURING_TRANSITION');
      }
      continue;
    }
    if(beforeResume.requestedA!==control.requestedA){
      control=beforeResume;
      if(control.requestedA>originalCircuitA)throw new Error('CIRCUIT_LIMIT_BELOW_REQUEST');
      await setCircuitA(control.requestedA);
      hw=await waitHardware(
        x=>x.paused&&x.circuitTargetA===control.requestedA,
        CIRCUIT_CONFIRM_TIMEOUT_MS,
        'UPDATED_TRANSITION_CAP_CONFIRM_TIMEOUT'
      );
    }else{
      control=beforeResume;
    }

    await resumeSession();
    await saveStatus(
      'RUNNING','OPPORTUNITY_RESUME_SENT','RESUMING',
      control,hw,originalCircuitA,
      {
        live:true,physicalWritePerformed:true,action:'RESUME_SESSION',
        transitionId,startedAt,statusExtra:{replansWhilePaused:replan}
      }
    );

    // Easee resume can reset dynamic charger current. Give Easee one short
    // device-settle tick, then re-apply and confirm the bounded opportunity.
    // This wait is for Easee command ordering, never for Tesla consumption.
    await sleep(POLL_MS);
    await setCurrentA(control.requestedA);
    hw=await waitHardware(
      x=>x.chargerTargetA===control.requestedA,
      CURRENT_CONFIRM_TIMEOUT_MS,
      'CURRENT_TARGET_CONFIRM_TIMEOUT'
    );

    await saveStatus(
      'RUNNING','OPPORTUNITY_CURRENT_CONFIRMED','RESTORING_CIRCUIT_CAP',
      control,hw,originalCircuitA,
      {
        live:true,physicalWritePerformed:true,action:'RESTORE_CIRCUIT_CAP',
        transitionId,startedAt,
        phaseConfirmedMode:control.mode,
        phaseConfirmedAt:iso(),
        phaseConfirmationSource:hw.phaseConfirmationSource,
        statusExtra:{
          replansWhilePaused:replan,
          teslaConsumptionObserved:hw.powerW!==null&&hw.powerW>0
        }
      }
    );

    hw=await restoreCircuit(originalCircuitA);

    const latest=await readControl();
    if(latest.ok&&latest.mode===control.mode&&latest.requestedA!==control.requestedA){
      if(latest.requestedA<=originalCircuitA){
        await setCurrentA(latest.requestedA);
        control=latest;
        hw=await waitHardware(
          x=>x.chargerTargetA===control.requestedA,
          CURRENT_CONFIRM_TIMEOUT_MS,
          'FINAL_CURRENT_CONFIRM_TIMEOUT'
        );
      }
    }

    await saveStatus(
      'STABLE','BOUNDED_TRANSITION_COMPLETE','STABLE',
      control,hw,null,
      {
        live:true,physicalWritePerformed:true,action:'NOOP',
        transitionId,startedAt,
        phaseConfirmedMode:control.mode,
        phaseConfirmedAt:iso(),
        phaseConfirmationSource:hw.phaseConfirmationSource,
        statusExtra:{
          durationMs:Date.now()-Date.parse(startedAt),
          replansWhilePaused:replan,
          selfRetriggerUsed:false,
          teslaConsumptionObserved:hw.powerW!==null&&hw.powerW>0
        }
      }
    );
    return true;
  }

  throw new Error('MODE_UNSTABLE_DURING_TRANSITION');
}catch(err){
  return await safeAbort(
    String(err?.message||err||'BOUNDED_TRANSITION_FAILED'),
    control,
    originalCircuitA,
    liveEnabled,
    startedAt
  );
}
