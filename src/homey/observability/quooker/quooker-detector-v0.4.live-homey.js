// EM v2 | 01 Quooker Detector | v0.4 LIVE OBSERVE-ONLY
// Switch is authoritative for OFF/ON. P1 L3 delta classifies heating.
// No physical writes. Runs every 15 s plus immediate Cooker on/off triggers.

const VERSION='EM2_QUOOKER_DETECTOR_V0.4';
const COOKER_ID='42992d14-c4e4-43fc-aaf0-29a73a8e2eb9';
const P1_ID='7a696d77-15fb-4b68-9bce-f1e39bff5045';
const OFF_P1_REFRESH_MS=55000;
const START_MIN_W=1300, START_MAX_W=1900;
const HOLD_MIN_W=1100, HOLD_MAX_W=2050;

const NAMES={
  switchOn:'EM_Quooker_Switch_On',
  active:'EM_Quooker_Active',
  powerW:'EM_Quooker_Power_W',
  status:'EM_Quooker_Status',
  lastSample:'EM_Quooker_Last_Sample',
  baseline:'EM_Quooker_Baseline_L3_W',
  lastTransition:'EM_Quooker_Last_Transition',
  history:'EM_Quooker_Transition_History',
  lastHeatingAt:'EM_Quooker_Last_Heating_At',
  lastHeatingPowerW:'EM_Quooker_Last_Heating_Power_W',
  diagnostic:'EM_Quooker_Diagnostic'
};

const now=Date.now();
const iso=new Date(now).toISOString();
const num=v=>Number.isFinite(Number(v))?Number(v):null;
const parse=v=>{try{return JSON.parse(String(v??''));}catch{return null;}};

const [cooker,allVars]=await Promise.all([
  Homey.devices.getDevice({id:COOKER_ID}),
  Homey.logic.getVariables()
]);
const byName=Object.fromEntries(Object.values(allVars).map(v=>[v.name,v]));

const ensure=async(name,type,initial)=>{
  let v=byName[name];
  if(v)return v;
  v=await Homey.logic.createVariable({variable:{name,type,value:initial}});
  byName[name]=v;
  return v;
};
const set=async(name,type,value)=>{
  const v=await ensure(name,type,value);
  if(v.value===value)return;
  await Homey.logic.updateVariable({id:v.id,variable:{value}});
  v.value=value;
};

const diag=parse(byName[NAMES.diagnostic]?.value);
const previous={
  baselineL3W:num(diag?.baselineL3W),
  active:diag?.active===true,
  status:String(diag?.status||byName[NAMES.status]?.value||'UNKNOWN'),
  switchOn:diag?.switchOn===true,
  lastP1SampleAt:String(diag?.lastP1SampleAt||'')
};

const cookerOn=cooker?.capabilitiesObj?.onoff?.value===true;
const lastP1Ms=Date.parse(previous.lastP1SampleAt);
const p1AgeMs=Number.isFinite(lastP1Ms)?now-lastP1Ms:Infinity;
const switchChanged=previous.switchOn!==cookerOn;
const needP1=cookerOn || switchChanged || previous.baselineL3W===null || p1AgeMs>=OFF_P1_REFRESH_MS;

let l3W=null;
let p1Sampled=false;
let lastP1SampleAt=previous.lastP1SampleAt||null;

if(needP1){
  const p1=await Homey.devices.getDevice({id:P1_ID});
  l3W=num(p1?.capabilitiesObj?.['measure_power.l3']?.value);
  p1Sampled=l3W!==null;
  if(p1Sampled)lastP1SampleAt=iso;
}

let result;
if(!cookerOn && !p1Sampled){
  result={
    valid:true,switchOn:false,active:false,powerW:0,status:'OFF',
    baselineL3W:previous.baselineL3W,deltaW:0,
    reason:'SWITCH_OFF_BASELINE_REUSE'
  };
}else if(l3W===null){
  result={
    valid:false,switchOn:cookerOn,active:false,powerW:0,
    status:cookerOn?'ON_IDLE':'OFF',
    baselineL3W:previous.baselineL3W,deltaW:null,
    reason:'INVALID_L3'
  };
}else if(!cookerOn){
  result={
    valid:true,switchOn:false,active:false,powerW:0,status:'OFF',
    baselineL3W:l3W,deltaW:0,
    reason:'SWITCH_OFF_BASELINE_TRACK'
  };
}else{
  const baseline=previous.baselineL3W===null?l3W:previous.baselineL3W;
  const delta=l3W-baseline;
  const heating=previous.active
    ? delta>=HOLD_MIN_W && delta<=HOLD_MAX_W
    : delta>=START_MIN_W && delta<=START_MAX_W;

  if(heating){
    result={
      valid:true,switchOn:true,active:true,powerW:Math.round(delta),
      status:'HEATING',baselineL3W:baseline,deltaW:Math.round(delta),
      reason:previous.active?'HEATING_HOLD_DELTA':'HEATING_START_DELTA'
    };
  }else{
    result={
      valid:true,switchOn:true,active:false,powerW:0,status:'ON_IDLE',
      baselineL3W:l3W,deltaW:Math.round(delta),
      reason:previous.status==='HEATING'
        ?'HEATING_STOP_BASELINE_RESET'
        :'ON_IDLE_BASELINE_TRACK'
    };
  }
}

let history=parse(byName[NAMES.history]?.value);
if(!Array.isArray(history))history=[];
let lastTransition=String(byName[NAMES.lastTransition]?.value||'');
if(previous.status!==result.status){
  const tr={
    at:iso,
    from:previous.status,
    to:result.status,
    switchOn:result.switchOn,
    l3W:l3W===null?null:Math.round(l3W),
    baselineL3W:result.baselineL3W===null?null:Math.round(result.baselineL3W),
    deltaW:result.deltaW,
    powerW:result.powerW,
    reason:result.reason
  };
  history=[...history,tr].slice(-8);
  lastTransition=JSON.stringify(tr);
}

let lastHeatingAt=String(byName[NAMES.lastHeatingAt]?.value||'');
let lastHeatingPowerW=num(byName[NAMES.lastHeatingPowerW]?.value)??0;
if(result.active){
  lastHeatingAt=iso;
  lastHeatingPowerW=result.powerW;
}

const diagnostic={
  schema:VERSION,
  generatedAt:iso,
  valid:result.valid,
  switchOn:result.switchOn,
  active:result.active,
  status:result.status,
  powerW:result.powerW,
  l3W:l3W===null?null:Math.round(l3W),
  baselineL3W:result.baselineL3W===null?null:Math.round(result.baselineL3W),
  deltaW:result.deltaW,
  reason:result.reason,
  p1Sampled,
  lastP1SampleAt,
  thresholds:{
    startMinW:START_MIN_W,startMaxW:START_MAX_W,
    holdMinW:HOLD_MIN_W,holdMaxW:HOLD_MAX_W
  },
  safety:{
    observeOnly:true,
    physicalWritePerformed:false,
    switchAuthoritative:true
  }
};

await set(NAMES.switchOn,'boolean',result.switchOn);
await set(NAMES.active,'boolean',result.active);
await set(NAMES.powerW,'number',result.powerW);
await set(NAMES.status,'string',result.status);
await set(NAMES.lastSample,'string',iso);
if(result.baselineL3W!==null)await set(NAMES.baseline,'number',Math.round(result.baselineL3W));
await set(NAMES.lastTransition,'string',lastTransition);
await set(NAMES.history,'string',JSON.stringify(history));
await set(NAMES.lastHeatingAt,'string',lastHeatingAt);
await set(NAMES.lastHeatingPowerW,'number',lastHeatingPowerW);
await set(NAMES.diagnostic,'string',JSON.stringify(diagnostic));

return true;
