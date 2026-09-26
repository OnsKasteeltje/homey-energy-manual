// EV Gate v0.3.0 PHASE-AWARE CONTROL CONTRACT
// Validates authoritative OFF | 1P+A | 3P+A command. No device writes.

const VERSION='EM2_EV_ADAPTER_GATE_V0.3';
const MAPPING='PHASE_MODE_A_230V_V0.1';
const FRESH_MS=120000;

const IDS={
  intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',
  adapter:'f2118322-d59d-4aa8-b478-234effc3983c',
  state:'8e1efbb0-7999-494c-9429-7d274afacd79',
  gate:'4c66836b-77ae-43b5-b8e0-b32af15b57bc',
  health:'db467a16-7d23-4033-af96-42a69b932a2b'
};

const [intentVar,adapterVar,stateVar,gateVar,healthVar]=await Promise.all([
  Homey.logic.getVariable({id:IDS.intent}),
  Homey.logic.getVariable({id:IDS.adapter}),
  Homey.logic.getVariable({id:IDS.state}),
  Homey.logic.getVariable({id:IDS.gate}),
  Homey.logic.getVariable({id:IDS.health})
]);

const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};
const age=x=>{const t=Date.parse(String(x||''));return Number.isFinite(t)?Date.now()-t:Infinity;};

const intent=parse(intentVar?.value);
const adapter=parse(adapterVar?.value);
const state=parse(stateVar?.value);
const health=parse(healthVar?.value);
const ev=intent?.targets?.ev||{};
const cmd=adapter?.command||{};

const controlRevision=String(intent?.controlRevision||'');
const adapterControlRevision=String(adapter?.controlRevision||'');

const targetW=num(ev?.target_W);
const intentMode=String(ev?.phase_mode||'OFF');
const intentA=num(ev?.phase_requested_A);
const intentW=num(ev?.phase_requested_W);

const mode=String(cmd?.mode||'OFF');
const a=num(cmd?.requested_A);
const w=num(cmd?.requested_W);
const phaseCount=num(adapter?.electrical?.phase_count);
const wPerA=num(adapter?.electrical?.w_per_A);
const maxA=num(adapter?.electrical?.max_A);

const expectedPhaseCount=mode==='1P'?1:mode==='3P'?3:0;
const expectedW=mode==='1P'&&Number.isInteger(a)?a*230:
                mode==='3P'&&Number.isInteger(a)?a*690:0;
const expectedWPerA=mode==='1P'?230:mode==='3P'?690:0;

const intentFresh=age(intent?.generatedAt)<=FRESH_MS;
const adapterFresh=age(adapter?.generatedAt)<=FRESH_MS;
const stateFresh=age(state?.sampledAt)<=FRESH_MS;

const checks={
  schema:
    intent?.schema==='EM2_POWER_INTENT_V0.2' &&
    adapter?.schema==='EM2_EV_POWER_ADAPTER_V0.2' &&
    cmd?.schema==='EM2_EV_PHASE_COMMAND_V0.1',
  controlRevisionAligned:
    !!controlRevision &&
    adapterControlRevision===controlRevision,
  phaseAuthority:
    ev?.phase_control_schema==='EM2_EV_PHASE_CONTROL_V0.1' &&
    ev?.phase_control_authoritative===true,
  adapterSafety:
    adapter?.valid===true &&
    adapter?.readOnly===true &&
    adapter?.deviceWrites===false &&
    cmd?.physicalWrite===false &&
    adapter?.safety?.failClosed===true &&
    adapter?.safety?.semanticTokenGuard===true &&
    adapter?.safety?.exactPhasePowerMapping===true &&
    adapter?.safety?.mappingRevision===MAPPING,
  fresh:
    intentFresh &&
    adapterFresh,
  mode:
    ['OFF','1P','3P'].includes(mode) &&
    mode===intentMode,
  current:
    Number.isInteger(a) &&
    a===intentA &&
    a>=0 &&
    a<=maxA &&
    (mode==='OFF'?a===0:a>=6),
  power:
    Number.isInteger(w) &&
    w===intentW &&
    w===targetW &&
    w===expectedW,
  electrical:
    phaseCount===expectedPhaseCount &&
    wPerA===expectedWPerA,
  phaseOwner:
    cmd?.physicalPhaseOwner==='EASEE_EQUALIZER'
};

const errors=Object.entries(checks).filter(([,ok])=>!ok).map(([k])=>k.toUpperCase());

const gate={
  schema:VERSION,
  mode:'RUNTIME',
  contract:'EM2_EV_POWER_ADAPTER_V0.2',
  mapping:MAPPING,
  sourceRevision:num(adapter?.sourceRevision),
  intentRevision:num(intent?.sourceRevision),
  stateRevision:num(adapter?.stateRevision),
  coreRevision:num(state?.revision),
  controlRevision,
  adapterControlRevision,
  adapterGeneratedAt:adapter?.generatedAt??null,
  requested_A:a,
  requested_W:w,
  phaseMode:mode,
  target_W:targetW,
  updatedAt:new Date().toISOString(),
  checks,
  errors,
  deviceHealth:{
    observabilityOnly:true,
    schema:health?.schema??null,
    status:health?.status??'UNKNOWN',
    reason:health?.reason??'MISSING',
    stateFresh
  },
  finalStatus:errors.length?'FAIL':'PASS',
  authority:{
    phaseControl:true,
    singleWriterRequired:true,
    physicalWriter:'EV_ACTUATOR_ONLY'
  }
};

const value=JSON.stringify(gate);
if(gateVar?.value!==value){
  await Homey.logic.updateVariable({id:IDS.gate,variable:{value}});
}
return gate.finalStatus==='PASS';
