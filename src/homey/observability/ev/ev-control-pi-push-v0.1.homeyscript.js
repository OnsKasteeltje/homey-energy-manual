// EM v2 | 81 Observability | EV Control Pi Push v0.1
// Control-neutral LAN evidence transport. Targeted Logic reads only.
// No device reads, no Logic writes, no physical writes, no planning decisions.
// Trigger after EM2_EV_Adapter_Gate and/or EM2_EV_Actuator_Status changes.

const VERSION='EMS_HOMEY_EV_CONTROL_EVIDENCE_V0.1';
const PI_URL='http://192.168.1.42:3100/state/ev-control';

const IDS={
  token:'33d0c297-0760-4fd1-810c-00ef4303974b',
  intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',
  adapter:'f2118322-d59d-4aa8-b478-234effc3983c',
  gate:'4c66836b-77ae-43b5-b8e0-b32af15b57bc',
  actuator:'ea1f8a44-2f6c-490e-9b86-bae761886cf9',
  health:'db467a16-7d23-4033-af96-42a69b932a2b'
};

const parse=v=>{
  try{return JSON.parse(String(v??''));}
  catch(_){return null;}
};

const [tokenV,intentV,adapterV,gateV,actuatorV,healthV]=await Promise.all([
  Homey.logic.getVariable({id:IDS.token}),
  Homey.logic.getVariable({id:IDS.intent}),
  Homey.logic.getVariable({id:IDS.adapter}),
  Homey.logic.getVariable({id:IDS.gate}),
  Homey.logic.getVariable({id:IDS.actuator}),
  Homey.logic.getVariable({id:IDS.health})
]);

const token=String(tokenV?.value??'').trim();
if(!token)throw new Error('PI_STATE_PUSH_TOKEN_EMPTY');

const payload={
  schema:VERSION,
  generatedAt:new Date().toISOString(),
  readOnly:true,
  observabilityOnly:true,
  controlImpact:'NONE',
  intent:parse(intentV?.value),
  adapter:parse(adapterV?.value),
  gate:parse(gateV?.value),
  actuator:parse(actuatorV?.value),
  deviceHealth:parse(healthV?.value),
  safety:{
    targetedLogicReadsOnly:true,
    deviceReads:false,
    logicWrites:false,
    deviceWrites:false
  }
};

if(!payload.gate&&!payload.actuator&&!payload.deviceHealth){
  throw new Error('EV_CONTROL_EVIDENCE_EMPTY');
}

const response=await fetch(PI_URL,{
  method:'POST',
  headers:{
    'Authorization':`Bearer ${token}`,
    'Content-Type':'application/json',
    'Accept':'application/json'
  },
  body:JSON.stringify(payload)
});

let result=null;
try{result=await response.json();}catch(_){}

if(!response.ok){
  throw new Error(`PI_EV_CONTROL_PUSH_HTTP_${response.status}_${String(result?.reason??'REJECTED')}`);
}
if(result?.evidenceWritten!==true){
  throw new Error('PI_EV_CONTROL_PUSH_NOT_WRITTEN');
}

return true;
