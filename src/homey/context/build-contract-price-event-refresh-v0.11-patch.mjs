#!/usr/bin/env node
// Build the Contract Price Event Refresh v0.11 branch entirely outside Homey.
// Input: one current production Advanced Flow JSON + provisioned EVENT_STATE_ID.
// Output: complete Advanced Flow JSON suitable for one atomic Homey update.
//
// This script performs NO Homey calls.

import fs from 'node:fs';

const [,, inputPath, eventStateId, outputPath = 'contract-price-adapter-v0.11.patched.json'] = process.argv;
if (!inputPath || !eventStateId) {
  console.error('Usage: node build-contract-price-event-refresh-v0.11-patch.mjs <advanced-flow.json> <EVENT_STATE_ID> [output.json]');
  process.exit(2);
}

const flow = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
if (!flow?.cards || typeof flow.cards !== 'object') throw new Error('INVALID_ADVANCED_FLOW_NO_CARDS');

const PBTH_DEVICE = 'd28cdd44-ab8c-4f4c-8ea7-279f444ecd81';
const PBTH_ACTION_ID = `homey:device:${PBTH_DEVICE}:prices_json`;
const PBTH_TRIGGER_ID = `homey:device:${PBTH_DEVICE}:new_prices`;
const HOMEYSCRIPT_CONDITION_ID = 'homey:app:com.athom.homeyscript:runCode_v2';

// Fixed node UUIDs: generated once in GitHub so the patch is reproducible.
const ID = {
  trigger: '08a4a1b6-37d7-4df0-90c2-7402ef60aac1',
  eligibility: '28f94fe4-567a-49a0-b6dd-290126b032df',
  pbthAction: 'cd6dd83d-a3ed-49da-b5e7-aec5449a58de',
  bufferWrite: 'b2f2ee46-f9ad-4c73-bc2c-5a0f6120d7cf',
  postFetch: 'c093dafc-08cf-4699-874d-c5949bfd4fd4',
  note: 'a824c262-08de-4165-ab99-4fb06ec5cc4a'
};

for (const id of Object.values(ID)) {
  if (flow.cards[id]) throw new Error(`PATCH_NODE_ID_COLLISION:${id}`);
}

const entries = Object.entries(flow.cards);
const scheduledPbthEntry = entries.find(([, card]) => card?.type === 'action' && card?.id === PBTH_ACTION_ID && card?.args?.period === 'next_hours');
if (!scheduledPbthEntry) throw new Error('BASELINE_MISMATCH_PBTH_ACTION_NOT_FOUND');
const [scheduledPbthNodeId, scheduledPbthCard] = scheduledPbthEntry;

const downstream = Array.isArray(scheduledPbthCard.outputSuccess) ? scheduledPbthCard.outputSuccess : [];
if (downstream.length !== 1) throw new Error(`BASELINE_MISMATCH_PBTH_SUCCESS_EDGE_COUNT:${downstream.length}`);
const scheduledBufferNodeId = downstream[0];
const scheduledBufferCard = flow.cards[scheduledBufferNodeId];
if (!scheduledBufferCard || scheduledBufferCard.type !== 'action') throw new Error('BASELINE_MISMATCH_BUFFER_ACTION_NOT_FOUND');

// The clone must preserve the exact live Logic-setter card/args shape, but its droptoken
// must reference the newly cloned PBTH action node rather than the scheduled node.
const rewriteTokenSource = value => {
  if (typeof value === 'string') return value.split(scheduledPbthNodeId).join(ID.pbthAction);
  if (Array.isArray(value)) return value.map(rewriteTokenSource);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k,v]) => [k, rewriteTokenSource(v)]));
  return value;
};

const clone = obj => JSON.parse(JSON.stringify(obj));
const eventPbthCard = clone(scheduledPbthCard);
eventPbthCard.x = Number(scheduledPbthCard.x || 0) + 500;
eventPbthCard.y = Number(scheduledPbthCard.y || 0) + 420;
eventPbthCard.outputSuccess = [ID.bufferWrite];

const eventBufferCard = rewriteTokenSource(clone(scheduledBufferCard));
eventBufferCard.x = Number(eventPbthCard.x || 0) + 260;
eventBufferCard.y = Number(eventPbthCard.y || 0);
eventBufferCard.outputSuccess = [ID.postFetch];

const eligibilityCode = `// Contract Price Event Refresh v0.11 — EVENT ELIGIBILITY GATE\nconst IDS={canonical:'8d346495-f183-4072-86d0-c4bc9da94e2e',context:'93e41221-6b4d-4f5f-83dc-997c9620f758',eventState:'${eventStateId}'};\nconst read=async id=>Homey.logic.getVariable({id});\nconst write=async(id,value)=>Homey.logic.updateVariable({id,variable:{value}});\nconst parse=s=>{try{return JSON.parse(String(s??''));}catch{return null;}};\nconst nowMs=Date.now(),nowIso=new Date(nowMs).toISOString();\nconst canonical=await read(IDS.canonical),contract=String(canonical?.value||'FIXED').toUpperCase();\nconst stateVar=await read(IDS.eventState);\nconst eventState=parse(stateVar?.value)||{schema:'EM2_PRICE_EVENT_REFRESH_STATE_V0.1',lastAttemptAt:null,cooldownUntil:null,lastResult:'NEVER',lastReason:null};\nasync function stop(result,reason){await write(IDS.eventState,JSON.stringify({...eventState,lastResult:result,lastReason:reason}));return false;}\nif(contract!=='DYNAMIC')return await stop('SKIPPED_FIXED','CONTRACT_NOT_DYNAMIC');\nconst contextVar=await read(IDS.context),context=parse(contextVar?.value)||{},horizonHours=Number(context.horizonHours);\nif(Number.isFinite(horizonHours)&&horizonHours>=12)return await stop('SKIPPED_HORIZON_OK','HORIZON_GTE_12H');\nconst cooldownUntilMs=Date.parse(String(eventState.cooldownUntil||''));\nif(Number.isFinite(cooldownUntilMs)&&nowMs<cooldownUntilMs)return await stop('SKIPPED_COOLDOWN','NO_CHANGE_COOLDOWN');\nawait write(IDS.eventState,JSON.stringify({...eventState,lastAttemptAt:nowIso,lastResult:'ATTEMPT_ADMITTED',lastReason:'HORIZON_LT_12H'}));\nreturn true;`;

const postFetchCode = `// Contract Price Event Refresh v0.11 — POST-FETCH SEMANTIC PROCESSOR\nconst IDS={mirror:'211e5846-aada-4607-8d52-01b2ef578866',buffer:'29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b',context:'93e41221-6b4d-4f5f-83dc-997c9620f758',source:'3e5a182d-2479-479a-bb58-42a27f4a4e23',quality:'abedc6f4-cfee-4496-9b3c-418f1f3ad2bc',horizon:'587ea957-f9e9-44c7-b975-3bed53bd9ab8',updatedAt:'77e16ec7-9ebb-4488-9caf-47c1ab3d4ddb',eventState:'${eventStateId}'};\nconst COOLDOWN_MS=3600000,EPS=1e-9,read=async id=>Homey.logic.getVariable({id}),write=async(id,value)=>Homey.logic.updateVariable({id,variable:{value}}),parse=s=>{try{return JSON.parse(String(s??''));}catch{return null;}};\nconst nowMs=Date.now(),nowIso=new Date(nowMs).toISOString(),stateVar=await read(IDS.eventState),eventState=parse(stateVar?.value)||{},oldVar=await read(IDS.context),oldCtx=parse(oldVar?.value)||{},oldPrices=Array.isArray(oldCtx.priceSeries)?oldCtx.priceSeries.map(Number).filter(Number.isFinite):[];\nconst buffer=await read(IDS.buffer),raw=parse(buffer?.value),source=Array.isArray(raw)?raw:[],prices=[];for(const v of source){const n=Number(v);if(!Number.isFinite(n)||n<=-2||n>=5)break;prices.push(n);}\nasync function cool(result,reason){await write(IDS.eventState,JSON.stringify({...eventState,cooldownUntil:new Date(nowMs+COOLDOWN_MS).toISOString(),lastResult:result,lastReason:reason}));return false;}\nif(prices.length<4)return await cool('DEGRADED','LT_4_CONTIGUOUS_SLOTS');\nconst oldSlots=Number(oldCtx.slots)||oldPrices.length||0,oldHorizon=Number(oldCtx.horizonHours)||oldSlots*.25,newSlots=prices.length,newHorizon=newSlots*.25,overlap=Math.min(oldPrices.length,prices.length);let priceChanged=false;for(let i=0;i<overlap;i++){if(Math.abs(Number(oldPrices[i])-prices[i])>EPS){priceChanged=true;break;}}\nconst changed=newSlots>oldSlots||newHorizon>oldHorizon+EPS||priceChanged;if(!changed)return await cool('UNCHANGED','NO_SEMANTIC_PRICE_CHANGE');\nconst horizon=newHorizon>=12?'FULL':newHorizon>=6?'INTRADAY':'DIAGNOSTIC',ctx={...oldCtx,schema:'EM2_UNIFORM_PRICE_CONTEXT_V0.4',contractType:'DYNAMIC',source:'PBTH_PRICES_JSON_TARGETED_EVENT',quality:'GOOD',updatedAt:nowIso,importPriceNow:prices[0],negativeNow:prices[0]<0,horizon,horizonHours:newHorizon,slotMinutes:15,slots:newSlots,priceSeries:prices,guards:{...(oldCtx.guards||{}),targetedLogicReads:true,broadLogicEnumeration:false,broadDeviceEnumeration:false,pbthActionCardOnly:true,noActuatorWrites:true,eventDrivenShortHorizonRefresh:true,eventRefreshThresholdHours:12,noChangeCooldownMinutes:60}};\nawait write(IDS.mirror,'DYNAMIC');await write(IDS.context,JSON.stringify(ctx));await write(IDS.source,ctx.source);await write(IDS.quality,'GOOD');await write(IDS.horizon,horizon);await write(IDS.updatedAt,nowIso);await write(IDS.eventState,JSON.stringify({...eventState,cooldownUntil:null,lastResult:'UPDATED',lastReason:'SEMANTIC_PRICE_CHANGE'}));return true;`;

const baseX = Number(scheduledPbthCard.x || 0) + 500;
const baseY = Number(scheduledPbthCard.y || 0) + 160;

flow.cards[ID.trigger] = {
  type: 'trigger',
  id: PBTH_TRIGGER_ID,
  x: baseX - 520,
  y: baseY,
  args: { period: 'next_hours' },
  outputSuccess: [ID.eligibility]
};
flow.cards[ID.eligibility] = {
  type: 'condition',
  id: HOMEYSCRIPT_CONDITION_ID,
  x: baseX - 260,
  y: baseY,
  args: { code: eligibilityCode },
  inverted: false,
  outputTrue: [ID.pbthAction]
};
flow.cards[ID.pbthAction] = eventPbthCard;
flow.cards[ID.bufferWrite] = eventBufferCard;
flow.cards[ID.postFetch] = {
  type: 'condition',
  id: HOMEYSCRIPT_CONDITION_ID,
  x: Number(eventBufferCard.x || 0) + 260,
  y: Number(eventBufferCard.y || 0),
  args: { code: postFetchCode },
  inverted: false
};
flow.cards[ID.note] = {
  type: 'note',
  x: baseX - 520,
  y: baseY - 170,
  color: 'blue',
  value: 'v0.11 PBTH event refresh: DYNAMIC + horizon <12h + 60m no-change cooldown. Scheduled 15m route remains fallback. No actuator writes.'
};

// Static invariants before writing output.
const eventPbthCount = Object.values(flow.cards).filter(c => c?.type === 'action' && c?.id === PBTH_ACTION_ID).length;
if (eventPbthCount < 2) throw new Error('PATCH_INVARIANT_EXPECT_SCHEDULED_PLUS_EVENT_PBTH_ACTION');
if (flow.cards[ID.trigger].args.period !== 'next_hours') throw new Error('PATCH_INVARIANT_TRIGGER_PERIOD');
if (flow.cards[ID.pbthAction].args.period !== 'next_hours') throw new Error('PATCH_INVARIANT_ACTION_PERIOD');

fs.writeFileSync(outputPath, JSON.stringify(flow, null, 2) + '\n');
console.log(JSON.stringify({
  ok: true,
  input: inputPath,
  output: outputPath,
  eventStateId,
  reusedScheduledPbthNode: scheduledPbthNodeId,
  reusedScheduledBufferNode: scheduledBufferNodeId,
  addedNodeIds: ID
}, null, 2));
