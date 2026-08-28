// PREP TEMPLATE ONLY — DO NOT DEPLOY UNTIL CURRENT v0.2.2 RUNTIME IS CAPTURED.
// EM v2 | 20 Power Intent | P1 v0.2.3 LOW-LOAD
// This file is based on the older GitHub v0.2.1 policy semantics only.
// Runtime v0.2.2 is known to be Public-decoupled and may contain additional changes.
// Purpose: establish the targeted-read structure, not replace runtime source.

const ID={
  state:'__RESOLVE_EM2_STATE_ID__',
  decision:'__RESOLVE_EM2_DECISION_ID__',
  wwControl:'__RESOLVE_EM2_CONTROL_WW_ID__',
  previousIntent:'__RESOLVE_EM2_POWER_INTENT_ID__',
  outputIntent:'__RESOLVE_EM2_POWER_INTENT_ID__'
};

const [stateV,decisionV,wwV,prevV]=await Promise.all([
  Homey.logic.getVariable({id:ID.state}),
  Homey.logic.getVariable({id:ID.decision}),
  Homey.logic.getVariable({id:ID.wwControl}),
  Homey.logic.getVariable({id:ID.previousIntent})
]);

const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};
const state=parse(stateV?.value),decision=parse(decisionV?.value),ww=parse(wwV?.value),prev=parse(prevV?.value);

// IMPORTANT: sourceRevision derivation below must be reconciled to the actual v0.2.2 runtime.
// v0.2.1 used Public State revision. v0.2.2 is Public-decoupled, therefore the exact authoritative
// revision source must come from the runtime capture, not be guessed here.
const stateRev=num(state?.revision??state?.state_revision);
const decisionRev=num(decision?.sourceRevision??decision?.source_revision);
const wwRev=num(ww?.sourceRevision??ww?.source_revision);
const sourceRevision=(stateRev!==null&&decisionRev===stateRev&&wwRev===stateRev)?stateRev:null;

if(sourceRevision!==null&&prev?.schema==='EM2_POWER_INTENT_V0.2'&&num(prev?.sourceRevision)===sourceRevision&&prev?.valid===true)return true;

const aligned=sourceRevision!==null;
const dIntent=String(decision?.intent??'HOLD').toUpperCase(),priority=String(decision?.priority??'MAY').toUpperCase();
const flexW=Math.max(0,num(decision?.inputs?.flexExportBudgetW)??0);
const importBudgetW=Math.max(0,num(decision?.inputs?.discretionaryImportBudgetW)??0);
const remainingKWh=Math.max(0,num(decision?.inputs?.remainingKWh)??0);
const deadlineRaw=state?.goals?.teslaDeadline??null,deadlineMs=Date.parse(String(deadlineRaw||'')),hoursToDeadline=Number.isFinite(deadlineMs)?Math.max(0,(deadlineMs-Date.now())/3600000):null;
let evW=0,evStatus='IDLE',evSource='CORE_DECISION_IDLE';
if(aligned){
  if(dIntent==='TESLA_CHARGE_DEADLINE'){
    if(remainingKWh>0&&hoursToDeadline!==null&&hoursToDeadline>0){evW=Math.max(0,Math.round((remainingKWh/hoursToDeadline)*1000));evStatus='NUMERIC_DEADLINE_TARGET';evSource='REMAINING_KWH_OVER_TIME_TO_DEADLINE';}
    else{evW=0;evStatus='DEADLINE_TARGET_UNAVAILABLE';evSource='MISSING_DEADLINE_OR_REMAINING_ENERGY';}
  }else if(dIntent==='TESLA_CHARGE_OPPORTUNITY'){
    if(flexW>=800){evW=flexW;evStatus='NUMERIC_PV_EXPORT_TARGET';evSource='FLEX_EXPORT_BUDGET';}
    else{evW=0;evStatus='OPPORTUNITY_WITHOUT_PV_BUDGET';evSource='FAIL_CLOSED_NO_PV_EXPORT_BUDGET';}
  }else if(dIntent==='TESLA_BUFFER_EXPORT'){
    evW=flexW;evStatus='NUMERIC_PV_EXPORT_TARGET';evSource='FLEX_EXPORT_BUDGET';
  }
}
const wwAction=String(ww?.action??ww?.intent??'HOLD').toUpperCase(),wwOn=wwAction==='BOILER_ON'?true:wwAction==='BOILER_OFF'?false:null;
const out={schema:'EM2_POWER_INTENT_V0.2',policyRevision:'__COPY_EXACT_FROM_V0.2.2_RUNTIME__',generatedAt:new Date().toISOString(),sourceRevision,readOnly:true,controlMode:'SHADOW',deviceWrites:false,valid:aligned,status:aligned?'OK':'REVISION_MISMATCH',inputRevisions:{state:stateRev,decision:decisionRev,wwControl:wwRev},policyProjection:{decisionIntent:dIntent,priority,flexExportBudget_W:Math.round(flexW),discretionaryImportBudget_W:Math.round(importBudgetW),remaining_kWh:remainingKWh,hoursToDeadline:hoursToDeadline===null?null:Math.round(hoursToDeadline*100)/100,teslaOpportunityPolicy:'PV_SURPLUS_ONLY'},targets:{ev:{target_W:aligned?Math.round(evW):0,status:aligned?evStatus:'REVISION_MISMATCH',source:evSource},ww:{target_W:null,target_on:wwOn,status:'BINARY_INTENT',sourceAction:wwAction},battery:{target_W:0,status:'NOT_INTEGRATED'}},safety:{logicOnly:true,noDeviceReads:true,noDeviceWrites:true,noNetworkCalls:true,noPoller:true,idempotentBySourceRevision:true,targetedLogicReads:true,broadLogicEnumeration:false}};

const encoded=JSON.stringify(out);
if(prevV?.value!==encoded) await Homey.logic.updateVariable({id:ID.outputIntent,variable:{value:encoded}});
return aligned;
