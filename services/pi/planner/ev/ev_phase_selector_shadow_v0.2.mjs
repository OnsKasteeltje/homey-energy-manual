// EV Phase Selector v0.2 SHADOW
// Pi planner component. P1 total net power is authoritative for PV opportunity.
// Decision: OFF | 1P | 3P + requested current.
// Physical phase selection in 1P is owned by Easee/Equalizer, not EMS.
//
// Sign convention: negative P1 = export, positive P1 = import.
// Previous SHADOW state is used only for mode dwell/hysteresis.
// It is never treated as physical EV load.

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
});

const clamp=(n,lo,hi)=>Math.max(lo,Math.min(hi,n));
const finite=n=>Number.isFinite(Number(n));

export function decideEvPhaseShadow(input, previous={}, nowMs=Date.now(), cfg=CONFIG) {
  const p1TotalW=Number(input?.p1TotalW);
  const opportunityAllowed=input?.opportunityAllowed===true;
  const maxA=clamp(Math.floor(Number(input?.maxA??cfg.maxA)),0,cfg.maxA);

  if(!opportunityAllowed || !finite(p1TotalW) || maxA<cfg.minA) {
    return shadow('OFF',0,'BLOCKED_OR_INVALID_INPUT',input,previous,nowMs,cfg);
  }

  const prevMode=String(previous?.mode||'OFF');

  // Physical-load reconstruction uses only fresh production control authority.
  // The physical phase used during 1P is deliberately irrelevant here:
  // total P1 is the energy-control feedback, Equalizer owns phase safety/selection.
  const actualA=clamp(Math.floor(Number(input?.actualEvCommandA??0)),0,cfg.maxA);
  const actualPhaseCount=Number(input?.actualEvPhaseCount??0);
  const actualShapeValid=
    actualA===0 ||
    actualPhaseCount===1 ||
    actualPhaseCount===3;

  if(!actualShapeValid) {
    return shadow('OFF',0,'INVALID_ACTUAL_EV_COMMAND_SHAPE',input,previous,nowMs,cfg);
  }

  const actualEvW=actualA*(actualPhaseCount===3?3:actualPhaseCount===1?1:0)*cfg.voltageV;
  const availableTotalW=Math.max(0,-p1TotalW+actualEvW);

  const lastModeChangeMs=Number(previous?.modeSinceMs??0);
  const modeDwellOK=nowMs-lastModeChangeMs>=cfg.minModeDwellMs;

  let mode=prevMode, reason='HOLD';

  if(prevMode==='3P') {
    if(availableTotalW<cfg.leave3pW && modeDwellOK) {
      if(availableTotalW>=cfg.start1pW){mode='1P';reason='3P_TO_1P_TOTAL_SURPLUS_LOW';}
      else {mode='OFF';reason='3P_TO_OFF_SURPLUS_LOW';}
    }
  } else if(prevMode==='1P') {
    if(availableTotalW>=cfg.enter3pW && modeDwellOK) {
      mode='3P';reason='1P_TO_3P_TOTAL_SURPLUS_HIGH';
    } else if(availableTotalW<cfg.stop1pW && modeDwellOK) {
      mode='OFF';reason='1P_TO_OFF_TOTAL_SURPLUS_LOW';
    }
  } else {
    if(availableTotalW>=cfg.enter3pW) {
      mode='3P';reason='OFF_TO_3P_TOTAL_SURPLUS';
    } else if(availableTotalW>=cfg.start1pW) {
      mode='1P';reason='OFF_TO_1P_TOTAL_SURPLUS';
    }
  }

  let requestedA=0;
  if(mode==='3P') requestedA=clamp(Math.floor(availableTotalW/(3*cfg.voltageV)),cfg.minA,maxA);
  if(mode==='1P') requestedA=clamp(Math.floor(availableTotalW/cfg.voltageV),cfg.minA,maxA);

  return shadow(mode,requestedA,reason,{
    ...input,
    actualEvW,
    availableTotalW
  },previous,nowMs,cfg);
}

function shadow(mode,requestedA,reason,input,previous,nowMs,cfg){
  const changed=mode!==String(previous?.mode||'OFF');
  return {
    schema:'EMS_PI_EV_PHASE_SELECTOR_SHADOW_V0.2',
    generatedAt:new Date(nowMs).toISOString(),
    mode,
    requestedA,
    requestedW:mode==='3P'?requestedA*3*cfg.voltageV:mode==='1P'?requestedA*cfg.voltageV:0,
    phaseCommand:null,
    physicalPhaseOwner:mode==='1P'?'EASEE_EQUALIZER':'NOT_APPLICABLE',
    reason,
    p1Authoritative:true,
    p1DecisionBasis:'TOTAL_NET_GRID_POWER_PLUS_ACTUAL_EV_COMMAND',
    actualEvCommandSource:'PRODUCTION_CONTROL_AUTHORITY_INPUT',
    shadowStateAffectsPhysicalReconstruction:false,
    modeSinceMs:changed?nowMs:Number(previous?.modeSinceMs??nowMs),
    input,
    deviceWrites:false,
    controlWrites:false,
    shadow:true
  };
}
