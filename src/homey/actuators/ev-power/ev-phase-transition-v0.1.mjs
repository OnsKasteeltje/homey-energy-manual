// Pure EV phase transition state machine v0.1
// No Homey/Easee calls. Returns the next actuator action only.
//
// Functional modes:
//   OFF
//   1P + A
//   3P + A
//
// Easee phase-mode mapping:
//   1P -> 1 (Locked to single phase)
//   3P -> 3 (Locked to three phase)
// Physical phase selection inside 1P remains owned by Easee/Equalizer.

export const TRANSITION_SCHEMA='EM2_EV_PHASE_TRANSITION_STATE_V0.1';
export const ACTION_SCHEMA='EM2_EV_PHASE_TRANSITION_ACTION_V0.1';

export const DEFAULTS=Object.freeze({
  minA:6,
  maxA:16,
  zeroConfirmW:250,
  zeroConfirmA:1,
  deadTimeMs:5000,
  commandConfirmTimeoutMs:30000,
  transitionTimeoutMs:90000,
});

const finite=v=>Number.isFinite(Number(v));
const nowIso=ms=>new Date(ms).toISOString();

export function normalizeEaseePhaseMode(raw){
  const s=String(raw??'').trim().toLowerCase();
  if(raw===1||s==='1'||s.includes('locked to single')||s==='1p')return '1P';
  if(raw===3||s==='3'||s.includes('locked to three')||s==='3p')return '3P';
  if(raw===2||s==='2'||s==='auto')return 'AUTO';
  return 'UNKNOWN';
}

export function easeeCommandForMode(mode){
  if(mode==='1P')return 1;
  if(mode==='3P')return 3;
  return null;
}

export function initialTransitionState(nowMs=Date.now()){
  return {
    schema:TRANSITION_SCHEMA,
    stage:'STABLE',
    transitionId:null,
    requestedMode:'OFF',
    requestedA:0,
    startedAt:null,
    stageSince:nowIso(nowMs),
    phaseCommandSentAt:null,
    phaseConfirmedAt:null,
    failure:null,
  };
}

function validRequest(mode,a,cfg){
  if(mode==='OFF')return a===0;
  return ['1P','3P'].includes(mode)&&Number.isInteger(a)&&a>=cfg.minA&&a<=cfg.maxA;
}

function action(type,extra={}){
  return {schema:ACTION_SCHEMA,type,physicalWriteAllowed:false,...extra};
}

export function decidePhaseTransition(input, previous=initialTransitionState(), nowMs=Date.now(), cfg=DEFAULTS){
  const desiredMode=String(input?.desiredMode||'OFF');
  const desiredA=Number(input?.desiredA??0);
  const gatePass=input?.gatePass===true;
  const controlFresh=input?.controlFresh===true;
  const liveEnabled=input?.liveEnabled===true;
  const chargerTargetA=finite(input?.chargerTargetA)?Number(input.chargerTargetA):null;
  const chargerPowerW=finite(input?.chargerPowerW)?Math.max(0,Number(input.chargerPowerW)):null;
  const offeredA=finite(input?.offeredA)?Math.max(0,Number(input.offeredA)):null;
  const confirmedMode=normalizeEaseePhaseMode(input?.easeePhaseMode);
  const commandResult=input?.phaseCommandResult||null;

  const state={...initialTransitionState(nowMs),...previous};
  const transitionAgeMs=state.startedAt?nowMs-Date.parse(state.startedAt):0;
  const stageAgeMs=state.stageSince?nowMs-Date.parse(state.stageSince):0;

  const fail=(reason)=>({
    state:{...state,stage:'FAILED',failure:reason,stageSince:nowIso(nowMs)},
    action:action('SET_CURRENT_0',{reason,requestedA:0,failClosed:true})
  });

  if(!gatePass||!controlFresh){
    return fail(!gatePass?'GATE_NOT_PASS':'CONTROL_NOT_FRESH');
  }
  if(!validRequest(desiredMode,desiredA,cfg)){
    return fail('INVALID_PHASE_REQUEST');
  }
  if(state.startedAt&&transitionAgeMs>cfg.transitionTimeoutMs){
    return fail('TRANSITION_TIMEOUT');
  }

  // SHADOW state machine: LIVE permission is surfaced but never turns returned
  // actions into physical writes. The sole EV actuator will perform that mapping
  // only after commissioning.
  const base={desiredMode,desiredA,confirmedMode,liveEnabled};

  if(desiredMode==='OFF'){
    const next={...state,stage:'STABLE',requestedMode:'OFF',requestedA:0,transitionId:null,startedAt:null,stageSince:nowIso(nowMs),phaseCommandSentAt:null,phaseConfirmedAt:null,failure:null};
    return {state:next,action:action(chargerTargetA===0?'NOOP':'SET_CURRENT_0',{...base,requestedA:0})};
  }

  // Stable and already in requested locked phase mode.
  if(state.stage==='STABLE'&&confirmedMode===desiredMode){
    const next={...state,requestedMode:desiredMode,requestedA:desiredA,failure:null};
    return {state:next,action:action(chargerTargetA===desiredA?'NOOP':'SET_CURRENT',{...base,requestedA:desiredA})};
  }

  // New/mutated request starts a new transition.
  const requestChanged=state.requestedMode!==desiredMode||state.requestedA!==desiredA;
  if(state.stage==='STABLE'||state.stage==='FAILED'||requestChanged){
    const transitionId=`${nowMs}:${desiredMode}:${desiredA}`;
    const next={...state,stage:'ZEROING',transitionId,requestedMode:desiredMode,requestedA:desiredA,startedAt:nowIso(nowMs),stageSince:nowIso(nowMs),phaseCommandSentAt:null,phaseConfirmedAt:null,failure:null};
    return {state:next,action:action('SET_CURRENT_0',{...base,requestedA:0,reason:'PHASE_CHANGE_REQUIRES_ZERO_CURRENT'})};
  }

  if(state.stage==='ZEROING'){
    const zeroConfirmed=
      chargerTargetA===0 &&
      (chargerPowerW===null||chargerPowerW<=cfg.zeroConfirmW) &&
      (offeredA===null||offeredA<=cfg.zeroConfirmA);
    if(!zeroConfirmed){
      return {state,action:action('SET_CURRENT_0',{...base,requestedA:0,reason:'WAIT_ZERO_CONFIRMATION'})};
    }
    const next={...state,stage:'PHASE_COMMAND',stageSince:nowIso(nowMs)};
    return {state:next,action:action('SET_PHASE_MODE',{...base,phaseModeValue:easeeCommandForMode(desiredMode),reason:'ZERO_CONFIRMED'})};
  }

  if(state.stage==='PHASE_COMMAND'){
    if(commandResult?.transitionId===state.transitionId&&commandResult?.ok===false){
      return fail(`PHASE_COMMAND_FAILED:${String(commandResult?.reason||'UNKNOWN')}`);
    }
    if(commandResult?.transitionId===state.transitionId&&commandResult?.ok===true){
      const next={...state,stage:'CONFIRMING',stageSince:nowIso(nowMs),phaseCommandSentAt:commandResult.at||nowIso(nowMs)};
      return {state:next,action:action('WAIT_PHASE_CONFIRM',{...base,reason:'COMMAND_ACCEPTED'})};
    }
    return {state,action:action('SET_PHASE_MODE',{...base,phaseModeValue:easeeCommandForMode(desiredMode),reason:'COMMAND_NOT_YET_CONFIRMED_SENT'})};
  }

  if(state.stage==='CONFIRMING'){
    if(confirmedMode===desiredMode){
      const next={...state,stage:'DEADTIME',stageSince:nowIso(nowMs),phaseConfirmedAt:nowIso(nowMs)};
      return {state:next,action:action('WAIT_DEADTIME',{...base,remainingMs:cfg.deadTimeMs,reason:'PHASE_CONFIRMED'})};
    }
    if(stageAgeMs>cfg.commandConfirmTimeoutMs){
      return fail('PHASE_CONFIRM_TIMEOUT');
    }
    return {state,action:action('WAIT_PHASE_CONFIRM',{...base,reason:'PHASE_NOT_CONFIRMED'})};
  }

  if(state.stage==='DEADTIME'){
    const remaining=Math.max(0,cfg.deadTimeMs-stageAgeMs);
    if(remaining>0){
      return {state,action:action('WAIT_DEADTIME',{...base,remainingMs:remaining})};
    }
    const next={...state,stage:'APPLY_CURRENT',stageSince:nowIso(nowMs)};
    return {state:next,action:action('SET_CURRENT',{...base,requestedA:desiredA,reason:'PHASE_CONFIRMED_DEADTIME_COMPLETE'})};
  }

  if(state.stage==='APPLY_CURRENT'){
    if(confirmedMode!==desiredMode){
      return fail('PHASE_CONFIRMATION_LOST');
    }
    if(chargerTargetA===desiredA){
      const next={...state,stage:'STABLE',transitionId:null,startedAt:null,stageSince:nowIso(nowMs),failure:null};
      return {state:next,action:action('NOOP',{...base,requestedA:desiredA,reason:'TRANSITION_COMPLETE'})};
    }
    return {state,action:action('SET_CURRENT',{...base,requestedA:desiredA,reason:'WAIT_CURRENT_TARGET'})};
  }

  return fail('UNKNOWN_TRANSITION_STAGE');
}
