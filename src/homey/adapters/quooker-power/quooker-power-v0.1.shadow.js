// EM v2 | 60 Adapter | Quooker Power v0.1 SHADOW
// Pi owns the time envelope. Homey applies realtime P1 hysteresis inside OPPORTUNITY.
// No physical device writes. Publishes EM2_Control_Quooker only.

const POWER_INTENT_ID='04b57041-dd7f-41f7-a00a-f023afb1ccee';
const P1_ROLLING_ID='5abde7ec-c426-4a9b-8d98-8b4ce544ef57';
const CONTROL_VAR_ID='c3bc28a2-e09e-427d-b697-bc01f3e924d3';
const MAX_INTENT_AGE_MS=180000;
const MAX_P1_AGE_MS=120000;
const OBS_NAMES={
  target:'EM2_Quooker_Shadow_Target_On',
  mode:'EM2_Quooker_Shadow_Mode_Code',
  grid:'EM2_Quooker_Shadow_AvgGridW'
};

const parse=v=>{try{return JSON.parse(String(v??''));}catch{return null;}};
const num=v=>{const n=Number(v);return Number.isFinite(n)?n:null;};
const now=Date.now();

const [intentVar,p1Var,outVar]=await Promise.all([
  Homey.logic.getVariable({id:POWER_INTENT_ID}),
  Homey.logic.getVariable({id:P1_ROLLING_ID}),
  Homey.logic.getVariable({id:CONTROL_VAR_ID})
]);

if(!outVar)return false;

const intent=parse(intentVar?.value);
const rolling=parse(p1Var?.value);
const previous=parse(outVar?.value);

const intentAt=Date.parse(String(intent?.generatedAt||''));
const intentFresh=Number.isFinite(intentAt)&&now-intentAt>=0&&now-intentAt<=MAX_INTENT_AGE_MS;
const intentValid=intent?.schema==='EM2_POWER_INTENT_V0.2'&&intent?.valid===true&&intentFresh;
const q=intent?.targets?.quooker||{};
const mode=['OPPORTUNITY','FORCED_ON','OFF'].includes(String(q.mode||'').toUpperCase())
  ? String(q.mode).toUpperCase()
  : 'OFF';

const modeledPowerW=Math.max(0,Math.round(num(q.modeled_power_W)||1580));
const startExportW=Math.max(0,Math.round(num(q.start_export_W)||1250));
const stopImportW=Math.max(0,Math.round(num(q.stop_import_W)||600));

const p1At=Date.parse(String(rolling?.generatedAt||rolling?.newestAt||''));
const p1Fresh=rolling?.schema==='EM2_P1_ROLLING_V0.1'&&rolling?.fresh===true&&
  Number.isFinite(p1At)&&now-p1At>=0&&now-p1At<=MAX_P1_AGE_MS;
const avgGridW=num(rolling?.avgGridW);

let targetOn=false;
let reason='FAIL_CLOSED_INVALID_INTENT';

if(intentValid){
  if(mode==='FORCED_ON'){
    targetOn=true;
    reason='FORCED_WINDOW';
  }else if(mode==='OFF'){
    targetOn=false;
    reason='OUTSIDE_WINDOW';
  }else if(!p1Fresh||avgGridW===null){
    targetOn=false;
    reason='OPPORTUNITY_P1_STALE';
  }else{
    const wasOn=previous?.schema==='EM2_CONTROL_QUOOKER_V0.1'&&previous?.target_on===true;
    if(wasOn){
      targetOn=avgGridW<stopImportW;
      reason=targetOn?'OPPORTUNITY_HOLD_HYSTERESIS':'OPPORTUNITY_STOP_IMPORT_LIMIT';
    }else{
      targetOn=avgGridW<=-startExportW;
      reason=targetOn?'OPPORTUNITY_START_EXPORT':'OPPORTUNITY_WAIT_EXPORT';
    }
  }
}

let observabilityIds=previous?.observabilityIds||null;
let obsVars=null;
if(
  !observabilityIds?.target ||
  !observabilityIds?.mode ||
  !observabilityIds?.grid
){
  // One-time bootstrap only. Normal runtime uses the persisted pinned IDs.
  const allVars=await Homey.logic.getVariables();
  const byName=Object.fromEntries(Object.values(allVars).map(v=>[v.name,v]));
  const ensure=async(name,type,initial)=>{
    if(byName[name])return byName[name];
    const created=await Homey.logic.createVariable({variable:{name,type,value:initial}});
    byName[name]=created;
    return created;
  };
  const targetObs=await ensure(OBS_NAMES.target,'boolean',false);
  const modeObs=await ensure(OBS_NAMES.mode,'number',0);
  const gridObs=await ensure(OBS_NAMES.grid,'number',0);
  observabilityIds={target:targetObs.id,mode:modeObs.id,grid:gridObs.id};
  obsVars={target:targetObs,mode:modeObs,grid:gridObs};
}else{
  const [targetObs,modeObs,gridObs]=await Promise.all([
    Homey.logic.getVariable({id:observabilityIds.target}),
    Homey.logic.getVariable({id:observabilityIds.mode}),
    Homey.logic.getVariable({id:observabilityIds.grid})
  ]);
  obsVars={target:targetObs,mode:modeObs,grid:gridObs};
}

const out={
  schema:'EM2_CONTROL_QUOOKER_V0.1',
  generatedAt:new Date(now).toISOString(),
  sourceControlRevision:intent?.controlRevision??null,
  mode:intentValid?mode:'OFF',
  target_on:targetOn,
  reason,
  modeledPowerW,
  thresholds:{startExportW,stopImportW},
  p1:{avgGridW,p1Fresh},
  observabilityIds,
  safety:{
    shadow:true,
    deviceWrites:false,
    failClosed:true,
    plannerOwner:'PI',
    executor:'HOMEY',
    singlePhysicalWriterRequired:true
  }
};

const value=JSON.stringify(out);
if(outVar.value!==value){
  await Homey.logic.updateVariable({id:CONTROL_VAR_ID,variable:{value}});
}

const modeCode=mode==='FORCED_ON'?2:mode==='OPPORTUNITY'?1:0;
if(obsVars?.target?.value!==targetOn){
  await Homey.logic.updateVariable({id:observabilityIds.target,variable:{value:targetOn}});
}
if(Number(obsVars?.mode?.value)!==modeCode){
  await Homey.logic.updateVariable({id:observabilityIds.mode,variable:{value:modeCode}});
}
if(avgGridW!==null&&Number(obsVars?.grid?.value)!==Math.round(avgGridW)){
  await Homey.logic.updateVariable({id:observabilityIds.grid,variable:{value:Math.round(avgGridW)}});
}
return true;
