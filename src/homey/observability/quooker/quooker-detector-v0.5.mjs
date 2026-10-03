// Quooker heating detector v0.5 — phase-vector edge classifier.
// Observe-only. Cooker switch is authoritative for OFF/ON.
// Heating is identified by a ~1.6 kW step isolated to L3.

export const SCHEMA='EM2_QUOOKER_DETECTOR_V0.5';

export const CONFIG=Object.freeze({
  edgeMinW:1300,
  edgeMaxW:1900,
  quietOtherPhaseW:350,
  totalResidualW:500,
  maxSampleAgeMs:20000,
  maxHeatingMs:12*60*1000,
});

const finite=v=>Number.isFinite(Number(v));
const n=v=>finite(v)?Number(v):null;
const abs=Math.abs;

function normSample(raw){
  if(!raw)return null;
  const s={
    atMs:n(raw.atMs),
    totalW:n(raw.totalW),
    l1W:n(raw.l1W),
    l2W:n(raw.l2W),
    l3W:n(raw.l3W),
  };
  return s.atMs!==null&&s.l1W!==null&&s.l2W!==null&&s.l3W!==null?s:null;
}

export function phaseDelta(previousSample,currentSample){
  const a=normSample(previousSample), b=normSample(currentSample);
  if(!a||!b)return null;
  const dtMs=b.atMs-a.atMs;
  if(dtMs<=0)return null;
  return {
    dtMs,
    d1W:b.l1W-a.l1W,
    d2W:b.l2W-a.l2W,
    d3W:b.l3W-a.l3W,
    dTotalW:a.totalW!==null&&b.totalW!==null?b.totalW-a.totalW:null,
  };
}

export function isIsolatedL3Edge(delta,direction,cfg=CONFIG){
  if(!delta||delta.dtMs>cfg.maxSampleAgeMs)return false;
  const signed=direction==='down'?-delta.d3W:delta.d3W;
  if(signed<cfg.edgeMinW||signed>cfg.edgeMaxW)return false;
  if(abs(delta.d1W)>cfg.quietOtherPhaseW)return false;
  if(abs(delta.d2W)>cfg.quietOtherPhaseW)return false;
  if(delta.dTotalW!==null){
    const expected=direction==='down'?-signed:signed;
    if(abs(delta.dTotalW-expected)>cfg.totalResidualW)return false;
  }
  return true;
}

export function classifyQuookerEdge(input,previous={},cfg=CONFIG){
  const switchOn=input?.switchOn===true;
  const current=normSample(input?.sample);
  const last=normSample(previous?.lastSample);
  const wasActive=previous?.active===true;
  const heatingStartedAtMs=n(previous?.heatingStartedAtMs);
  const detectedPowerW=Math.round(n(previous?.detectedPowerW)??0);

  if(!switchOn){
    return {
      schema:SCHEMA,valid:current!==null,switchOn:false,active:false,powerW:0,
      status:'OFF',reason:'SWITCH_OFF',lastSample:current||last,
      heatingStartedAtMs:null,detectedPowerW:0,delta:null
    };
  }

  if(!current){
    return {
      schema:SCHEMA,valid:false,switchOn:true,active:false,powerW:0,
      status:'ON_IDLE',reason:'INVALID_PHASE_SAMPLE',lastSample:last,
      heatingStartedAtMs:null,detectedPowerW:0,delta:null
    };
  }

  const delta=phaseDelta(last,current);
  const start=isIsolatedL3Edge(delta,'up',cfg);
  const stop=isIsolatedL3Edge(delta,'down',cfg);
  const timedOut=wasActive&&heatingStartedAtMs!==null&&
    current.atMs-heatingStartedAtMs>cfg.maxHeatingMs;

  if(wasActive){
    if(stop){
      return {
        schema:SCHEMA,valid:true,switchOn:true,active:false,powerW:0,
        status:'ON_IDLE',reason:'HEATING_STOP_ISOLATED_L3_EDGE',
        lastSample:current,heatingStartedAtMs:null,detectedPowerW:0,delta
      };
    }
    if(timedOut){
      return {
        schema:SCHEMA,valid:true,switchOn:true,active:false,powerW:0,
        status:'ON_IDLE',reason:'HEATING_TIMEOUT_FAIL_SAFE',
        lastSample:current,heatingStartedAtMs:null,detectedPowerW:0,delta
      };
    }
    return {
      schema:SCHEMA,valid:true,switchOn:true,active:true,
      powerW:detectedPowerW,status:'HEATING',reason:'HEATING_LATCHED_UNTIL_FALLING_EDGE',
      lastSample:current,heatingStartedAtMs,detectedPowerW,delta
    };
  }

  if(start){
    const p=Math.round(delta.d3W);
    return {
      schema:SCHEMA,valid:true,switchOn:true,active:true,powerW:p,
      status:'HEATING',reason:'HEATING_START_ISOLATED_L3_EDGE',
      lastSample:current,heatingStartedAtMs:current.atMs,detectedPowerW:p,delta
    };
  }

  return {
    schema:SCHEMA,valid:true,switchOn:true,active:false,powerW:0,
    status:'ON_IDLE',
    reason:delta?'NO_ISOLATED_L3_EDGE':'BASELINE_SAMPLE',
    lastSample:current,heatingStartedAtMs:null,detectedPowerW:0,delta
  };
}
