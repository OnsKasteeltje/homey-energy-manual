// EM v2 | 01 Quooker Detector | v0.5 LIVE OBSERVE-ONLY
// Three-phase isolated-pulse detector. No physical writes.

const VERSION='EM2_QUOOKER_DETECTOR_V0.5';
const COOKER_ID='42992d14-c4e4-43fc-aaf0-29a73a8e2eb9';
const P1_ID='7a696d77-15fb-4b68-9bce-f1e39bff5045';
const OFF_P1_REFRESH_MS=55000;
const START_MIN_W=1300, START_MAX_W=1900;
const HOLD_MIN_W=1100, HOLD_MAX_W=2050;
const SIDE_MAX_W=350, SIDE_HOLD_MAX_W=500;
const MAX_HEATING_MS=90000;

const IDS={
  switchOn:'fbd409dd-1813-4d1d-b095-48c5eead2eaa',
  active:'e1ade1a1-cffb-499f-ac62-42fe6254dd52',
  powerW:'57c81ed9-4c92-4293-b017-0700a9746598',
  status:'9b4159f1-2856-4284-9898-bf2e8ec6d0ff',
  lastSample:'a3b345ed-4e9a-4a44-9358-750caad10386',
  baselineL3:'bc90d360-d13f-4a99-95b1-8a4cc9bbed3d',
  lastTransition:'9f39700e-49f8-42e4-9252-6cafa98fca30',
  history:'d63f7fc9-0a6e-4a08-b299-e65572f56ce7',
  lastHeatingAt:'10e95965-b8f1-47b6-a60d-9abaff5b3eda',
  lastHeatingPowerW:'338fd52b-1151-49a0-9179-dc74666778e4',
  diagnostic:'23bfb36f-d883-47ca-a932-c98b1d8c074e',
};

const now=Date.now(), iso=new Date(now).toISOString();
const finite=v=>Number.isFinite(Number(v));
const num=v=>finite(v)?Number(v):null;
const round=v=>v===null?null:Math.round(v);
const parse=v=>{try{return JSON.parse(String(v??''));}catch{return null;}};
const getVar=async id=>Homey.logic.getVariable({id});
const write=async(id,value)=>Homey.logic.updateVariable({id,variable:{value}});

const [cooker,diagVar]=await Promise.all([
  Homey.devices.getDevice({id:COOKER_ID}),
  getVar(IDS.diagnostic),
]);
const pd=parse(diagVar?.value)||{};
const prev={
  switchOn:pd.switchOn===true,active:pd.active===true,status:String(pd.status||'UNKNOWN'),
  powerW:num(pd.powerW)??0,
  baselineL1W:num(pd.baselineL1W),baselineL2W:num(pd.baselineL2W),baselineL3W:num(pd.baselineL3W),
  heatingStartedAtMs:num(pd.heatingStartedAtMs),
  lastP1SampleAt:String(pd.lastP1SampleAt||''),
  history:Array.isArray(pd.history)?pd.history:null,
  lastHeatingAt:String(pd.lastHeatingAt||''),
  lastHeatingPowerW:num(pd.lastHeatingPowerW)??0,
};

const cookerOn=cooker?.capabilitiesObj?.onoff?.value===true;
const lastP1Ms=Date.parse(prev.lastP1SampleAt);
const p1AgeMs=Number.isFinite(lastP1Ms)?now-lastP1Ms:Infinity;
const switchChanged=prev.switchOn!==cookerOn;
const needP1=cookerOn||switchChanged||prev.baselineL3W===null||p1AgeMs>=OFF_P1_REFRESH_MS;

let l1W=null,l2W=null,l3W=null,p1Sampled=false,lastP1SampleAt=prev.lastP1SampleAt||null;
if(needP1){
  const p1=await Homey.devices.getDevice({id:P1_ID});
  l1W=num(p1?.capabilitiesObj?.['measure_power.l1']?.value);
  l2W=num(p1?.capabilitiesObj?.['measure_power.l2']?.value);
  l3W=num(p1?.capabilitiesObj?.['measure_power.l3']?.value);
  p1Sampled=l1W!==null&&l2W!==null&&l3W!==null;
  if(p1Sampled)lastP1SampleAt=iso;
}

let r;
if(!cookerOn&&!p1Sampled){
  r={valid:true,switchOn:false,active:false,powerW:0,status:'OFF',
    l1W:null,l2W:null,l3W:null,
    baselineL1W:prev.baselineL1W,baselineL2W:prev.baselineL2W,baselineL3W:prev.baselineL3W,
    deltaL1W:0,deltaL2W:0,deltaL3W:0,heatingStartedAtMs:null,reason:'SWITCH_OFF_BASELINE_REUSE'};
}else if(!p1Sampled){
  r={valid:false,switchOn:cookerOn,active:false,powerW:0,status:cookerOn?'ON_IDLE':'OFF',
    l1W,l2W,l3W,baselineL1W:prev.baselineL1W,baselineL2W:prev.baselineL2W,baselineL3W:prev.baselineL3W,
    deltaL1W:null,deltaL2W:null,deltaL3W:null,heatingStartedAtMs:null,reason:'INVALID_PHASE_SAMPLE'};
}else if(!cookerOn){
  r={valid:true,switchOn:false,active:false,powerW:0,status:'OFF',
    l1W,l2W,l3W,baselineL1W:l1W,baselineL2W:l2W,baselineL3W:l3W,
    deltaL1W:0,deltaL2W:0,deltaL3W:0,heatingStartedAtMs:null,reason:'SWITCH_OFF_BASELINE_TRACK'};
}else if(prev.baselineL1W===null||prev.baselineL2W===null||prev.baselineL3W===null){
  r={valid:true,switchOn:true,active:false,powerW:0,status:'ON_IDLE',
    l1W,l2W,l3W,baselineL1W:l1W,baselineL2W:l2W,baselineL3W:l3W,
    deltaL1W:0,deltaL2W:0,deltaL3W:0,heatingStartedAtMs:null,reason:'BASELINE_INITIALIZED'};
}else{
  const d1=l1W-prev.baselineL1W,d2=l2W-prev.baselineL2W,d3=l3W-prev.baselineL3W;
  const sideLimit=prev.active?SIDE_HOLD_MAX_W:SIDE_MAX_W;
  const sideStable=Math.abs(d1)<=sideLimit&&Math.abs(d2)<=sideLimit;
  const l3Signature=prev.active?(d3>=HOLD_MIN_W&&d3<=HOLD_MAX_W):(d3>=START_MIN_W&&d3<=START_MAX_W);
  const age=prev.active&&prev.heatingStartedAtMs!==null?Math.max(0,now-prev.heatingStartedAtMs):0;

  if(prev.active&&prev.heatingStartedAtMs!==null&&age>=MAX_HEATING_MS){
    r={valid:true,switchOn:true,active:false,powerW:0,status:'ON_IDLE',
      l1W,l2W,l3W,baselineL1W:l1W,baselineL2W:l2W,baselineL3W:l3W,
      deltaL1W:round(d1),deltaL2W:round(d2),deltaL3W:round(d3),heatingStartedAtMs:null,
      reason:'HEATING_MAX_DURATION_FAILSAFE'};
  }else if(l3Signature&&sideStable){
    r={valid:true,switchOn:true,active:true,powerW:round(d3),status:'HEATING',
      l1W,l2W,l3W,baselineL1W:prev.baselineL1W,baselineL2W:prev.baselineL2W,baselineL3W:prev.baselineL3W,
      deltaL1W:round(d1),deltaL2W:round(d2),deltaL3W:round(d3),
      heatingStartedAtMs:prev.active&&prev.heatingStartedAtMs!==null?prev.heatingStartedAtMs:now,
      reason:prev.active?'HEATING_HOLD_ISOLATED_L3':'HEATING_START_ISOLATED_L3'};
  }else{
    r={valid:true,switchOn:true,active:false,powerW:0,status:'ON_IDLE',
      l1W,l2W,l3W,baselineL1W:l1W,baselineL2W:l2W,baselineL3W:l3W,
      deltaL1W:round(d1),deltaL2W:round(d2),deltaL3W:round(d3),heatingStartedAtMs:null,
      reason:(!sideStable&&d3>=START_MIN_W&&d3<=START_MAX_W)
        ?'REJECT_SIDE_PHASE_MOVEMENT'
        :(prev.status==='HEATING'?'HEATING_STOP_BASELINE_RESET':'ON_IDLE_BASELINE_TRACK')};
  }
}

let history=prev.history;
if(!Array.isArray(history)){
  const hv=await getVar(IDS.history);
  history=parse(hv?.value);
  if(!Array.isArray(history))history=[];
}

let transition=null;
if(prev.status!==r.status){
  transition={at:iso,from:prev.status,to:r.status,switchOn:r.switchOn,
    l1W:round(l1W),l2W:round(l2W),l3W:round(l3W),
    baselineL1W:round(r.baselineL1W),baselineL2W:round(r.baselineL2W),baselineL3W:round(r.baselineL3W),
    deltaL1W:r.deltaL1W,deltaL2W:r.deltaL2W,deltaL3W:r.deltaL3W,powerW:r.powerW,reason:r.reason};
  history=[...history,transition].slice(-8);
}

let lastHeatingAt=prev.lastHeatingAt,lastHeatingPowerW=prev.lastHeatingPowerW;
if(r.active&&!prev.active){lastHeatingAt=iso;lastHeatingPowerW=r.powerW;}

const diagnostic={
  schema:VERSION,generatedAt:iso,valid:r.valid,switchOn:r.switchOn,active:r.active,status:r.status,powerW:r.powerW,
  l1W:round(r.l1W),l2W:round(r.l2W),l3W:round(r.l3W),
  baselineL1W:round(r.baselineL1W),baselineL2W:round(r.baselineL2W),baselineL3W:round(r.baselineL3W),
  deltaL1W:r.deltaL1W,deltaL2W:r.deltaL2W,deltaL3W:r.deltaL3W,heatingStartedAtMs:r.heatingStartedAtMs,
  reason:r.reason,p1Sampled,lastP1SampleAt,history,lastHeatingAt,lastHeatingPowerW,
  thresholds:{startMinW:START_MIN_W,startMaxW:START_MAX_W,holdMinW:HOLD_MIN_W,holdMaxW:HOLD_MAX_W,
    sidePhaseMaxAbsDeltaW:SIDE_MAX_W,sidePhaseHoldMaxAbsDeltaW:SIDE_HOLD_MAX_W,maxHeatingMs:MAX_HEATING_MS},
  safety:{observeOnly:true,physicalWritePerformed:false,switchAuthoritative:true,threePhaseIsolation:true,maxHeatingFailsafe:true},
};

const writes=[];
if(prev.switchOn!==r.switchOn)writes.push([IDS.switchOn,r.switchOn]);
if(prev.active!==r.active)writes.push([IDS.active,r.active]);
if(prev.powerW!==r.powerW)writes.push([IDS.powerW,r.powerW]);
if(prev.status!==r.status)writes.push([IDS.status,r.status]);
writes.push([IDS.lastSample,iso]);
if(round(prev.baselineL3W)!==round(r.baselineL3W)&&r.baselineL3W!==null)writes.push([IDS.baselineL3,round(r.baselineL3W)]);
if(transition){writes.push([IDS.lastTransition,JSON.stringify(transition)],[IDS.history,JSON.stringify(history)]);}
if(r.active&&!prev.active){writes.push([IDS.lastHeatingAt,lastHeatingAt],[IDS.lastHeatingPowerW,lastHeatingPowerW]);}
writes.push([IDS.diagnostic,JSON.stringify(diagnostic)]);
for(const [id,value] of writes)await write(id,value);

return true;
