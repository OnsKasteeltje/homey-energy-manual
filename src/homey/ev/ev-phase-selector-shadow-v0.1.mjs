// EV Phase Selector v0.1 SHADOW
// Architecture: P1 is authoritative. No Easee writes. No control-path writes.
// State machine: OFF <-> 1P 6..16A <-> 3P 6..16A.
//
// Sign convention: negative P1 = export, positive P1 = import.
// IMPORTANT: previous SHADOW state is used only for dwell/hysteresis.
// It must never be treated as physical EV load. Counterfactual available power
// may add back only the fresh ACTUAL production EV command supplied by the caller.

export const CONFIG = Object.freeze({
  voltageV: 230,
  minA: 6,
  maxA: 16,
  onePhaseMinW: 1380,
  onePhaseMaxW: 3680,
  threePhaseMinW: 4140,
  enter3pW: 4400,
  leave3pW: 3600,
  start1pW: 1500,
  stop1pW: 1100,
  minModeDwellMs: 120000,
  minPhaseDwellMs: 300000,
});

const clamp=(n,lo,hi)=>Math.max(lo,Math.min(hi,n));
const finite=n=>Number.isFinite(Number(n));

export function decideEvPhaseShadow(input, previous={}, nowMs=Date.now(), cfg=CONFIG) {
  const p1TotalW=Number(input?.p1TotalW);
  const phases=[Number(input?.p1L1W),Number(input?.p1L2W),Number(input?.p1L3W)];
  const opportunityAllowed=input?.opportunityAllowed===true;
  const maxA=clamp(Math.floor(Number(input?.maxA??cfg.maxA)),0,cfg.maxA);

  if(!opportunityAllowed || !finite(p1TotalW) || phases.some(x=>!finite(x)) || maxA<cfg.minA) {
    return shadow('OFF',0,null,'BLOCKED_OR_INVALID_INPUT',input,previous,nowMs,cfg);
  }

  const prevMode=String(previous?.mode||'OFF');
  const prevPhase=Number.isInteger(previous?.phase)?previous.phase:null;

  // Physical-load reconstruction is deliberately separate from SHADOW state.
  // actualEvCommandA/PhaseCount/Phase must come from fresh production control authority,
  // never from stale Easee telemetry and never from the previous SHADOW recommendation.
  const actualA=clamp(Math.floor(Number(input?.actualEvCommandA??0)),0,cfg.maxA);
  const actualPhaseCount=Number(input?.actualEvPhaseCount??0);
  const actualPhase=Number.isInteger(input?.actualEvPhase)?input.actualEvPhase:null;
  const actualShapeValid=
    actualA===0 ||
    actualPhaseCount===3 ||
    (actualPhaseCount===1 && actualPhase>=1 && actualPhase<=3);

  if(!actualShapeValid) {
    return shadow('OFF',0,null,'INVALID_ACTUAL_EV_COMMAND_SHAPE',input,previous,nowMs,cfg);
  }

  const actualEvW=actualA*(actualPhaseCount===3?3:actualPhaseCount===1?1:0)*cfg.voltageV;
  const availableTotalW=Math.max(0,-p1TotalW+actualEvW);

  const phaseAvailableW=phases.map((w,i)=>{
    const phaseNo=i+1;
    const addBackW=actualA*cfg.voltageV*(
      actualPhaseCount===3 || (actualPhaseCount===1 && actualPhase===phaseNo) ? 1 : 0
    );
    return Math.max(0,-w+addBackW);
  });
  const bestIdx=phaseAvailableW.indexOf(Math.max(...phaseAvailableW));
  const bestPhase=bestIdx+1;
  const bestPhaseW=phaseAvailableW[bestIdx];

  const lastModeChangeMs=Number(previous?.modeSinceMs??0);
  const lastPhaseChangeMs=Number(previous?.phaseSinceMs??0);
  const modeDwellOK=nowMs-lastModeChangeMs>=cfg.minModeDwellMs;
  const phaseDwellOK=nowMs-lastPhaseChangeMs>=cfg.minPhaseDwellMs;

  let mode=prevMode, phase=prevPhase, reason='HOLD';

  if(prevMode==='3P') {
    if(availableTotalW<cfg.leave3pW && modeDwellOK) {
      if(bestPhaseW>=cfg.start1pW){mode='1P';phase=bestPhase;reason='3P_TO_1P_TOTAL_SURPLUS_LOW';}
      else {mode='OFF';phase=null;reason='3P_TO_OFF_SURPLUS_LOW';}
    }
  } else if(prevMode==='1P') {
    if(availableTotalW>=cfg.enter3pW && modeDwellOK) {
      mode='3P';phase=null;reason='1P_TO_3P_TOTAL_SURPLUS_HIGH';
    } else if(bestPhaseW<cfg.stop1pW && modeDwellOK) {
      mode='OFF';phase=null;reason='1P_TO_OFF_PHASE_SURPLUS_LOW';
    } else if(bestPhase!==prevPhase && phaseDwellOK && bestPhaseW>=cfg.start1pW) {
      phase=bestPhase;reason='1P_BEST_PHASE_CHANGE';
    }
  } else {
    if(availableTotalW>=cfg.enter3pW) {
      mode='3P';phase=null;reason='OFF_TO_3P_TOTAL_SURPLUS';
    } else if(bestPhaseW>=cfg.start1pW) {
      mode='1P';phase=bestPhase;reason='OFF_TO_1P_BEST_PHASE';
    }
  }

  let requestedA=0;
  if(mode==='3P') requestedA=clamp(Math.floor(availableTotalW/(3*cfg.voltageV)),cfg.minA,maxA);
  if(mode==='1P') requestedA=clamp(Math.floor(bestPhaseW/cfg.voltageV),cfg.minA,maxA);

  return shadow(mode,requestedA,phase,reason,{
    ...input,
    actualEvW,
    availableTotalW,
    phaseAvailableW,
    bestPhase,
    bestPhaseW
  },previous,nowMs,cfg);
}

function shadow(mode,requestedA,phase,reason,input,previous,nowMs,cfg){
  const changed=mode!==String(previous?.mode||'OFF');
  const phaseChanged=phase!==(Number.isInteger(previous?.phase)?previous.phase:null);
  return {
    schema:'EM2_EV_PHASE_SELECTOR_SHADOW_V0.1',
    generatedAt:new Date(nowMs).toISOString(),
    mode,
    requestedA,
    requestedW:mode==='3P'?requestedA*3*cfg.voltageV:mode==='1P'?requestedA*cfg.voltageV:0,
    phase,
    reason,
    p1Authoritative:true,
    actualEvCommandSource:'PRODUCTION_CONTROL_AUTHORITY_INPUT',
    shadowStateAffectsPhysicalReconstruction:false,
    threePhaseDecisionBasis:'TOTAL_P1_NET_POWER_PLUS_ACTUAL_EV_COMMAND',
    onePhaseDecisionBasis:'BEST_P1_PHASE_SURPLUS_PLUS_ACTUAL_EV_COMMAND',
    modeSinceMs:changed?nowMs:Number(previous?.modeSinceMs??nowMs),
    phaseSinceMs:phaseChanged?nowMs:Number(previous?.phaseSinceMs??nowMs),
    input,
    deviceWrites:false,
    controlWrites:false,
    shadow:true
  };
}
