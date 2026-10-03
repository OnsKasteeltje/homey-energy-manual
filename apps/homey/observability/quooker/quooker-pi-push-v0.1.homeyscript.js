// EM v2 | 81 Observability | Quooker Evidence Pi Push v0.1
// Control-neutral LAN evidence transport. Targeted Logic reads only.
// No device reads, no Logic writes, no physical writes, no planning decisions.
// Trigger after Quooker control, actuator-status and/or detector-diagnostic changes.

const VERSION='EMS_HOMEY_QUOOKER_EVIDENCE_V0.1';
const PI_URL='http://192.168.1.42:3100/state/quooker';

const IDS={
  token:'33d0c297-0760-4fd1-810c-00ef4303974b',
  control:'c3bc28a2-e09e-427d-b697-bc01f3e924d3',
  actuator:'fa5e7753-4ad2-4335-900f-7b26ad980e1b',
  detector:'23bfb36f-d883-47ca-a932-c98b1d8c074e'
};

const parse=v=>{
  try{return JSON.parse(String(v??''));}
  catch(_){return null;}
};

const [tokenV,controlV,actuatorV,detectorV]=await Promise.all([
  Homey.logic.getVariable({id:IDS.token}),
  Homey.logic.getVariable({id:IDS.control}),
  Homey.logic.getVariable({id:IDS.actuator}),
  Homey.logic.getVariable({id:IDS.detector})
]);

const token=String(tokenV?.value??'').trim();
if(!token)throw new Error('PI_STATE_PUSH_TOKEN_EMPTY');

const payload={
  schema:VERSION,
  generatedAt:new Date().toISOString(),
  readOnly:true,
  observabilityOnly:true,
  controlImpact:'NONE',
  control:parse(controlV?.value),
  actuator:parse(actuatorV?.value),
  detector:parse(detectorV?.value),
  safety:{
    targetedLogicReadsOnly:true,
    deviceReads:false,
    logicWrites:false,
    deviceWrites:false,
    physicalWritePerformed:false
  }
};

if(!payload.control&&!payload.actuator&&!payload.detector){
  throw new Error('QUOOKER_EVIDENCE_EMPTY');
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
  throw new Error(`PI_QUOOKER_PUSH_HTTP_${response.status}_${String(result?.reason??'REJECTED')}`);
}
if(result?.evidenceWritten!==true){
  throw new Error('PI_QUOOKER_PUSH_NOT_WRITTEN');
}

return true;
