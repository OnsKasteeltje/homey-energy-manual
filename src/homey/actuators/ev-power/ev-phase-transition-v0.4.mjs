// Pure EV phase transition state machine v0.4
// No Homey/Easee calls. Returns the next actuator action only.
//
// Commissioning findings:
// - target_charger_current=0 alone is not a stable safe state;
// - resume_charging resets the dynamic charger-current limit;
// - therefore a transition requires a confirmed paused session and a temporary
//   symmetric circuit-current cap before resume.
//
// The circuit cap is set/restored through native Homey Easee control. Because
// all phases receive the same cap, EMS still does not select the physical phase.

export const TRANSITION_SCHEMA='EM2_EV_PHASE_TRANSITION_STATE_V0.4';
export const ACTION_SCHEMA='EM2_EV_PHASE_TRANSITION_ACTION_V0.4';

export const DEFAULTS=Object.freeze({
  minA:6,
  maxA:16,
  zeroConfirmW:250,
  zeroConfirmA:1,
  deadTimeMs:5000,
  commandConfirmTimeoutMs:30000,
  transitionWarnMs:90000,
  maxCircuitA:64,
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
    originalCircuitA:null,
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

function pauseConfirmed(input,cfg){
  const cs=String(input?.chargeState||'').toLowerCase();
  const powerW=finite(input?.chargerPowerW)?Math.max(0,Number(input.chargerPowerW)):null;
  const offeredA=finite(input?.offeredA)?Math.max(0,Number(input.offeredA)):null;
  return (
    input?.charging!==true &&
    cs==='plugged_in_paused' &&
    powerW!==null && powerW<=cfg.zeroConfirmW &&
    offeredA!==null && offeredA<=cfg.zeroConfirmA
  );
}

function circuitA(input,cfg){
  const raw=input?.circuitTargetA;
  if(raw===null||raw===undefined||raw==='')return null;
  const n=Number(raw);
  return Number.isInteger(n)&&n>=0&&n<=cfg.maxCircuitA?n:null;
}

export function decidePhaseTransition(input, previous=initialTransitionState(), nowMs=Date.now(), cfg=DEFAULTS){
  const desiredMode=String(input?.desiredMode||'OFF');
  const desiredA=Number(input?.desiredA??0);
  const gatePass=input?.gatePass===true;
  const controlFresh=input?.controlFresh===true;
  const liveEnabled=input?.liveEnabled===true;
  const chargerTargetA=finite(input?.chargerTargetA)?Number(input.chargerTargetA):null;
  const currentCircuitA=circuitA(input,cfg);
  const charging=input?.charging===true;
  const chargeState=String(input?.chargeState||'unknown').toLowerCase();
  const confirmedMode=normalizeEaseePhaseMode(input?.easeePhaseMode);
  const phaseCommandResult=input?.phaseCommandResult||null;
  const paused=pauseConfirmed(input,cfg);

  const state={...initialTransitionState(nowMs),...previous};
  const transitionAgeMs=state.startedAt?nowMs-Date.parse(state.startedAt):0;
  const stageAgeMs=state.stageSince?nowMs-Date.parse(state.stageSince):0;

  const fail=(reason)=>({
    state:{...state,stage:'FAILED',failure:reason,stageSince:nowIso(nowMs)},
    action:action('PAUSE_SESSION',{
      reason,failClosed:true,
      circuitRestoreA:state.originalCircuitA
    })
  });

  if(!gatePass||!controlFresh)return fail(!gatePass?'GATE_NOT_PASS':'CONTROL_NOT_FRESH');
  if(!validRequest(desiredMode,desiredA,cfg))return fail('INVALID_PHASE_REQUEST');

  const base={
    desiredMode,desiredA,confirmedMode,liveEnabled,chargeState,charging,
    pauseConfirmed:paused,currentCircuitA,originalCircuitA:state.originalCircuitA
  };

  if(desiredMode==='OFF'){
    const next={
      ...state,stage:'STABLE',requestedMode:'OFF',requestedA:0,
      transitionId:null,startedAt:null,stageSince:nowIso(nowMs),
      phaseCommandSentAt:null,phaseConfirmedAt:null,failure:null
    };
    return {state:next,action:action(paused?'NOOP':'PAUSE_SESSION',{
      ...base,reason:paused?'ALREADY_PAUSED':'OFF_REQUIRES_PAUSED_SESSION'
    })};
  }

  // Starting/resuming from a paused session in the already-confirmed mode still
  // needs the resume safety cap, because Easee resets charger current on resume.
  if(state.stage==='STABLE'&&confirmedMode===desiredMode&&paused){
    if(currentCircuitA===null)return fail('CIRCUIT_TARGET_UNKNOWN');
    if(currentCircuitA<desiredA)return fail('CIRCUIT_LIMIT_BELOW_REQUEST');
    const transitionId=`${nowMs}:${desiredMode}:${desiredA}`;
    const next={
      ...state,stage:'ARMING_CIRCUIT_CAP',transitionId,
      requestedMode:desiredMode,requestedA:desiredA,
      originalCircuitA:currentCircuitA,
      startedAt:nowIso(nowMs),stageSince:nowIso(nowMs),failure:null
    };
    return {state:next,action:action('SET_TRANSITION_CIRCUIT_CAP',{
      ...base,amps:desiredA,reason:'PAUSED_RESUME_REQUIRES_SAFETY_CAP'
    })};
  }

  if(state.stage==='STABLE'&&confirmedMode===desiredMode){
    const next={...state,requestedMode:desiredMode,requestedA:desiredA,failure:null};
    return {state:next,action:action(chargerTargetA===desiredA?'NOOP':'SET_CURRENT',{
      ...base,requestedA:desiredA,reason:'STABLE_CURRENT_CONTROL'
    })};
  }

  const requestChanged=state.requestedMode!==desiredMode||state.requestedA!==desiredA;
  if(state.stage==='STABLE'||state.stage==='FAILED'||requestChanged){
    if(currentCircuitA===null)return fail('CIRCUIT_TARGET_UNKNOWN');
    if(currentCircuitA<desiredA)return fail('CIRCUIT_LIMIT_BELOW_REQUEST');
    const transitionId=`${nowMs}:${desiredMode}:${desiredA}`;
    const next={
      ...state,stage:'PAUSING',transitionId,
      requestedMode:desiredMode,requestedA:desiredA,
      originalCircuitA:currentCircuitA,
      startedAt:nowIso(nowMs),stageSince:nowIso(nowMs),
      phaseCommandSentAt:null,phaseConfirmedAt:null,failure:null
    };
    return {state:next,action:action('PAUSE_SESSION',{
      ...base,originalCircuitA:currentCircuitA,
      reason:'PHASE_CHANGE_REQUIRES_PAUSED_SESSION'
    })};
  }

  if(state.stage==='PAUSING'){
    if(!paused)return {state,action:action('PAUSE_SESSION',{...base,reason:'WAIT_PAUSE_CONFIRMATION'})};
    const next={...state,stage:'PHASE_COMMAND',stageSince:nowIso(nowMs)};
    return {state:next,action:action('SET_PHASE_MODE',{
      ...base,phaseModeValue:easeeCommandForMode(desiredMode),reason:'PAUSE_CONFIRMED'
    })};
  }

  if(state.stage==='PHASE_COMMAND'){
    if(!paused)return fail('PAUSE_CONFIRMATION_LOST');
    if(phaseCommandResult?.transitionId===state.transitionId&&phaseCommandResult?.ok===false){
      return fail(`PHASE_COMMAND_FAILED:${String(phaseCommandResult?.reason||'UNKNOWN')}`);
    }
    if(phaseCommandResult?.transitionId===state.transitionId&&phaseCommandResult?.ok===true){
      const next={
        ...state,stage:'CONFIRMING_PHASE',stageSince:nowIso(nowMs),
        phaseCommandSentAt:phaseCommandResult.at||nowIso(nowMs)
      };
      return {state:next,action:action('WAIT_PHASE_CONFIRM',{...base,reason:'COMMAND_ACCEPTED'})};
    }
    return {state,action:action('SET_PHASE_MODE',{
      ...base,phaseModeValue:easeeCommandForMode(desiredMode),
      reason:'COMMAND_NOT_YET_CONFIRMED_SENT'
    })};
  }

  if(state.stage==='CONFIRMING_PHASE'){
    if(!paused)return fail('PAUSE_CONFIRMATION_LOST');
    if(confirmedMode===desiredMode){
      const next={
        ...state,stage:'DEADTIME',stageSince:nowIso(nowMs),
        phaseConfirmedAt:nowIso(nowMs)
      };
      return {state:next,action:action('WAIT_DEADTIME',{
        ...base,remainingMs:cfg.deadTimeMs,reason:'PHASE_CONFIRMED'
      })};
    }
    if(stageAgeMs>cfg.commandConfirmTimeoutMs){
      const next={...state,stageSince:nowIso(nowMs),phaseCommandSentAt:null};
      return {state:next,action:action('SET_PHASE_MODE',{
        ...base,phaseModeValue:easeeCommandForMode(desiredMode),
        reason:'PHASE_CONFIRM_RETRY'
      })};
    }
    return {state,action:action('WAIT_PHASE_CONFIRM',{...base,reason:'PHASE_NOT_CONFIRMED'})};
  }

  if(state.stage==='DEADTIME'){
    if(!paused){
      const next={...state,stage:'PAUSING',stageSince:nowIso(nowMs)};
      return {state:next,action:action('PAUSE_SESSION',{...base,reason:'WAIT_PAUSE_CONFIRMATION'})};
    }
    if(confirmedMode!==desiredMode){
      const next={...state,stage:'CONFIRMING_PHASE',stageSince:nowIso(nowMs),phaseCommandSentAt:null};
      return {state:next,action:action('SET_PHASE_MODE',{
        ...base,phaseModeValue:easeeCommandForMode(desiredMode),
        reason:'PHASE_CONFIRM_RETRY'
      })};
    }
    const remaining=Math.max(0,cfg.deadTimeMs-stageAgeMs);
    if(remaining>0)return {state,action:action('WAIT_DEADTIME',{...base,remainingMs:remaining})};
    const next={...state,stage:'ARMING_CIRCUIT_CAP',stageSince:nowIso(nowMs)};
    return {state:next,action:action('SET_TRANSITION_CIRCUIT_CAP',{
      ...base,amps:desiredA,reason:'PROTECT_RESUME_CURRENT_RESET'
    })};
  }

  if(state.stage==='ARMING_CIRCUIT_CAP'){
    if(!paused){
      return {state,action:action('PAUSE_SESSION',{...base,reason:'WAIT_PAUSE_CONFIRMATION'})};
    }
    if(confirmedMode!==desiredMode){
      const next={...state,stage:'CONFIRMING_PHASE',stageSince:nowIso(nowMs),phaseCommandSentAt:null};
      return {state:next,action:action('SET_PHASE_MODE',{
        ...base,phaseModeValue:easeeCommandForMode(desiredMode),
        reason:'PHASE_CONFIRM_RETRY'
      })};
    }
    if(currentCircuitA===desiredA){
      const next={...state,stage:'RESUMING',stageSince:nowIso(nowMs)};
      return {state:next,action:action('RESUME_SESSION',{
        ...base,reason:'TRANSITION_CIRCUIT_CAP_CONFIRMED'
      })};
    }
    return {state,action:action('SET_TRANSITION_CIRCUIT_CAP',{
      ...base,amps:desiredA,reason:'WAIT_CIRCUIT_CAP_CONFIRMATION'
    })};
  }

  if(state.stage==='RESUMING'){
    if(confirmedMode!==desiredMode)return fail('PHASE_CONFIRMATION_LOST');
    if(chargeState==='plugged_in'||chargeState==='plugged_in_charging'||charging){
      const next={...state,stage:'APPLY_CURRENT',stageSince:nowIso(nowMs)};
      return {state:next,action:action('SET_CURRENT',{
        ...base,requestedA:desiredA,reason:'RESUME_RESETS_CHARGER_CURRENT'
      })};
    }
    return {state,action:action('RESUME_SESSION',{...base,reason:'WAIT_SESSION_RESUME'})};
  }

  if(state.stage==='APPLY_CURRENT'){
    if(confirmedMode!==desiredMode)return fail('PHASE_CONFIRMATION_LOST');
    if(chargerTargetA!==desiredA){
      return {state,action:action('SET_CURRENT',{
        ...base,requestedA:desiredA,reason:'WAIT_CURRENT_TARGET'
      })};
    }
    if(charging||chargeState==='plugged_in_charging'){
      const restoreA=Number(state.originalCircuitA);
      if(!Number.isInteger(restoreA)||restoreA<desiredA||restoreA>cfg.maxCircuitA){
        return fail('ORIGINAL_CIRCUIT_LIMIT_INVALID');
      }
      const next={...state,stage:'RESTORING_CIRCUIT_CAP',stageSince:nowIso(nowMs)};
      return {state:next,action:action('RESTORE_CIRCUIT_CAP',{
        ...base,amps:restoreA,reason:'DESIRED_CURRENT_AND_CHARGING_CONFIRMED'
      })};
    }
    return {state,action:action('SET_CURRENT',{
      ...base,requestedA:desiredA,reason:'CURRENT_SET_WAIT_CHARGING'
    })};
  }

  if(state.stage==='RESTORING_CIRCUIT_CAP'){
    const restoreA=Number(state.originalCircuitA);
    if(!Number.isInteger(restoreA)||restoreA<desiredA||restoreA>cfg.maxCircuitA){
      return fail('ORIGINAL_CIRCUIT_LIMIT_INVALID');
    }
    if(currentCircuitA===restoreA){
      const next={
        ...state,stage:'STABLE',transitionId:null,startedAt:null,
        stageSince:nowIso(nowMs),originalCircuitA:null,failure:null
      };
      return {state:next,action:action('NOOP',{
        ...base,requestedA:desiredA,reason:'TRANSITION_COMPLETE'
      })};
    }
    return {state,action:action('RESTORE_CIRCUIT_CAP',{
      ...base,amps:restoreA,reason:'WAIT_CIRCUIT_RESTORE_CONFIRMATION'
    })};
  }

  return fail('UNKNOWN_TRANSITION_STAGE');
}
