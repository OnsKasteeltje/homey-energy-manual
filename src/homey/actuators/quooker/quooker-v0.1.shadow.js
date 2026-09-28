// EM v2 | 60 Actuator | Quooker v0.1 SHADOW
// Validates EM2_Control_Quooker against the physical Cooker device.
// SHADOW ONLY: never writes the Cooker device. Publishes actuator status.

const CONTROL_VAR_ID='c3bc28a2-e09e-427d-b697-bc01f3e924d3';
const COOKER_DEVICE_ID='42992d14-c4e4-43fc-aaf0-29a73a8e2eb9';
const STATUS_VAR_NAME='EM2_Quooker_Actuator_Status';
const MAX_CONTROL_AGE_MS=180000;

const parse=v=>{try{return JSON.parse(String(v??''));}catch{return null;}};
const now=Date.now();

const [controlVar,cooker,vars]=await Promise.all([
  Homey.logic.getVariable({id:CONTROL_VAR_ID}),
  Homey.devices.getDevice({id:COOKER_DEVICE_ID}),
  Homey.logic.getVariables()
]);

const ctl=parse(controlVar?.value);
let statusVar=Object.values(vars).find(v=>v.name===STATUS_VAR_NAME)||null;

const ctlAt=Date.parse(String(ctl?.generatedAt||''));
const fresh=Number.isFinite(ctlAt)&&now-ctlAt>=0&&now-ctlAt<=MAX_CONTROL_AGE_MS;
const valid=ctl?.schema==='EM2_CONTROL_QUOOKER_V0.1'&&
  ctl?.safety?.deviceWrites===false&&fresh;

const desiredOn=valid&&ctl?.target_on===true;
const actualOn=cooker?.capabilitiesObj?.onoff?.value===true;
const wouldWrite=actualOn!==desiredOn;

const out={
  schema:'EM2_QUOOKER_ACTUATOR_STATUS_V0.1',
  generatedAt:new Date(now).toISOString(),
  mode:'SHADOW',
  controlValid:valid,
  controlFresh:fresh,
  controlGeneratedAt:ctl?.generatedAt??null,
  desiredOn,
  actualOn,
  wouldWrite,
  reason:valid?String(ctl?.reason||'UNKNOWN'):'FAIL_CLOSED_INVALID_OR_STALE_CONTROL',
  device:{id:COOKER_DEVICE_ID,name:String(cooker?.name||'Cooker')},
  safety:{
    shadow:true,
    deviceWrites:false,
    physicalWritePerformed:false,
    soleWriterNotYetClaimed:true
  }
};

const value=JSON.stringify(out);
if(!statusVar){
  statusVar=await Homey.logic.createVariable({variable:{name:STATUS_VAR_NAME,type:'string',value}});
}else if(statusVar.value!==value){
  await Homey.logic.updateVariable({id:statusVar.id,variable:{value}});
}
return true;
