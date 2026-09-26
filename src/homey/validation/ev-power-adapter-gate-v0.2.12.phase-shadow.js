// Exact source captured from LIVE Homey Advanced Flow
// Flow: EM v2 | 80 Validation | EV Gate v0.2.11 ADAPTER-RETRIGGER
// Flow ID: ec5e5d34-8205-4cf0-a661-7bf744feb6e0
// Derived from live v0.2.10: 2026-09-25
// v0.2.11 invariant: Gate validates the control contract; Core/Easee chargeState is observability-only.

// === HomeyScript card 1: a0e10000-0000-4000-8000-000000000004 ===
// EV Gate v0.2.12 PHASE-SHADOW
const IDS={intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',adapter:'f2118322-d59d-4aa8-b478-234effc3983c',state:'8e1efbb0-7999-494c-9429-7d274afacd79',gate:'4c66836b-77ae-43b5-b8e0-b32af15b57bc',health:'db467a16-7d23-4033-af96-42a69b932a2b'};
const [intentVar,adapterVar,stateVar,gateVar,healthVar]=await Promise.all([Homey.logic.getVariable({id:IDS.intent}),Homey.logic.getVariable({id:IDS.adapter}),Homey.logic.getVariable({id:IDS.state}),Homey.logic.getVariable({id:IDS.gate}),Homey.logic.getVariable({id:IDS.health})]);
const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};const age=x=>{const t=Date.parse(String(x||''));return Number.isFinite(t)?Date.now()-t:Infinity;};
const intent=parse(intentVar?.value),adapter=parse(adapterVar?.value),state=parse(stateVar?.value),prev=parse(gateVar?.value),health=parse(healthVar?.value),ev=intent?.targets?.ev||{};
const targetW=num(ev?.target_W),targetStatus=String(ev?.status??''),targetSource=String(ev?.source??'');
const semanticToken=()=>String(intent?.controlRevision||'')||JSON.stringify({policy:String(intent?.policyRevision||''),engine:String(intent?.engineVersion||''),valid:intent?.valid===true,status:String(intent?.status||''),evTargetW:targetW,evStatus:targetStatus,evSource:targetSource,wwTargetOn:intent?.targets?.ww?.target_on??null,wwStatus:String(intent?.targets?.ww?.status||''),authority:String(intent?.policyProjection?.authoritySelector||intent?.policyProjection?.plannerOwner||'')});
const controlRevision=semanticToken(),adapterControlRevision=String(adapter?.controlRevision||''),r=num(intent?.sourceRevision),ar=num(adapter?.sourceRevision),coreR=num(state?.revision),ag=String(adapter?.generatedAt??'');
const a=num(adapter?.command?.requested_A),ph=num(adapter?.electrical?.phase_count),v=num(adapter?.electrical?.voltage_V),wpa=num(adapter?.electrical?.w_per_A),minA=num(adapter?.electrical?.min_A),maxA=num(adapter?.electrical?.max_A),minW=num(adapter?.electrical?.min_charge_W),maxW=num(adapter?.electrical?.max_charge_W),execW=num(adapter?.electrical?.executable_W),status=String(adapter?.status||'');
const coreChargeState=String(state?.tesla?.chargeState??'unknown'),stateFresh=age(state?.sampledAt)>=0&&age(state?.sampledAt)<=120000;
const electricalOK=ph===3&&v===230&&wpa===690&&minA===6&&maxA!==null&&maxA>=6&&maxA<=16&&Number.isInteger(maxA)&&minW===wpa*minA&&maxW===wpa*maxA;
let expectedA=null,allowedStatus=[];if(targetW!==null&&Number.isInteger(targetW)&&targetW>=0&&electricalOK){if(targetW===0){expectedA=0;allowedStatus=['ZERO_INTENT'];}else if(targetW<minW){expectedA=0;allowedStatus=['BELOW_MINIMUM_EXECUTABLE_POWER'];}else{expectedA=Math.min(maxA,Math.floor(targetW/wpa+Number.EPSILON));if(expectedA<minA)expectedA=0;allowedStatus=(expectedA===maxA&&targetW/wpa>maxA)?['CLAMPED_TO_MAX_CURRENT']:(expectedA*wpa<targetW?['QUANTIZED_DOWN']:['EXECUTABLE']);}}
const phaseShadow=adapter?.phaseShadow||{};
const phaseShadowMode=String(phaseShadow?.mode||'OFF'),phaseShadowA=num(phaseShadow?.requested_A);
const phaseShadowChecks={
  schema:phaseShadow?.schema==='EM2_EV_POWER_ADAPTER_PHASE_SHADOW_V0.1',
  valid:phaseShadow?.valid===true,
  mode:['OFF','1P','3P'].includes(phaseShadowMode),
  current:Number.isInteger(phaseShadowA)&&phaseShadowA>=0&&phaseShadowA<=16&&(phaseShadowMode==='OFF'?phaseShadowA===0:phaseShadowA>=6),
  phaseOwner:phaseShadow?.physicalPhaseOwner==='EASEE_EQUALIZER'&&phaseShadow?.phaseCommand===null,
  noWrites:phaseShadow?.readOnly===true&&phaseShadow?.deviceWrites===false&&phaseShadow?.physicalWrite===false
};
const phaseShadowErrors=Object.entries(phaseShadowChecks).filter(([,ok])=>!ok).map(([k])=>k.toUpperCase());
const commandRangeOK=a===0||(Number.isInteger(a)&&a>=6&&a<=maxA),mappingPowerOK=a!==null&&execW===a*wpa&&(targetW===0||a===0||execW<=targetW||a===maxA);
const checks={schema:adapter?.schema==='EM2_EV_POWER_ADAPTER_V0.1'&&adapter?.inputSchema==='EM2_POWER_INTENT_V0.2',controlRevisionAligned:!!controlRevision&&adapterControlRevision===controlRevision,safety:adapter?.readOnly===true&&adapter?.deviceWrites===false&&adapter?.command?.physicalWrite===false&&adapter?.safety?.failClosed===true&&adapter?.safety?.semanticTokenGuard===true&&adapter?.safety?.mappingRevision==='FLOOR_3P230_START6_RUN6_FAIL_CLOSED',coreStateObservabilityOnly:true,electrical:electricalOK,commandRange:commandRangeOK,translation:targetW!==null&&num(adapter?.input?.target_W)===targetW&&adapter?.valid===true&&a===expectedA&&allowedStatus.includes(status)&&mappingPowerOK};
const errors=Object.entries(checks).filter(([,ok])=>!ok).map(([k])=>k.toUpperCase());const semantic=JSON.stringify({controlRevision,adapterControlRevision,targetW,a,status,coreChargeState,coreR,ag});
const gate={schema:'EM2_EV_ADAPTER_GATE_V0.2',mode:'RUNTIME',contract:'EM2_EV_POWER_ADAPTER_V0.1',mapping:'FLOOR_3P230_START6_RUN6_FAIL_CLOSED',phaseShadow:{status:phaseShadowErrors.length?'FAIL':'PASS',checks:phaseShadowChecks,errors:phaseShadowErrors,mode:phaseShadowMode,requested_A:phaseShadowA,observabilityOnly:true,doesNotAffectProductionGate:true},sourceRevision:ar,intentRevision:r,stateRevision:num(adapter?.stateRevision),coreRevision:coreR,controlRevision,adapterControlRevision,adapterGeneratedAt:ag,requested_A:a,target_W:targetW,updatedAt:new Date().toISOString(),checks,errors,semantic,deviceHealth:{observabilityOnly:true,schema:health?.schema??null,status:health?.status??'UNKNOWN',reason:health?.reason??'MISSING'},finalStatus:errors.length?'FAIL':'PASS'};await Homey.logic.updateVariable({id:IDS.gate,variable:{value:JSON.stringify(gate)}});return gate.finalStatus==='PASS';
