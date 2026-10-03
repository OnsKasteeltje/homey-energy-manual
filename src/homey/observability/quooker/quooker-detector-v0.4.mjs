// Quooker heating detector v0.4 — pure classifier.
// Observe-only. Switch state is authoritative for OFF/ON.
// L3 delta relative to a recent non-heating baseline classifies HEATING.

export const SCHEMA='EM2_QUOOKER_DETECTOR_V0.4';

export const CONFIG=Object.freeze({
  startMinW:1300,
  startMaxW:1900,
  holdMinW:1100,
  holdMaxW:2050,
});

const finite=v=>Number.isFinite(Number(v));
const n=v=>finite(v)?Number(v):null;

export function classifyQuookerSample(input, previous={}, cfg=CONFIG){
  const switchOn=input?.switchOn===true;
  const l3W=n(input?.l3W);
  const previousBaseline=n(previous?.baselineL3W);
  const previousActive=previous?.active===true;
  const previousStatus=String(previous?.status||'UNKNOWN');

  if(l3W===null){
    return {
      schema:SCHEMA,
      valid:false,
      switchOn,
      active:false,
      powerW:0,
      status:switchOn?'ON_IDLE':'OFF',
      baselineL3W:previousBaseline,
      deltaW:null,
      reason:'INVALID_L3'
    };
  }

  if(!switchOn){
    return {
      schema:SCHEMA,
      valid:true,
      switchOn:false,
      active:false,
      powerW:0,
      status:'OFF',
      baselineL3W:l3W,
      deltaW:0,
      reason:'SWITCH_OFF_BASELINE_TRACK'
    };
  }

  // Keep the last non-heating baseline across OFF->ON. This is important:
  // it means an element that energizes immediately after the switch turns on
  // is still compared with the recent OFF background instead of becoming its
  // own baseline.
  const baseline=previousBaseline===null?l3W:previousBaseline;
  const deltaW=l3W-baseline;

  const heating=previousActive
    ? deltaW>=cfg.holdMinW && deltaW<=cfg.holdMaxW
    : deltaW>=cfg.startMinW && deltaW<=cfg.startMaxW;

  if(heating){
    return {
      schema:SCHEMA,
      valid:true,
      switchOn:true,
      active:true,
      powerW:Math.round(deltaW),
      status:'HEATING',
      baselineL3W:baseline,
      deltaW:Math.round(deltaW),
      reason:previousActive?'HEATING_HOLD_DELTA':'HEATING_START_DELTA'
    };
  }

  // While the switch is ON but the element is not heating, the current L3
  // value is the best background reference for the next pulse. This lets the
  // baseline follow PV ramps and unrelated L3 loads without learning through
  // an active Quooker pulse.
  return {
    schema:SCHEMA,
    valid:true,
    switchOn:true,
    active:false,
    powerW:0,
    status:'ON_IDLE',
    baselineL3W:l3W,
    deltaW:Math.round(deltaW),
    reason:previousStatus==='HEATING'?'HEATING_STOP_BASELINE_RESET':'ON_IDLE_BASELINE_TRACK'
  };
}
