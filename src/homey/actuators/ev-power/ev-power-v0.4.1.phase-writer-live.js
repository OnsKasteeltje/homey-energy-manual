// EV Actuator v0.4.1 PHASE-WRITER LIVE
// Stateful physical writer candidate. The physical execution flag stays false
// until live cutover is explicitly promoted after regression + dry-run.
//
// One transition step per HomeyScript invocation:
// PAUSE -> SET_PHASE_MODE -> CONFIRM -> DEADTIME -> CIRCUIT CAP -> RESUME
// -> SET CURRENT -> RESTORE CIRCUIT CAP -> STABLE.
//
// Native Homey Easee action cards own pause/resume/current/circuit writes.
// Only set_phase_mode uses Easee Cloud because the Homey Easee app does not
// expose that action card.

const VERSION='EM2_EV_ACTUATOR_V0.4.1_PHASE_WRITER';
const TRANSITION_SCHEMA='EM2_EV_PHASE_TRANSITION_STATE_V0.4';
const PHASE_EXECUTION_ENABLED=true;

const FLOW_ID='fea23193-a03f-49dd-9780-7e72ee48747d';
const CHARGER_ID='4d0b6913-d940-474e-95d6-b43f194c4119';
const CHARGER_SERIAL='ECHM6B9F';
const FRESH_MS=120000;
const DEADTIME_MS=5000;
const PHASE_CONFIRM_TIMEOUT_MS=30000;
const TRANSITION_WARN_MS=90000;

const IDS={
  live:'8d47e98d-e4bc-4f47-8c02-c2aca7f7a978',
  status:'ea1f8a44-2f6c-490e-9b86-bae761886cf9',
  intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',
  adapter:'f2118322-d59d-4aa8-b478-234effc3983c',
  gate:'4c66836b-77ae-43b5-b8e0-b32af15b57bc',
  access:'9bc21974-4863-4471-b9ac-a55b252fdfbd',
  refresh:'2855a2ee-caa1-43b3-a9ef-ce91acd2ad42',
  expires:'832f3227-f2f6-4c95-9032-39c6160e966d'
};

const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};
const age=x=>{const t=Date.parse(String(x||''));return Number.isFinite(t)?Date.now()-t:Infinity;};
const iso=()=>new Date().toISOString();
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

const ACTION_IDS={
  pause:`homey:device:${CHARGER_ID}:pauseCharging`,
  resume:`homey:device:${CHARGER_ID}:resumeCharging`,
  circuit:`homey:device:${CHARGER_ID}:circuitCurrentControl`,
  current:`homey:device:${CHARGER_ID}:setDynamicChargerCurrent`
};
const runNative=async(id,args={})=>{
  return await Homey.flow.runFlowCardAction({id,args});
};

const pauseSession=()=>runNative(ACTION_IDS.pause,{});
const resumeSession=()=>runNative(ACTION_IDS.resume,{});
const setCircuitA=a=>runNative(ACTION_IDS.circuit,{current:a});
const setCurrentA=a=>runNative(ACTION_IDS.current,{current:a});

const postJson=async(url,body,accessToken)=>{
  const r=await fetch(url,{
    method:'POST',
    headers:{
      'Authorization':`Bearer ${accessToken}`,
      'Accept':'application/json',
      'Content-Type':'application/json'
    },
    body:JSON.stringify(body)
  });
  let payload=null;try{payload=await r.json();}catch(_){}
  if(!r.ok)throw new Error(`EASEE_HTTP_${r.status}`);
  return payload||{};
};

const getAccessToken=async vars=>{
  let access=String(vars.access?.value||'').trim();
  let refresh=String(vars.refresh?.value||'').trim();
  const expiresAt=Date.parse(String(vars.expires?.value||''));
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
      Homey.logic.updateVariable({id:IDS.access,variable:{value:nextAccess}}),
      Homey.logic.updateVariable({id:IDS.refresh,variable:{value:nextRefresh}}),
      Homey.logic.updateVariable({id:IDS.expires,variable:{value:nextExpiry}})
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
    `https://api.easee.com/api/chargers/${encodeURIComponent(CHARGER_SERIAL)}/commands/set_phase_mode`,
    {phaseMode:pv},
    access
  );
};

const scheduleNext=async(ms=1200)=>{
  await new Promise(resolve=>setTimeout(resolve,ms));
  await Homey.flow.triggerAdvancedFlow({id:FLOW_ID});
};

const [liveVar,statusVar,intentVar,adapterVar,gateVar,accessVar,refreshVar,expiresVar]=await Promise.all([
  Homey.logic.getVariable({id:IDS.live}),
  Homey.logic.getVariable({id:IDS.status}),
  Homey.logic.getVariable({id:IDS.intent}),
  Homey.logic.getVariable({id:IDS.adapter}),
  Homey.logic.getVariable({id:IDS.gate}),
  Homey.logic.getVariable({id:IDS.access}),
  Homey.logic.getVariable({id:IDS.refresh}),
  Homey.logic.getVariable({id:IDS.expires})
]);
const vars={access:accessVar,refresh:refreshVar,expires:expiresVar};

const intent=parse(intentVar?.value);
const adapter=parse(adapterVar?.value);
const gate=parse(gateVar?.value);
const previous=parse(statusVar?.value);
const cmd=adapter?.command||{};
const ev=intent?.targets?.ev||{};

const controlRevision=String(intent?.controlRevision||'');
const desiredMode=String(cmd?.mode||'OFF');
const desiredA=num(cmd?.requested_A);
const desiredW=num(cmd?.requested_W);
const targetW=num(ev?.target_W);

const contractAligned=
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
  ['OFF','1P','3P'].includes(desiredMode) &&
  Number.isInteger(desiredA) &&
  Number.isInteger(desiredW) &&
  desiredW===targetW &&
  ((desiredMode==='OFF'&&desiredA===0&&desiredW===0) ||
   (desiredMode==='1P'&&desiredA>=6&&desiredA<=16&&desiredW===desiredA*230) ||
   (desiredMode==='3P'&&desiredA>=6&&desiredA<=16&&desiredW===desiredA*690));

const fresh=
  age(intent?.generatedAt)<=FRESH_MS &&
  age(adapter?.generatedAt)<=FRESH_MS &&
  age(gate?.updatedAt)<=FRESH_MS;

const deadlineTarget=
  String(ev?.status||'')==='NUMERIC_DEADLINE_TARGET' ||
  String(ev?.source||'')==='REMAINING_KWH_OVER_TIME_TO_DEADLINE';
const deadlinePhaseOK=!deadlineTarget||desiredMode==='3P';

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

const nowMs=Date.now();
// Transition state is only reusable within the exact same LIVE writer
// version. Never inherit ARMED-DISABLED or older-version transition state at
// cutover, otherwise stale requestedMode/stage can look like a live mode change.
const priorT=
  previous?.schema===VERSION &&
  previous?.phaseExecutionEnabled===true &&
  previous?.transition?.schema===TRANSITION_SCHEMA
    ?previous.transition
    :null;
let t=priorT||{
  schema:TRANSITION_SCHEMA,
  stage:'STABLE',
  transitionId:null,
  requestedMode:'OFF',
  requestedA:0,
  originalCircuitA:null,
  startedAt:null,
  stageSince:iso(),
  failure:null
};

const transitionAge=t.startedAt?nowMs-Date.parse(t.startedAt):0;
const stageAge=t.stageSince?nowMs-Date.parse(t.stageSince):0;
const liveEnabled=liveVar?.value===true;
const canWrite=PHASE_EXECUTION_ENABLED&&liveEnabled;

// A previous fail-closed transition must not deadlock the actuator forever.
// Recovery is allowed only from the safest observable boundary: session
// already paused, zero offered/load, known restored circuit limit and valid
// control contract. From there restart as STABLE and re-evaluate the current
// authoritative request.
const safePausedRecovery=
  t.stage==='FAILED' &&
  paused &&
  circuitTargetA!==null &&
  circuitTargetA>=6 &&
  circuitTargetA<=64 &&
  contractAligned &&
  fresh &&
  requestValid &&
  deadlinePhaseOK;

if(safePausedRecovery){
  t={
    schema:TRANSITION_SCHEMA,
    stage:'STABLE',
    transitionId:null,
    requestedMode:confirmedMode==='1P'||confirmedMode==='3P'?confirmedMode:'OFF',
    requestedA:0,
    originalCircuitA:null,
    startedAt:null,
    stageSince:iso(),
    failure:null
  };
}

const save=async(status,reason,action='NOOP',write=false,extra={})=>{
  const value=JSON.stringify({
    schema:VERSION,
    status,
    at:iso(),
    reason,
    live:liveEnabled,
    phaseExecutionEnabled:PHASE_EXECUTION_ENABLED,
    physicalWritePerformed:write,
    controlRevision,
    targetW,
    targetA:desiredA,
    phaseMode:desiredMode,
    candidateAction:action,
    confirmedMode,
    transition:t,
    transitionAgeMs:transitionAge,
    transitionSlow:t.startedAt&&transitionAge>TRANSITION_WARN_MS,
    observed:{
      chargeState,charging,paused,chargerTargetA,circuitTargetA,
      offeredA,powerW,confirmedPhaseRaw:phaseRaw
    },
    ...extra
  });
  await Homey.logic.updateVariable({id:IDS.status,variable:{value}});
};

const failClosed=async reason=>{
  t={...t,stage:'FAILED',failure:reason,stageSince:iso()};
  let wrote=false;
  if(canWrite && !paused){
    await pauseSession();
    wrote=true;
  }
  await save('FAILED',reason,'PAUSE_SESSION',wrote);
  return true;
};

if(!contractAligned)return await failClosed('CONTROL_CONTRACT_NOT_ALIGNED');
if(!fresh)return await failClosed('CONTROL_NOT_FRESH');
if(!requestValid)return await failClosed('INVALID_PHASE_REQUEST');
if(!deadlinePhaseOK)return await failClosed('DEADLINE_MUST_USE_3P');

if(!canWrite){
  await save(
    'ARMED_DISABLED',
    PHASE_EXECUTION_ENABLED?'LIVE_FLAG_DISABLED':'PHASE_EXECUTION_DISABLED',
    previous?.candidateAction||'NOOP',
    false
  );
  return true;
}

// During a transition, phase-mode changes fail closed. Current changes on
// the same phase are handled conservatively: decreases take effect immediately
// inside the transition; increases wait until the circuit cap has been restored
// and STABLE current control can apply them safely.
let transitionA=desiredA;
if(t.stage!=='STABLE'){
  if(t.requestedMode!==desiredMode){
    return await failClosed('PHASE_MODE_CHANGED_DURING_TRANSITION');
  }
  if(Number.isInteger(t.requestedA)&&t.requestedA>=6&&t.requestedA<=16){
    if(desiredA<t.requestedA){
      t={...t,requestedA:desiredA};
      transitionA=desiredA;
    }else{
      transitionA=t.requestedA;
    }
  }
}

if(desiredMode==='OFF'){
  if(paused){
    t={...t,stage:'STABLE',transitionId:null,requestedMode:'OFF',requestedA:0,originalCircuitA:null,startedAt:null,stageSince:iso(),failure:null};
    await save('STABLE','OFF_PAUSED','NOOP',false);
    return true;
  }
  await pauseSession();
  t={...t,stage:'PAUSING',requestedMode:'OFF',requestedA:0,startedAt:t.startedAt||iso(),stageSince:iso()};
  await save('TRANSITION','OFF_REQUIRES_PAUSE','PAUSE_SESSION',true);
  await scheduleNext();
  return true;
}

if(t.stage==='STABLE'){
  if(confirmedMode===desiredMode&&!paused){
    if(chargerTargetA!==desiredA){
      await setCurrentA(desiredA);
      t={...t,requestedMode:desiredMode,requestedA:desiredA,stageSince:iso(),failure:null};
      await save('STABLE','STABLE_CURRENT_ADJUST','SET_CURRENT',true);
    }else{
      t={...t,requestedMode:desiredMode,requestedA:desiredA,stageSince:iso(),failure:null};
      await save('STABLE','STABLE','NOOP',false);
    }
    return true;
  }

  if(circuitTargetA===null)return await failClosed('CIRCUIT_TARGET_UNKNOWN');
  if(circuitTargetA<desiredA)return await failClosed('CIRCUIT_LIMIT_BELOW_REQUEST');

  const transitionId=`${nowMs}:${desiredMode}:${desiredA}`;
  if(confirmedMode===desiredMode&&paused){
    t={...t,stage:'ARMING_CIRCUIT_CAP',transitionId,requestedMode:desiredMode,requestedA:desiredA,originalCircuitA:circuitTargetA,startedAt:iso(),stageSince:iso(),failure:null};
    await setCircuitA(desiredA);
    await save('TRANSITION','PAUSED_RESUME_REQUIRES_SAFETY_CAP','SET_TRANSITION_CIRCUIT_CAP',true);
    await scheduleNext();
    return true;
  }

  t={...t,stage:'PAUSING',transitionId,requestedMode:desiredMode,requestedA:desiredA,originalCircuitA:circuitTargetA,startedAt:iso(),stageSince:iso(),failure:null};
  await pauseSession();
  await save('TRANSITION','PHASE_CHANGE_REQUIRES_PAUSE','PAUSE_SESSION',true);
  await scheduleNext();
  return true;
}

if(t.stage==='PAUSING'){
  if(!paused){
    await pauseSession();
    await save('TRANSITION','WAIT_PAUSE_CONFIRMATION','PAUSE_SESSION',true);
    await scheduleNext();
    return true;
  }
  if(confirmedMode===desiredMode){
    t={...t,stage:'DEADTIME',stageSince:iso()};
    await save('TRANSITION','PHASE_ALREADY_CONFIRMED','WAIT_DEADTIME',false);
    await scheduleNext();
    return true;
  }
  await setPhaseMode(desiredMode,vars);
  t={...t,stage:'CONFIRMING_PHASE',stageSince:iso()};
  await save('TRANSITION','PHASE_COMMAND_SENT','SET_PHASE_MODE',true);
  await scheduleNext();
  return true;
}

if(t.stage==='CONFIRMING_PHASE'){
  if(!paused)return await failClosed('PAUSE_CONFIRMATION_LOST');
  if(confirmedMode===desiredMode){
    t={...t,stage:'DEADTIME',stageSince:iso()};
    await save('TRANSITION','PHASE_CONFIRMED','WAIT_DEADTIME',false);
    await scheduleNext();
    return true;
  }
  if(stageAge>PHASE_CONFIRM_TIMEOUT_MS){
    await setPhaseMode(desiredMode,vars);
    t={...t,stageSince:iso()};
    await save('TRANSITION','PHASE_CONFIRM_RETRY','SET_PHASE_MODE',true);
    await scheduleNext();
    return true;
  }
  await save('TRANSITION','PHASE_NOT_CONFIRMED','WAIT_PHASE_CONFIRM',false);
  await scheduleNext();
  return true;
}

if(t.stage==='DEADTIME'){
  if(!paused){
    await pauseSession();
    t={...t,stage:'PAUSING',stageSince:iso()};
    await save('TRANSITION','WAIT_PAUSE_CONFIRMATION','PAUSE_SESSION',true);
    await scheduleNext();
    return true;
  }
  if(confirmedMode!==desiredMode){
    await setPhaseMode(desiredMode,vars);
    t={...t,stage:'CONFIRMING_PHASE',stageSince:iso()};
    await save('TRANSITION','PHASE_CONFIRM_RETRY','SET_PHASE_MODE',true);
    await scheduleNext();
    return true;
  }
  if(stageAge<DEADTIME_MS){
    await save('TRANSITION','DEADTIME','WAIT_DEADTIME',false,{remainingMs:Math.max(0,DEADTIME_MS-stageAge)});
    await scheduleNext(Math.min(1500,Math.max(500,DEADTIME_MS-stageAge)));
    return true;
  }
  await setCircuitA(transitionA);
  t={...t,stage:'ARMING_CIRCUIT_CAP',stageSince:iso()};
  await save('TRANSITION','PROTECT_RESUME_CURRENT_RESET','SET_TRANSITION_CIRCUIT_CAP',true);
  await scheduleNext();
  return true;
}

if(t.stage==='ARMING_CIRCUIT_CAP'){
  if(!paused){
    await pauseSession();
    await save('TRANSITION','WAIT_PAUSE_CONFIRMATION','PAUSE_SESSION',true);
    await scheduleNext();
    return true;
  }
  if(confirmedMode!==desiredMode){
    await setPhaseMode(desiredMode,vars);
    t={...t,stage:'CONFIRMING_PHASE',stageSince:iso()};
    await save('TRANSITION','PHASE_CONFIRM_RETRY','SET_PHASE_MODE',true);
    await scheduleNext();
    return true;
  }
  if(circuitTargetA!==transitionA){
    await setCircuitA(transitionA);
    await save('TRANSITION','WAIT_CIRCUIT_CAP_CONFIRMATION','SET_TRANSITION_CIRCUIT_CAP',true);
    await scheduleNext();
    return true;
  }
  await resumeSession();
  t={...t,stage:'RESUMING',stageSince:iso()};
  await save('TRANSITION','TRANSITION_CIRCUIT_CAP_CONFIRMED','RESUME_SESSION',true);
  await scheduleNext();
  return true;
}

if(t.stage==='RESUMING'){
  if(confirmedMode!==desiredMode)return await failClosed('PHASE_CONFIRMATION_LOST');
  if(!(chargeState==='plugged_in'||chargeState==='plugged_in_charging'||charging)){
    await resumeSession();
    await save('TRANSITION','WAIT_SESSION_RESUME','RESUME_SESSION',true);
    await scheduleNext();
    return true;
  }
  await setCurrentA(transitionA);
  t={...t,stage:'APPLY_CURRENT',stageSince:iso()};
  await save('TRANSITION','RESUME_RESETS_CHARGER_CURRENT','SET_CURRENT',true);
  await scheduleNext();
  return true;
}

if(t.stage==='APPLY_CURRENT'){
  if(confirmedMode!==desiredMode)return await failClosed('PHASE_CONFIRMATION_LOST');
  if(chargerTargetA!==transitionA){
    await setCurrentA(transitionA);
    await save('TRANSITION','WAIT_CURRENT_TARGET','SET_CURRENT',true);
    await scheduleNext();
    return true;
  }
  if(!(charging||chargeState==='plugged_in_charging')){
    await save('TRANSITION','CURRENT_SET_WAIT_CHARGING','WAIT_CHARGING',false);
    await scheduleNext();
    return true;
  }
  const restoreA=Number(t.originalCircuitA);
  if(!Number.isInteger(restoreA)||restoreA<transitionA||restoreA>64)return await failClosed('ORIGINAL_CIRCUIT_LIMIT_INVALID');
  await setCircuitA(restoreA);
  t={...t,stage:'RESTORING_CIRCUIT_CAP',stageSince:iso()};
  await save('TRANSITION','DESIRED_CURRENT_AND_CHARGING_CONFIRMED','RESTORE_CIRCUIT_CAP',true);
  await scheduleNext();
  return true;
}

if(t.stage==='RESTORING_CIRCUIT_CAP'){
  const restoreA=Number(t.originalCircuitA);
  if(!Number.isInteger(restoreA)||restoreA<transitionA||restoreA>64)return await failClosed('ORIGINAL_CIRCUIT_LIMIT_INVALID');
  if(circuitTargetA!==restoreA){
    await setCircuitA(restoreA);
    await save('TRANSITION','WAIT_CIRCUIT_RESTORE_CONFIRMATION','RESTORE_CIRCUIT_CAP',true);
    await scheduleNext();
    return true;
  }
  t={...t,stage:'STABLE',transitionId:null,requestedMode:desiredMode,requestedA:transitionA,originalCircuitA:null,startedAt:null,stageSince:iso(),failure:null};
  await save('STABLE','TRANSITION_COMPLETE','NOOP',false,{transitionTargetA:transitionA});
  if(desiredA!==transitionA)await scheduleNext(500);
  return true;
}

return await failClosed('UNKNOWN_TRANSITION_STAGE');
