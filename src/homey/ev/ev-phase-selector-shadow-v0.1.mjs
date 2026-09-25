// EV Phase Selector v0.1 SHADOW
// Architecture: P1 is authoritative. No Easee writes. No control-path writes.
// State machine: OFF <-> 1P 6..16A <-> 3P 6..16A.
//
// Sign convention: negative P1 = export, positive P1 = import.
// 1P selection uses the phase with the largest sustained export.
// 3P selection uses TOTAL net P1 power, not equal per-phase surplus.
//
// This module is pure and intended for replay/shadow validation before Homey LIVE integration.

export const CONFIG = Object.freeze({
  voltageV: 230,
  minA: 6,
  maxA: 16,
  onePhaseMinW: 1380,
  onePhaseMaxW: 3680,
  threePhaseMinW: 4140,
  // Deliberate hysteresis around the 1P16A / 3P6A transition.
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

  // P1 closed-loop available power: add back only our previous commanded EV load.
  const prevMode=String(previous?.mode||'OFF');
  const prevA=Number.isInteger(previous?.requestedA)?previous.requestedA:0;
  const prevPhase=Number.isInteger(previous?.phase)?previous.phase:null;
  const prevEvW=prevMode==='3P'?prevA*3*cfg.voltageV:prevMode==='1P'?prevA*cfg.voltageV:0;
  // P1 is measured while the EV may already be charging. Add the commanded EV load
  // back only to estimate the counterfactual total PV surplus before EV consumption.
  const availableTotalW=Math.max(0,-p1TotalW+prevEvW);
  // Mode fallback must react to the actual residual grid balance, otherwise adding
  // the current 3P load back makes 3P self-sustain even after PV has collapsed.
  const residualExportW=Math.max(0,-p1TotalW);

  // For 1P, estimate counterfactual per-phase surplus by adding previous 1P EV load back to its phase.
  const phaseAvailableW=phases.map((w,i)=>Math.max(0,-w+(prevMode==='1P'&&prevPhase===i+1?prevA*cfg.voltageV:0)));
  const bestIdx=phaseAvailableW.indexOf(Math.max(...phaseAvailableW));
  const bestPhase=bestIdx+1;
  const bestPhaseW=phaseAvailableW[bestIdx];

  const lastModeChangeMs=Number(previous?.modeSinceMs??0);
  const lastPhaseChangeMs=Number(previous?.phaseSinceMs??0);
  const modeDwellOK=nowMs-lastModeChangeMs>=cfg.minModeDwellMs;
  const phaseDwellOK=nowMs-lastPhaseChangeMs>=cfg.minPhaseDwellMs;

  let mode=prevMode, phase=prevPhase, reason='HOLD';

  if(prevMode==='3P') {
    if(residualExportW<cfg.leave3pW && modeDwellOK) {
      if(bestPhaseW>=cfg.start1pW){mode='1P';phase=bestPhase;reason='3P_TO_1P_RESIDUAL_SURPLUS_LOW';}
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

  return shadow(mode,requestedA,phase,reason,{...input,availableTotalW,residualExportW,phaseAvailableW,bestPhase,bestPhaseW},previous,nowMs,cfg);
}

function shadow(mode,requestedA,phase,reason,input,previous,nowMs,cfg){
  const changed=mode!==String(previous?.mode||'OFF');
  const phaseChanged=phase!== (Number.isInteger(previous?.phase)?previous.phase:null);
  return {
    schema:'EM2_EV_PHASE_SELECTOR_SHADOW_V0.1',
    generatedAt:new Date(nowMs).toISOString(),
    mode,
    requestedA,
    requestedW:mode==='3P'?requestedA*3*cfg.voltageV:mode==='1P'?requestedA*cfg.voltageV:0,
    phase,
    reason,
    p1Authoritative:true,
    threePhaseDecisionBasis:'TOTAL_P1_NET_POWER',
    onePhaseDecisionBasis:'BEST_P1_PHASE_SURPLUS',
    modeSinceMs:changed?nowMs:Number(previous?.modeSinceMs??nowMs),
    phaseSinceMs:phaseChanged?nowMs:Number(previous?.phaseSinceMs??nowMs),
    input,
    deviceWrites:false,
    controlWrites:false,
    shadow:true
  };
}
