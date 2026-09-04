// EM v2 | 60 Adapter | EV Power v0.1.2 MIN7 TARGETED-READ SHADOW
// Contract: EV_target_W only; fixed 3×230V; floor quantization; 0A or 7..16A; fail-closed; NO device writes/network/device reads.
const IDS={intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',state:'8e1efbb0-7999-494c-9429-7d274afacd79',maxA:'4a7398bb-9253-49ab-8850-820d1a622bd6',output:'f2118322-d59d-4aa8-b478-234effc3983c'};
const [intentVar,stateVar,maxVar,outVar]=await Promise.all([Homey.logic.getVariable({id:IDS.intent}),Homey.logic.getVariable({id:IDS.state}),Homey.logic.getVariable({id:IDS.maxA}),Homey.logic.getVariable({id:IDS.output})]);
const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};
const ageMs=x=>{const t=Date.parse(String(x||''));return Number.isFinite(t)?Date.now()-t:Infinity;};
const intent=parse(intentVar?.value),state=parse(stateVar?.value),prev=parse(outVar?.value);
const r=num(intent?.sourceRevision),sr=num(state?.revision),inputSchema=String(intent?.schema||''),ev=intent?.targets?.ev||{},targetW=num(ev?.target_W);
const PHASES=3,VOLTAGE_V=230,MIN_A=7,FRESH_MS=120000;
const maxConfig=num(maxVar?.value),MAX_A=Math.floor(Math.min(16,maxConfig??16));
const intentAgeMs=ageMs(intent?.generatedAt),stateAgeMs=ageMs(state?.sampledAt);
const intentFresh=intentAgeMs>=0&&intentAgeMs<=FRESH_MS,stateFresh=stateAgeMs>=0&&stateAgeMs<=FRESH_MS;
const chargeState=String(state?.tesla?.chargeState??'unknown'),cs=chargeState.toLowerCase();
const chargerAvailable=!['','unknown'].includes(cs)&&!cs.includes('offline')&&!cs.includes('error')&&!cs.includes('fault');
const confirmedA=num(state?.tesla?.offeredA),deviceRequestedA=num(state?.tesla?.requestedA);
if(r!==null&&prev?.schema==='EM2_EV_POWER_ADAPTER_V0.1'&&num(prev?.sourceRevision)===r&&prev?.inputSchema===inputSchema&&num(prev?.input?.target_W)===targetW&&num(prev?.electrical?.max_A)===MAX_A&&prev?.safety?.mappingRevision==='FLOOR_3P230_MIN7_FAIL_CLOSED')return true;
const schemaOk=inputSchema==='EM2_POWER_INTENT_V0.2';
const aligned=r!==null&&sr===r&&schemaOk&&intent?.valid===true&&intent?.status==='OK'&&intent?.readOnly===true&&intent?.controlMode==='SHADOW'&&intent?.deviceWrites===false;
const wPerA=PHASES*VOLTAGE_V,minChargeW=wPerA*MIN_A,maxChargeW=MAX_A>=MIN_A?wPerA*MAX_A:0;
let requestedA=0,status='INVALID_INPUT',reason='Power Intent/Core mismatch',valid=false,theoreticalA=targetW===null?null:targetW/wPerA;
if(!aligned){status='REVISION_OR_SCHEMA_MISMATCH';reason='Power Intent/Core niet revision/schema-aligned';}
else if(targetW===null||!Number.isInteger(targetW)||targetW<0){status='INVALID_NUMERIC_TARGET';reason='EV target_W moet een niet-negatief geheel getal zijn';}
else if(MAX_A<MIN_A){status='MAX_CURRENT_BELOW_MINIMUM';reason=`Configured max ${MAX_A} A < minimum ${MIN_A} A`;}
else if(!intentFresh){status='STALE_INTENT';reason=`Power Intent ouder dan ${FRESH_MS/1000}s`;}
else if(!stateFresh){status='STALE_CHARGER_STATE';reason=`Core/Easee context ouder dan ${FRESH_MS/1000}s`;}
else if(targetW===0){requestedA=0;status='ZERO_INTENT';reason='0 W → idle';valid=true;}
else if(!chargerAvailable){status='CHARGER_UNAVAILABLE';reason=`Charger state ${chargeState} niet uitvoerbaar/vertrouwd`;}
else if(targetW<minChargeW){requestedA=0;status='BELOW_MINIMUM_EXECUTABLE_POWER';reason=`${targetW} W < 3×230V×${MIN_A}A = ${minChargeW} W`;valid=true;}
else {requestedA=Math.min(MAX_A,Math.floor(theoreticalA+Number.EPSILON));if(requestedA<MIN_A)requestedA=0;valid=true;status=requestedA===MAX_A&&theoreticalA>MAX_A?'CLAMPED_TO_MAX_CURRENT':requestedA*wPerA<targetW?'QUANTIZED_DOWN':'EXECUTABLE';reason=`${targetW} W → floor(${theoreticalA.toFixed(3)} A) → ${requestedA} A @ 3×230 V`;}
const executableW=requestedA*wPerA,deltaW=targetW===null?null:executableW-targetW;
const out={schema:'EM2_EV_POWER_ADAPTER_V0.1',inputSchema,generatedAt:new Date().toISOString(),sourceRevision:r,stateRevision:sr,valid,status,reason,readOnly:true,controlMode:'SHADOW',deviceWrites:false,input:{target_W:targetW,targetStatus:String(ev?.status??''),targetSource:String(ev?.source??''),intentAgeSec:Number.isFinite(intentAgeMs)?Math.round(intentAgeMs/1000):null,stateAgeSec:Number.isFinite(stateAgeMs)?Math.round(stateAgeMs/1000):null},electrical:{phase_count:PHASES,phase_source:'FIXED_V0.1_3_PHASE',voltage_V:VOLTAGE_V,voltage_source:'FIXED_V0.1_230V',w_per_A:wPerA,min_A:MIN_A,max_A:MAX_A,min_charge_W:minChargeW,max_charge_W:maxChargeW,theoretical_A:theoreticalA===null?null:Math.round(theoreticalA*10000)/10000,executable_W:executableW,delta_W:deltaW},command:{capability:'setDynamicChargerCurrent',requested_A:requestedA,commanded_A:null,confirmed_A:confirmedA,device_requested_A:deviceRequestedA,confirmedSource:'CORE_EASEE_OFFERED_A',physicalWrite:false,startStopDerived:false},ownership:{policy:'ENERGY_CORE_P1',translation:'EV_POWER_ADAPTER',physicalWriter:'DISABLED'},safety:{logicOnly:true,noDeviceWrites:true,noInsights:true,noNetworkCalls:true,noPoller:true,revisionGuard:true,strictInputSchema:'EM2_POWER_INTENT_V0.2',policyDecisionMadeHere:false,idempotentByRevisionSchemaTarget:true,failClosed:true,intentFresh,stateFresh,chargerAvailable,mappingRevision:'FLOOR_3P230_MIN7_FAIL_CLOSED',neverIncreaseUpstreamPower:true,dynamicWriteRequiredForFutureLive:true,automaticPhaseSwitching:false}};
const value=JSON.stringify(out);if(outVar.value!==value)await Homey.logic.updateVariable({id:IDS.output,variable:{value}});return out.valid;