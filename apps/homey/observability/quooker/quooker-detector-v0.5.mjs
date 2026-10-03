// Quooker heating detector v0.5 — pure observe-only classifier.
// A Quooker heating pulse is an isolated short L3 step while L1/L2 remain stable.

export const SCHEMA='EM2_QUOOKER_DETECTOR_V0.5';

export const CONFIG=Object.freeze({
  startMinW:1300,
  startMaxW:1900,
  holdMinW:1100,
  holdMaxW:2050,
  sidePhaseMaxAbsDeltaW:350,
  sidePhaseHoldMaxAbsDeltaW:500,
  maxHeatingMs:90000,
});

const finite=v=>Number.isFinite(Number(v));
const n=v=>finite(v)?Number(v):null;
const round=v=>v===null?null:Math.round(v);

function baseResult({switchOn,l1W,l2W,l3W,baseline,reason,valid=true}){
  return {
    schema:SCHEMA,valid,switchOn,active:false,powerW:0,
    status:switchOn?'ON_IDLE':'OFF',
    l1W:round(l1W),l2W:round(l2W),l3W:round(l3W),
    baselineL1W:round(baseline.l1W),baselineL2W:round(baseline.l2W),baselineL3W:round(baseline.l3W),
    deltaL1W:l1W===null||baseline.l1W===null?null:round(l1W-baseline.l1W),
    deltaL2W:l2W===null||baseline.l2W===null?null:round(l2W-baseline.l2W),
    deltaL3W:l3W===null||baseline.l3W===null?null:round(l3W-baseline.l3W),
    heatingStartedAtMs:null,
    reason,
  };
}

export function classifyQuookerSample(input, previous={}, cfg=CONFIG){
  const switchOn=input?.switchOn===true;
  const l1W=n(input?.l1W), l2W=n(input?.l2W), l3W=n(input?.l3W);
  const nowMs=finite(input?.nowMs)?Number(input.nowMs):Date.now();

  const previousBaseline={
    l1W:n(previous?.baselineL1W),
    l2W:n(previous?.baselineL2W),
    l3W:n(previous?.baselineL3W),
  };
  const previousActive=previous?.active===true;
  const previousStatus=String(previous?.status||'UNKNOWN');
  const previousHeatingStartedAtMs=n(previous?.heatingStartedAtMs);

  if(l1W===null||l2W===null||l3W===null){
    return baseResult({
      switchOn,l1W,l2W,l3W,baseline:previousBaseline,
      reason:'INVALID_PHASE_SAMPLE',valid:false,
    });
  }

  const current={l1W,l2W,l3W};

  if(!switchOn){
    return baseResult({
      switchOn:false,l1W,l2W,l3W,baseline:current,
      reason:'SWITCH_OFF_BASELINE_TRACK',
    });
  }

  if(previousBaseline.l1W===null||previousBaseline.l2W===null||previousBaseline.l3W===null){
    return baseResult({
      switchOn:true,l1W,l2W,l3W,baseline:current,
      reason:'BASELINE_INITIALIZED',
    });
  }

  const d1=l1W-previousBaseline.l1W;
  const d2=l2W-previousBaseline.l2W;
  const d3=l3W-previousBaseline.l3W;
  const sideLimit=previousActive?cfg.sidePhaseHoldMaxAbsDeltaW:cfg.sidePhaseMaxAbsDeltaW;
  const sidePhasesStable=Math.abs(d1)<=sideLimit && Math.abs(d2)<=sideLimit;
  const l3Signature=previousActive
    ? d3>=cfg.holdMinW && d3<=cfg.holdMaxW
    : d3>=cfg.startMinW && d3<=cfg.startMaxW;

  const heatingAgeMs=previousActive && previousHeatingStartedAtMs!==null
    ? Math.max(0,nowMs-previousHeatingStartedAtMs)
    : 0;

  if(previousActive && previousHeatingStartedAtMs!==null && heatingAgeMs>=cfg.maxHeatingMs){
    return baseResult({
      switchOn:true,l1W,l2W,l3W,baseline:current,
      reason:'HEATING_MAX_DURATION_FAILSAFE',
    });
  }

  if(l3Signature && sidePhasesStable){
    return {
      schema:SCHEMA,valid:true,switchOn:true,active:true,powerW:round(d3),status:'HEATING',
      l1W:round(l1W),l2W:round(l2W),l3W:round(l3W),
      baselineL1W:round(previousBaseline.l1W),baselineL2W:round(previousBaseline.l2W),baselineL3W:round(previousBaseline.l3W),
      deltaL1W:round(d1),deltaL2W:round(d2),deltaL3W:round(d3),
      heatingStartedAtMs:previousActive && previousHeatingStartedAtMs!==null?previousHeatingStartedAtMs:nowMs,
      reason:previousActive?'HEATING_HOLD_ISOLATED_L3':'HEATING_START_ISOLATED_L3',
    };
  }

  const reason=!sidePhasesStable && d3>=cfg.startMinW && d3<=cfg.startMaxW
    ? 'REJECT_SIDE_PHASE_MOVEMENT'
    : previousStatus==='HEATING'
      ? 'HEATING_STOP_BASELINE_RESET'
      : 'ON_IDLE_BASELINE_TRACK';

  return {
    ...baseResult({switchOn:true,l1W,l2W,l3W,baseline:current,reason}),
    deltaL1W:round(d1),deltaL2W:round(d2),deltaL3W:round(d3),
  };
}
