// EM v2 | 60 Actuator | Quooker v0.2 LIVE
// Sole physical writer for Cooker, driven by EM2_Control_Quooker.
// Fail closed: invalid/stale control => desired OFF.
// Idempotent: writes only when actual state differs from desired state.

const CONTROL_VAR_ID='c3bc28a2-e09e-427d-b697-bc01f3e924d3';
const COOKER_DEVICE_ID='42992d14-c4e4-43fc-aaf0-29a73a8e2eb9';
const STATUS_VAR_ID='fa5e7753-4ad2-4335-900f-7b26ad980e1b';
const MAX_CONTROL_AGE_MS=180000;

const parse=v=>{try{return JSON.parse(String(v??''));}catch{return null;}};
const now=Date.now();

const [controlVar,cooker,statusVar]=await Promise.all([
  Homey.logic.getVariable({id:CONTROL_VAR_ID}),
  Homey.devices.getDevice({id:COOKER_DEVICE_ID}),
  Homey.logic.getVariable({id:STATUS_VAR_ID})
]);

if(!statusVar)return false;

const ctl=parse(controlVar?.value);
const ctlAt=Date.parse(String(ctl?.generatedAt||''));
const fresh=Number.isFinite(ctlAt)&&now-ctlAt>=0&&now-ctlAt<=MAX_CONTROL_AGE_MS;
const valid=ctl?.schema==='EM2_CONTROL_QUOOKER_V0.1'&&
  ctl?.safety?.deviceWrites===false&&
  ctl?.safety?.plannerOwner==='PI'&&
  ctl?.safety?.executor==='HOMEY'&&
  fresh;

const desiredOn=valid&&ctl?.target_on===true;
const actualOnBefore=cooker?.capabilitiesObj?.onoff?.value===true;
let actualOnAfter=actualOnBefore;
let physicalWritePerformed=false;
let writeError=null;

if(actualOnBefore!==desiredOn){
  try{
    await Homey.devices.setCapabilityValue({
      deviceId:COOKER_DEVICE_ID,
      capabilityId:'onoff',
      value:desiredOn
    });
    physicalWritePerformed=true;
    actualOnAfter=desiredOn;
  }catch(err){
    writeError=String(err?.message||err||'UNKNOWN_WRITE_ERROR');
  }
}

const out={
  schema:'EM2_QUOOKER_ACTUATOR_STATUS_V0.2',
  generatedAt:new Date(now).toISOString(),
  mode:'LIVE',
  controlValid:valid,
  controlFresh:fresh,
  controlGeneratedAt:ctl?.generatedAt??null,
  desiredOn,
  actualOnBefore,
  actualOnAfter,
  physicalWritePerformed,
  writeError,
  reason:valid?String(ctl?.reason||'UNKNOWN'):'FAIL_CLOSED_INVALID_OR_STALE_CONTROL',
  device:{id:COOKER_DEVICE_ID,name:String(cooker?.name||'Cooker')},
  safety:{
    shadow:false,
    deviceWrites:true,
    failClosed:true,
    soleWriterClaimed:true,
    idempotent:true
  }
};

const value=JSON.stringify(out);
if(statusVar.value!==value){
  await Homey.logic.updateVariable({id:STATUS_VAR_ID,variable:{value}});
}
return writeError===null;
